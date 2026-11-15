from utils import completar_espera, obtener_incidente

# accion -> (fase en la que es valida, salida para la Step Function)
ACCIONES = {
    'confirmar': ('VERIFICACION', {'confirmado': True}),
    'descartar': ('VERIFICACION', {'confirmado': False}),
    'resolver': ('RESOLUCION', {'resuelto': True})
}


def lambda_handler(event, context):
    # Entrada (json)
    print(event)
    body = event.get('body') or {}
    accion = body.get('accion')
    # Proceso
    if accion not in ACCIONES:
        return {'statusCode': 400, 'error': 'accion debe ser una de ' + ', '.join(ACCIONES)}
    incidente = obtener_incidente(body.get('incidente_id', ''))
    if not incidente:
        return {'statusCode': 404, 'error': 'Incidente no encontrado'}
    fase, salida = ACCIONES[accion]
    if incidente.get('fase') != fase:
        return {'statusCode': 409, 'error': 'El incidente no espera ' + accion + ' (fase actual: ' + str(incidente.get('fase', 'ninguna')) + ')'}
    completar_espera(incidente, {**salida, 'por': 'OPERADOR'})
    # Salida (json)
    return {'statusCode': 200, 'mensaje': 'Accion ' + accion + ' aplicada a ' + incidente['incidente_id']}
