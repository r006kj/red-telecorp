import datetime
from botocore.exceptions import ClientError
from utils import (a_decimal, actualizar_estado_reporte, avisar_operadores, es_condicional, obtener_incidente,
                   registrar_historial, tabla)


def lambda_handler(event, context):
    # Entrada (json desde Step Functions)
    incidente = obtener_incidente(event['incidente_id'])
    resultado = event['resultado']
    # Proceso
    fin = datetime.datetime.now(datetime.timezone.utc)
    inicio = datetime.datetime.fromisoformat(incidente['inicio'])
    duracion = round((fin - inicio).total_seconds() / 60, 1)
    tabla('TABLA_INCIDENTES').update_item(
        Key={'incidente_id': incidente['incidente_id']},
        UpdateExpression='SET estado = :e, fin = :f, duracion_min = :d REMOVE task_token, fase',
        ExpressionAttributeValues={':e': resultado, ':f': fin.isoformat(timespec='seconds'), ':d': a_decimal(duracion)})
    for reporte_id in incidente.get('reportes', []):
        actualizar_estado_reporte(reporte_id, 'CERRADA', 'Incidente ' + incidente['incidente_id'] + ' ' + resultado)
    try:  # libera la zona solo si este incidente sigue siendo el activo
        tabla('TABLA_ZONAS').update_item(Key={'zona_id': incidente['zona_id']},
                                         UpdateExpression='REMOVE incidente_activo',
                                         ConditionExpression='incidente_activo = :i',
                                         ExpressionAttributeValues={':i': incidente['incidente_id']})
    except ClientError as e:
        if not es_condicional(e):
            raise
    registrar_historial(incidente['incidente_id'], resultado, 'Duracion: ' + str(duracion) + ' min', {'tipo': 'INCIDENTE'})
    avisar_operadores({'tipo': 'INCIDENTE', 'incidente_id': incidente['incidente_id'], 'estado': resultado,
                       'zona_id': incidente['zona_id'], 'duracion_min': duracion})
    # Salida (json)
    return {'resultado': resultado, 'duracion_min': duracion}
