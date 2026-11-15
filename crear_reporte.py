import boto3
import json
import os
from utils import TIPOS_PROBLEMA, ahora_iso, nuevo_id, obtener_zona

OBLIGATORIOS = ['dni', 'nombre', 'numero_servicio', 'zona_id', 'fecha_hora', 'tipo_problema', 'descripcion']
OPCIONALES = ['email', 'telefono', 'lat', 'lon']


def lambda_handler(event, context):
    # Entrada (json)
    print(event)
    body = event.get('body') or {}
    # Proceso
    faltan = [campo for campo in OBLIGATORIOS if not str(body.get(campo, '')).strip()]
    if faltan:
        return {'statusCode': 400, 'error': 'Faltan campos: ' + ', '.join(faltan)}
    if not body.get('email') and not body.get('telefono'):
        return {'statusCode': 400, 'error': 'Indica un correo o un celular para enviarte novedades'}
    if body['tipo_problema'] not in TIPOS_PROBLEMA:
        return {'statusCode': 400, 'error': 'tipo_problema debe ser uno de ' + ', '.join(TIPOS_PROBLEMA)}
    if not obtener_zona(body['zona_id']):
        return {'statusCode': 400, 'error': 'Zona desconocida'}
    reporte = {campo: str(body.get(campo, '')).strip()[:1000] for campo in OBLIGATORIOS + OPCIONALES}
    reporte['reporte_id'] = nuevo_id('REP')
    reporte['recibido'] = ahora_iso()
    # La cola absorbe picos (corte de energia, clima) sin perder reportes
    sqs = boto3.client('sqs')
    sqs.send_message(QueueUrl=os.environ['COLA_REPORTES_URL'], MessageBody=json.dumps(reporte))
    # Salida (json)
    return {
        'statusCode': 202,
        'reporte_id': reporte['reporte_id'],
        'mensaje': 'Reporte recibido. Guarda el codigo para consultar su estado.'
    }
