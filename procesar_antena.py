import boto3
import json
import os


def lambda_handler(event, context):
    # Entrada (evento de EventBridge)
    print(event)
    detalle = event.get('detail') or {}
    # Proceso
    try:
        gb = float(detalle['gb_por_minuto'])
        antena_id = str(detalle['antena_id'])
        if gb < 0:
            raise ValueError('GB negativo')
    except (KeyError, TypeError, ValueError):
        print('Metrica invalida descartada:', detalle)
        return {'statusCode': 400, 'error': 'Metrica invalida'}
    metrica = {'antena_id': antena_id, 'zona_id': detalle.get('zona_id'), 'gb': gb, 'fecha': detalle.get('fecha')}
    sqs = boto3.client('sqs')
    sqs.send_message(QueueUrl=os.environ['COLA_DATOS_URL'], MessageBody=json.dumps(metrica))
    # Salida (json)
    return {'statusCode': 200, 'metrica': metrica}
