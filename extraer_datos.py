import boto3
import json
import os
import urllib.request
from botocore.exceptions import ClientError
from utils import ahora_iso, es_condicional, obtener_zona, registrar_historial, secreto_gcp, tabla


def lambda_handler(event, context):
    # Entrada (lote de mensajes de la cola de reportes)
    fallidos = []
    for mensaje in event['Records']:
        try:
            procesar(json.loads(mensaje['body']))
        except Exception as e:
            print('Error procesando reporte:', e)
            fallidos.append({'itemIdentifier': mensaje['messageId']})
    # Salida: solo se reintentan los mensajes que fallaron
    return {'batchItemFailures': fallidos}


def clasificar_con_ia(descripcion, tipo_declarado):
    """Llama a la Cloud Run function de GCP (Gemini). Si falla, usa el tipo del formulario."""
    configuracion = secreto_gcp()
    url = configuracion.get('clasificador_url')
    if not url:
        return {'categoria': tipo_declarado, 'fuente': 'FORMULARIO'}
    peticion = urllib.request.Request(
        url,
        data=json.dumps({'descripcion': descripcion, 'tipoDeclarado': tipo_declarado}).encode(),
        headers={'Content-Type': 'application/json', 'X-Api-Key': configuracion.get('clasificador_api_key', '')},
        method='POST')
    try:
        with urllib.request.urlopen(peticion, timeout=8) as r:
            salida = json.loads(r.read())
        salida['fuente'] = 'GEMINI'
        return salida
    except Exception as e:
        print('Clasificador IA no disponible, se usa el tipo declarado:', e)
        return {'categoria': tipo_declarado, 'fuente': 'FORMULARIO'}


def procesar(datos):
    reportes = tabla('TABLA_REPORTES')
    if reportes.get_item(Key={'reporte_id': datos['reporte_id']}).get('Item'):
        return  # SQS puede entregar dos veces: idempotencia
    ia = clasificar_con_ia(datos['descripcion'], datos['tipo_problema'])
    zona = obtener_zona(datos['zona_id']) or {}
    reporte = {
        **datos,
        'zona_nombre': zona.get('nombre', datos['zona_id']),
        'zona_tipo': zona.get('tipo', 'RESIDENCIAL'),
        'estado': 'REGISTRADA',
        'tipo_ia': ia.get('categoria', datos['tipo_problema']),
        'resumen_ia': ia.get('resumen', ''),
        'fuente_ia': ia.get('fuente', 'FORMULARIO'),
        'creado': ahora_iso()
    }
    try:
        reportes.put_item(Item=reporte, ConditionExpression='attribute_not_exists(reporte_id)')
    except ClientError as e:
        if es_condicional(e):
            return
        raise
    registrar_historial(reporte['reporte_id'], 'REGISTRADA',
                        'Reporte recibido (' + reporte['tipo_ia'] + ', fuente ' + reporte['fuente_ia'] + ')',
                        {'tipo': 'REPORTE', 'zona_id': reporte['zona_id']})
    boto3.client('lambda').invoke(FunctionName=os.environ['FN_CORRELACIONAR'], InvocationType='Event',
                                  Payload=json.dumps({'reporte_id': reporte['reporte_id']}).encode())
