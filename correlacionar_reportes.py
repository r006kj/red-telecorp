import os
from boto3.dynamodb.conditions import Attr, Key
from utils import (actualizar_estado_reporte, ahora_ts, bloquear_zona, consultar, crear_incidente, iniciar_flujo,
                   nuevo_id, obtener_zona, tabla, vincular_reporte)

VENTANA = 24 * 3600  # 24 horas en segundos


def lambda_handler(event, context):
    # Entrada (json con reporte_id)
    print(event)
    reporte = tabla('TABLA_REPORTES').get_item(Key={'reporte_id': event['reporte_id']}).get('Item')
    if not reporte:
        return {'statusCode': 404, 'error': 'Reporte no encontrado'}
    zona = obtener_zona(reporte['zona_id']) or {}
    # Proceso
    # 1) Si la zona ya tiene un incidente abierto, el reporte se suma a el
    if zona.get('incidente_activo') and vincular_reporte(zona['incidente_activo'], reporte):
        return {'statusCode': 200, 'resultado': 'VINCULADO'}
    # 2) Clave (zona, usuario): el mismo usuario reportando dos veces cuenta como uno
    ahora = ahora_ts()
    correlacion = tabla('TABLA_CORRELACION')
    correlacion.put_item(Item={'zona_id': reporte['zona_id'], 'usuario_id': reporte['dni'],
                               'reporte_id': reporte['reporte_id'], 'epoch': ahora, 'expira': ahora + VENTANA})
    recientes = consultar(correlacion, KeyConditionExpression=Key('zona_id').eq(reporte['zona_id']),
                          FilterExpression=Attr('epoch').gte(ahora - VENTANA))
    umbral = int(os.environ.get('UMBRAL_USUARIOS', '10'))
    print('Zona', reporte['zona_id'], ':', len(recientes), 'usuarios distintos en 24 h (umbral', umbral, ')')
    if len(recientes) < umbral:
        return {'statusCode': 200, 'resultado': 'AISLADO', 'usuarios': len(recientes)}
    # 3) Incidente colectivo
    candidato = nuevo_id('INC')
    activo = bloquear_zona(reporte['zona_id'], candidato)
    if activo != candidato:  # otra ejecucion gano la carrera
        vincular_reporte(activo, reporte)
        return {'statusCode': 200, 'resultado': 'VINCULADO'}
    crear_incidente(candidato, 'USUARIOS', reporte['zona_id'],
                    reportes=[r['reporte_id'] for r in recientes], usuarios=[r['usuario_id'] for r in recientes])
    for r in recientes:
        actualizar_estado_reporte(r['reporte_id'], 'EN_REVISION', 'Posible incidente colectivo ' + candidato, candidato)
    with correlacion.batch_writer() as lote:
        for r in recientes:
            lote.delete_item(Key={'zona_id': r['zona_id'], 'usuario_id': r['usuario_id']})
    iniciar_flujo(candidato)
    # Salida (json)
    return {'statusCode': 200, 'resultado': 'INCIDENTE_CREADO', 'incidente_id': candidato}
