from utils import (actualizar_estado_reporte, ahora_iso, avisar_operadores, notificar_usuario, obtener_incidente,
                   registrar_historial, tabla)

# tipo de aviso -> (estado del incidente, estado de sus reportes)
CAMBIOS = {
    'EN_EVALUACION': ('EN_EVALUACION', 'EN_REVISION'),
    'INCIDENCIA_IDENTIFICADA': ('IDENTIFICADO', 'EN_ATENCION'),
    'RESTABLECIDO': ('RESTABLECIDO', 'SOLUCIONADA')
}


def lambda_handler(event, context):
    # Entrada (json desde Step Functions)
    tipo = event['tipo']
    estado_incidente, estado_reporte = CAMBIOS[tipo]
    incidente = obtener_incidente(event['incidente_id'])
    # Proceso
    tabla('TABLA_INCIDENTES').update_item(Key={'incidente_id': incidente['incidente_id']},
                                          UpdateExpression='SET estado = :e, actualizado = :t',
                                          ExpressionAttributeValues={':e': estado_incidente, ':t': ahora_iso()})
    registrar_historial(incidente['incidente_id'], estado_incidente, 'Aviso ' + tipo, {'tipo': 'INCIDENTE'})
    reportes = tabla('TABLA_REPORTES')
    avisados, enviados = set(), 0
    for reporte_id in incidente.get('reportes', []):
        reporte = reportes.get_item(Key={'reporte_id': reporte_id}).get('Item')
        if not reporte:
            continue
        actualizar_estado_reporte(reporte_id, estado_reporte, 'Incidente ' + incidente['incidente_id'] + ': ' + tipo,
                                  incidente['incidente_id'])
        if reporte['dni'] in avisados:
            continue  # un aviso por persona aunque haya reportado varias veces
        avisados.add(reporte['dni'])
        enviados += len(notificar_usuario(reporte, tipo, incidente.get('zona_nombre', 'tu zona')))
    avisar_operadores({'tipo': 'INCIDENTE', 'incidente_id': incidente['incidente_id'], 'estado': estado_incidente,
                       'zona_id': incidente['zona_id'], 'prioridad': incidente.get('prioridad')})
    # Salida (json)
    return {'usuarios_avisados': len(avisados), 'mensajes_enviados': enviados}
