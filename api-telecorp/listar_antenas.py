from utils import escanear, limpiar, tabla


def lambda_handler(event, context):
    # Proceso
    antenas = escanear(tabla('TABLA_ANTENAS'))
    antenas.sort(key=lambda a: a['antena_id'])
    # Salida (json)
    return {'statusCode': 200, 'antenas': limpiar(antenas)}
