from utils import SEVERIDAD, obtener_incidente, obtener_zona, registrar_historial, tabla


def lambda_handler(event, context):
    # Entrada (json desde Step Functions)
    incidente = obtener_incidente(event['incidente_id'])
    zona = obtener_zona(incidente['zona_id']) or {}
    # Proceso: busca la antena de la zona con peor severidad
    antenas = tabla('TABLA_ANTENAS')
    peor, peor_severidad = None, 0
    for antena_id in zona.get('antenas', []):
        antena = antenas.get_item(Key={'antena_id': antena_id}).get('Item') or {}
        severidad = SEVERIDAD.get(antena.get('estado'), 0)
        if severidad > peor_severidad:
            peor, peor_severidad = antena, severidad
    falla = peor is not None
    if falla:
        tabla('TABLA_INCIDENTES').update_item(
            Key={'incidente_id': incidente['incidente_id']},
            UpdateExpression='SET antena_id = :a, severidad = :s, usuarios_estimados = :u',
            ExpressionAttributeValues={':a': peor['antena_id'], ':s': peor['estado'],
                                       ':u': int(peor.get('usuarios_estimados', 0))})
        detalle = 'Falla en ' + peor['antena_id'] + ' (' + peor['estado'] + ')'
    else:
        detalle = 'Antenas de la zona sin anomalias: requiere verificacion del operador'
    registrar_historial(incidente['incidente_id'], 'VERIFICACION_INFRA', detalle, {'tipo': 'INCIDENTE'})
    # Salida (json)
    return {'falla_infra': falla, 'antena_id': peor['antena_id'] if falla else None,
            'severidad': peor['estado'] if falla else None}
