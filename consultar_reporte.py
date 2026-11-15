from utils import historial_de, limpiar, tabla


def lambda_handler(event, context):
    # Entrada (json)
    print(event)
    body = event.get('body') or {}
    reporte_id = body.get('reporte_id', '')
    dni = body.get('dni', '')
    # Proceso
    reporte = tabla('TABLA_REPORTES').get_item(Key={'reporte_id': reporte_id}).get('Item')
    if not reporte or reporte.get('dni') != dni:
        return {'statusCode': 404, 'error': 'No encontramos ese reporte con ese DNI. Si acabas de enviarlo, espera unos segundos.'}
    resultado = {
        'reporte_id': reporte['reporte_id'],
        'estado': reporte['estado'],
        'tipo_problema': reporte.get('tipo_problema'),
        'tipo_ia': reporte.get('tipo_ia'),
        'zona': reporte.get('zona_nombre', reporte.get('zona_id')),
        'incidente_id': reporte.get('incidente_id'),
        'historial': historial_de(reporte_id)
    }
    # Salida (json)
    return {'statusCode': 200, 'reporte': limpiar(resultado)}
