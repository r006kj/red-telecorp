from utils import escanear, historial_de, limpiar, tabla


def lambda_handler(event, context):
    # Proceso
    incidentes = escanear(tabla('TABLA_INCIDENTES'))
    incidentes.sort(key=lambda i: i.get('inicio', ''), reverse=True)
    for incidente in incidentes:
        incidente.pop('task_token', None)  # el token nunca sale de AWS
        incidente.pop('execution_arn', None)
        incidente['historial'] = historial_de(incidente['incidente_id'])
    # Salida (json)
    return {'statusCode': 200, 'incidentes': limpiar(incidentes)}
