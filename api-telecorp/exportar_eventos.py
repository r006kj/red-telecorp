import boto3
import json
import os
import urllib.request
from boto3.dynamodb.types import TypeDeserializer
from utils import ahora_iso, limpiar, secreto_gcp

deserializador = TypeDeserializer()


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


def publicar_pubsub(filas):
    """Envia las filas al puente en Cloud Run, que las publica en Pub/Sub.
    No se transporta ninguna credencial de Google hacia AWS: solo una API key propia."""
    configuracion = secreto_gcp()
    base = configuracion.get('clasificador_url')
    if not base:
        print('Sin URL de GCP: solo se respalda en S3')
        return
    peticion = urllib.request.Request(
        base.rstrip('/') + '/eventos',
        data=json.dumps({'filas': filas}).encode(), method='POST',
        headers={'Content-Type': 'application/json',
                 'X-Api-Key': configuracion.get('clasificador_api_key', '')})
    with urllib.request.urlopen(peticion, timeout=20) as r:
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
