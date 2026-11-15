from utils import escanear, limpiar, tabla


def lambda_handler(event, context):
    # Proceso
    reportes = escanear(tabla('TABLA_REPORTES'))
    reportes.sort(key=lambda r: r.get('creado', ''), reverse=True)
    # Salida (json)
    return {'statusCode': 200, 'reportes': limpiar(reportes)}
