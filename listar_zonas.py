from utils import escanear, tabla


def lambda_handler(event, context):
    # Proceso
    zonas = escanear(tabla('TABLA_ZONAS'))
    resultado = sorted([{'zona_id': z['zona_id'], 'nombre': z['nombre'], 'tipo': z['tipo']} for z in zonas],
                       key=lambda z: z['nombre'])
    # Salida (json)
    return {'statusCode': 200, 'zonas': resultado}
