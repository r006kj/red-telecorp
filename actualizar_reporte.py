from utils import ESTADOS_REPORTE, actualizar_estado_reporte, notificar_usuario, tabla


def lambda_handler(event, context):
    # Entrada (json)
    print(event)
    body = event.get('body') or {}
    estado = body.get('estado')
    reporte_id = body.get('reporte_id', '')
    # Proceso
    if estado not in ESTADOS_REPORTE:
        return {'statusCode': 400, 'error': 'estado debe ser uno de ' + ', '.join(ESTADOS_REPORTE)}
    reporte = tabla('TABLA_REPORTES').get_item(Key={'reporte_id': reporte_id}).get('Item')
    if not reporte:
        return {'statusCode': 404, 'error': 'Reporte no encontrado'}
    actualizar_estado_reporte(reporte_id, estado, 'Cambio manual del operador')
    notificar_usuario(reporte, 'ESTADO_ACTUALIZADO', reporte.get('zona_nombre', 'tu zona'), estado)
    # Salida (json)
    return {'statusCode': 200, 'mensaje': 'Reporte ' + reporte_id + ' actualizado a ' + estado}
