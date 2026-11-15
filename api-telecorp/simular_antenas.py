import boto3
import json
import os
import random
from utils import tabla, escanear, ahora_iso

# Rangos de GB por minuto segun el modo de cada antena
RANGOS = {
    'normal': (61, 128),
    'caida': (5, 59),
    'saturada': (130, 180),
    'inhabilitada': (0, 0)
}


def lambda_handler(event, context):
    # Entrada (evento de horario cada 1 minuto)
    prob_falla = float(os.environ.get('SIM_PROB_FALLA', '0'))
    events = boto3.client('events')
    # Proceso
    entradas = []
    for antena in escanear(tabla('TABLA_ANTENAS')):
        modo = antena.get('modo_simulacion', 'normal')
        if modo == 'normal' and random.random() < prob_falla:
            modo = random.choice(['caida', 'saturada', 'inhabilitada'])
        bajo, alto = RANGOS.get(modo, RANGOS['normal'])
        gb = 0 if alto == 0 else round(random.uniform(bajo, alto), 2)
        metrica = {'antena_id': antena['antena_id'], 'zona_id': antena['zona_id'], 'gb_por_minuto': gb, 'fecha': ahora_iso()}
        entradas.append({'Source': 'telecorp.antenas', 'DetailType': 'MetricaTrafico', 'Detail': json.dumps(metrica)})
    for i in range(0, len(entradas), 10):  # put_events acepta hasta 10 por llamada
        events.put_events(Entries=entradas[i:i + 10])
    # Salida (json)
    print('Metricas enviadas:', len(entradas))
    return {'statusCode': 200, 'metricas_enviadas': len(entradas)}
