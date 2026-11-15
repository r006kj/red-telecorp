from utils import ahora_ts, tabla


def lambda_handler(event, context):
    # Entrada: conexion nueva del panel de operadores
    conexion_id = event['requestContext']['connectionId']
    # Proceso
    tabla('TABLA_CONEXIONES').put_item(Item={'conexion_id': conexion_id, 'conectado': ahora_ts()})
    # Salida
    return {'statusCode': 200}
