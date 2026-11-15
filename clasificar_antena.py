import json
import os
from utils import (SEVERIDAD, a_decimal, ahora_iso, avisar_operadores, bloquear_zona, clasificar_trafico,
                   completar_espera, crear_incidente, iniciar_flujo, nuevo_id, obtener_incidente, obtener_zona,
                   registrar_historial, stepfunctions, tabla)


def lambda_handler(event, context):
    # Entrada (lote de mensajes de la cola de datos)
    fallidos = []
    for mensaje in event['Records']:
        try:
            procesar(json.loads(mensaje['body']))
        except Exception as e:
            print('Error procesando metrica:', e)
            fallidos.append({'itemIdentifier': mensaje['messageId']})
    # Salida: solo se reintentan los mensajes que fallaron
    return {'batchItemFailures': fallidos}


def procesar(metrica):
    antenas = tabla('TABLA_ANTENAS')
    antena = antenas.get_item(Key={'antena_id': metrica['antena_id']}).get('Item')
    if not antena:
        print('Antena desconocida:', metrica['antena_id'])
        return
    nuevo = clasificar_trafico(float(metrica['gb']))
    previo = antena.get('estado', 'NORMAL')
    antenas.update_item(Key={'antena_id': antena['antena_id']},
                        UpdateExpression='SET estado = :e, ultimo_gb = :g, actualizado = :t',
                        ExpressionAttributeValues={':e': nuevo, ':g': a_decimal(metrica['gb']), ':t': ahora_iso()})
    if nuevo == previo:
        return
    registrar_historial(antena['antena_id'], nuevo, previo + ' -> ' + nuevo + ' (' + str(metrica['gb']) + ' GB/min)',
                        {'tipo': 'ANTENA', 'zona_id': antena['zona_id']})
    avisar_operadores({'tipo': 'ANTENA', 'antena_id': antena['antena_id'], 'zona_id': antena['zona_id'],
                       'estado': nuevo, 'gb': metrica['gb']})
    if previo == 'NORMAL':
        al_detectar_anomalia(antena, nuevo)
    elif nuevo == 'NORMAL':
        al_recuperarse(antena)


def al_detectar_anomalia(antena, estado):
    # 1) Recurrencia: cada nueva falla se evalua en su propia Step Function
    stepfunctions.start_execution(stateMachineArn=os.environ['SF_RECURRENCIA'],
                                  input=json.dumps({'antena_id': antena['antena_id'], 'zona_id': antena['zona_id']}))
    # 2) Incidente de zona: se crea uno o se vincula al que ya existe
    candidato = nuevo_id('INC')
    activo = bloquear_zona(antena['zona_id'], candidato)
    if activo == candidato:
        crear_incidente(candidato, 'ANTENA', antena['zona_id'], antena_id=antena['antena_id'], severidad=estado,
                        usuarios_estimados=antena.get('usuarios_estimados', 0))
        iniciar_flujo(candidato)
        return
    incidente = obtener_incidente(activo)
    if not incidente:
        return
    if SEVERIDAD[estado] >= SEVERIDAD.get(incidente.get('severidad'), 0):
        tabla('TABLA_INCIDENTES').update_item(
            Key={'incidente_id': activo},
            UpdateExpression='SET antena_id = :a, severidad = :s, usuarios_estimados = :u',
            ExpressionAttributeValues={':a': antena['antena_id'], ':s': estado,
                                       ':u': int(antena.get('usuarios_estimados', 0))})
    registrar_historial(activo, 'ANTENA_VINCULADA', antena['antena_id'] + ' en estado ' + estado, {'tipo': 'INCIDENTE'})
    # Relacion usuarios <-> infraestructura: la antena confirma lo que el operador debia verificar
    if incidente.get('fase') == 'VERIFICACION':
        completar_espera(incidente, {'confirmado': True, 'por': 'ANTENA', 'antena_id': antena['antena_id']})


def al_recuperarse(antena):
    zona = obtener_zona(antena['zona_id']) or {}
    if not zona.get('incidente_activo'):
        return
    incidente = obtener_incidente(zona['incidente_activo'])
    if incidente and incidente.get('antena_id') == antena['antena_id'] and incidente.get('fase') == 'RESOLUCION':
        completar_espera(incidente, {'resuelto': True, 'por': 'AUTOMATICO', 'antena_id': antena['antena_id']})
