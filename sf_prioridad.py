from utils import PESO_ZONA, SEVERIDAD, obtener_incidente, registrar_historial, tabla


def lambda_handler(event, context):
    # Entrada (json desde Step Functions)
    incidente = obtener_incidente(event['incidente_id'])
    # Proceso: prioridad = factor de usuarios x severidad x peso de la zona
    usuarios = max(int(incidente.get('usuarios_reportantes', 0)), int(incidente.get('usuarios_estimados', 0)))
    factor = 1 if usuarios < 50 else 2 if usuarios < 500 else 3 if usuarios < 5000 else 4
    severidad = SEVERIDAD.get(incidente.get('severidad'), 2)  # sin falla de antena: severidad media
    peso = PESO_ZONA.get(incidente.get('zona_tipo'), 1)
    puntaje = factor * severidad * peso
    nivel = 'CRITICA' if puntaje >= 30 else 'ALTA' if puntaje >= 15 else 'MEDIA' if puntaje >= 6 else 'BAJA'
    tabla('TABLA_INCIDENTES').update_item(Key={'incidente_id': incidente['incidente_id']},
                                          UpdateExpression='SET prioridad = :p, puntaje = :s',
                                          ExpressionAttributeValues={':p': nivel, ':s': puntaje})
    registrar_historial(incidente['incidente_id'], 'PRIORIZADO',
                        nivel + ' (usuarios ' + str(usuarios) + ' x severidad ' + str(severidad) + ' x zona '
                        + str(incidente.get('zona_tipo')) + ' = ' + str(puntaje) + ')', {'tipo': 'INCIDENTE'})
    # Salida (json)
    return {'prioridad': nivel, 'puntaje': puntaje}
