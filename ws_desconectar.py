from utils import tabla


def lambda_handler(event, context):
    # Entrada: el panel cerro la conexion
    conexion_id = event['requestContext']['connectionId']
    # Proceso
    tabla('TABLA_CONEXIONES').delete_item(Key={'conexion_id': conexion_id})
    # Salida
    return {'statusCode': 200}
