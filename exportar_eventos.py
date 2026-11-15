import base64
import boto3
import json
import os
import urllib.request
from boto3.dynamodb.types import TypeDeserializer
from utils import ahora_iso, limpiar, secreto_gcp

deserializador = TypeDeserializer()
_credenciales = None


def plano(imagen):
    """Convierte el formato de DynamoDB Streams ({"S": "..."}) en un diccionario normal."""
    return limpiar({k: deserializador.deserialize(v) for k, v in imagen.items()})


def a_fila(origen, tipo_cambio, d, evento_id):
    """Fila con el esquema de la tabla BigQuery telecorp.eventos."""
    fila = {'evento_id': evento_id, 'tipo_cambio': tipo_cambio, 'ts': ahora_iso(), 'zona_id': d.get('zona_id'),
            'zona_nombre': d.get('zona_nombre'), 'zona_tipo': d.get('zona_tipo'), 'estado': d.get('estado')}
    if origen == 'incidentes':
        fila.update({'tabla': 'incidentes', 'entidad_id': d['incidente_id'], 'incidente_id': d['incidente_id'],
                     'origen': d.get('origen'), 'antena_id': d.get('antena_id'), 'prioridad': d.get('prioridad'),
                     'severidad': d.get('severidad'),
                     'usuarios_afectados': max(d.get('usuarios_reportantes', 0), d.get('usuarios_estimados', 0)),
                     'usuarios_reportantes': d.get('usuarios_reportantes'), 'duracion_min': d.get('duracion_min'),
                     'inicio': d.get('inicio'), 'fin': d.get('fin')})
    else:
        fila.update({'tabla': 'reportes', 'entidad_id': d['reporte_id'], 'incidente_id': d.get('incidente_id'),
                     'origen': 'USUARIO', 'tipo_problema': d.get('tipo_ia') or d.get('tipo_problema'),
                     'tipo_declarado': d.get('tipo_problema'), 'fuente_ia': d.get('fuente_ia'),
                     'inicio': d.get('creado')})
    return {k: v for k, v in fila.items() if v is not None}


def token_gcp(cuenta):
    global _credenciales
    from google.auth.transport.requests import Request
    from google.oauth2 import service_account
    if _credenciales is None:
        _credenciales = service_account.Credentials.from_service_account_info(
            cuenta, scopes=['https://www.googleapis.com/auth/pubsub'])
    if not _credenciales.valid:
        _credenciales.refresh(Request())
    return _credenciales.token


def publicar_pubsub(filas):
    configuracion = secreto_gcp()
    if not configuracion.get('service_account'):
        print('Sin credencial de GCP: solo se respalda en S3')
        return
    url = ('https://pubsub.googleapis.com/v1/projects/' + configuracion['project_id'] + '/topics/'
           + configuracion['topic'] + ':publish')
    token = token_gcp(configuracion['service_account'])
    for i in range(0, len(filas), 100):
        mensajes = [{'data': base64.b64encode(json.dumps(f).encode()).decode()} for f in filas[i:i + 100]]
        peticion = urllib.request.Request(url, data=json.dumps({'messages': mensajes}).encode(), method='POST',
                                          headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
        with urllib.request.urlopen(peticion, timeout=10) as r:
            r.read()


def lambda_handler(event, context):
    # Entrada (cambios de DynamoDB Streams)
    s3 = boto3.client('s3')
    filas = []
    # Proceso
    for registro in event['Records']:
        if registro['eventName'] == 'REMOVE' or 'NewImage' not in registro['dynamodb']:
            continue
        origen = 'incidentes' if '-t_incidentes/' in registro['eventSourceARN'] else 'reportes'
        datos = plano(registro['dynamodb']['NewImage'])
        datos.pop('task_token', None)
        # Respaldo crudo, idempotente por eventID (bucket con versionado)
        clave = 'raw/' + origen + '/' + ahora_iso()[:10] + '/' + registro['eventID'] + '.json'
        s3.put_object(Bucket=os.environ['BUCKET_DATOS'], Key=clave, Body=json.dumps(datos).encode(),
                      ContentType='application/json')
        filas.append(a_fila(origen, registro['eventName'], datos, registro['eventID']))
    if filas:
        publicar_pubsub(filas)  # si falla, el stream reintenta el lote
    # Salida (json)
    return {'statusCode': 200, 'exportados': len(filas)}
