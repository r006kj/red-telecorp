from botocore.exceptions import ClientError
from utils import es_condicional, registrar_historial, tabla

MODOS = ['normal', 'caida', 'saturada', 'inhabilitada']


def lambda_handler(event, context):
    # Entrada (json)
    print(event)
    body = event.get('body') or {}
    antena_id = body.get('antena_id', '')
    modo = body.get('modo')
    # Proceso: fuerza el estado de una antena para la demo
    if modo not in MODOS:
        return {'statusCode': 400, 'error': 'modo debe ser uno de ' + ', '.join(MODOS)}
    try:
        tabla('TABLA_ANTENAS').update_item(Key={'antena_id': antena_id},
                                           UpdateExpression='SET modo_simulacion = :m',
                                           ConditionExpression='attribute_exists(antena_id)',
                                           ExpressionAttributeValues={':m': modo})
    except ClientError as e:
        if es_condicional(e):
            return {'statusCode': 404, 'error': 'Antena no encontrada'}
        raise
    registrar_historial(antena_id, 'SIMULACION', 'Modo ' + modo, {'tipo': 'ANTENA'})
    # Salida (json)
    return {'statusCode': 200, 'mensaje': 'Modo ' + modo + ' aplicado. Se refleja en la siguiente metrica (hasta 1 minuto).'}
