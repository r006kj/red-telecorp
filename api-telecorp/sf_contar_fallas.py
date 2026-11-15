import datetime
import os
from boto3.dynamodb.conditions import Key
from utils import SEVERIDAD, consultar, tabla


def lambda_handler(event, context):
    # Entrada (json desde Step Functions)
    antena_id = event['antena_id']
    # Proceso: transiciones a una anomalia en los ultimos 7 dias
    desde = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=7)).isoformat(timespec='seconds')
    eventos = consultar(tabla('TABLA_HISTORIAL'),
                        KeyConditionExpression=Key('entidad_id').eq(antena_id) & Key('fecha').gte(desde))
    fallas = sum(1 for e in eventos if e['estado'] in SEVERIDAD)
    # Salida (json)
    return {'antena_id': antena_id, 'zona_id': event.get('zona_id'), 'fallas': fallas,
            'umbral': int(os.environ.get('UMBRAL_RECURRENCIA', '3'))}
