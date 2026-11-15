"""Genera 30 dias de telemetria simulada y la carga en BigQuery.

Sirve para entrenar el modelo de prediccion: el simulador real lleva pocas horas
corriendo y ARIMA necesita una serie larga. Una antena (ANT-ATE-1) se degrada de
forma progresiva en la ultima semana, que es el caso que el modelo debe anticipar.

Uso (en Cloud Shell, desde la raiz del repo):
    python gcp/sembrar_historico.py            # genera y carga
    python gcp/sembrar_historico.py --solo-csv # solo genera historico.csv
"""
import csv
import datetime
import math
import pathlib
import random
import subprocess
import sys

DIAS = 30
CAIDA = 60.0
SATURACION = 129.0
ZONAS = ['MIRAFLORES', 'SURCO', 'ATE', 'BARRANCO', 'JESUSMARIA', 'SANISIDRO']
ANTENA_QUE_FALLA = 'ANT-ATE-1'
SALIDA = pathlib.Path(__file__).resolve().parent.parent / 'historico.csv'


def estado(gb):
    if gb <= 0:
        return 'INHABILITADA'
    if gb < CAIDA:
        return 'CAIDA'
    if gb > SATURACION:
        return 'SATURADA'
    return 'NORMAL'


def trafico(hora_del_dia, base):
    """Ciclo diario: valle de madrugada, pico entre el mediodia y la noche."""
    ciclo = math.sin((hora_del_dia - 6) / 24 * 2 * math.pi)
    return base + 18 * ciclo + random.gauss(0, 4)


def generar():
    random.seed(34)
    fin = datetime.datetime.now(datetime.timezone.utc).replace(minute=0, second=0, microsecond=0)
    inicio = fin - datetime.timedelta(days=DIAS)
    filas = []
    for zona in ZONAS:
        for n in (1, 2):
            antena = 'ANT-' + zona + '-' + str(n)
            base = random.uniform(88, 102)
            t = inicio
            while t < fin:
                horas_restantes = (fin - t).total_seconds() / 3600
                gb = trafico(t.hour, base)
                # Degradacion progresiva de una antena durante los ultimos 7 dias
                if antena == ANTENA_QUE_FALLA and horas_restantes < 24 * 7:
                    avance = 1 - (horas_restantes / (24 * 7))
                    gb -= 45 * (avance ** 2)
                gb = round(max(gb, 0.0), 2)
                filas.append([antena, 'Z-' + zona, t.isoformat(timespec='seconds'), gb, estado(gb)])
                t += datetime.timedelta(hours=1)
    return filas


def main():
    filas = generar()
    with SALIDA.open('w', newline='', encoding='utf-8') as f:
        csv.writer(f).writerows(filas)
    bajo_umbral = sum(1 for r in filas if r[0] == ANTENA_QUE_FALLA and r[3] < CAIDA)
    print('Generadas', len(filas), 'filas en', SALIDA.name)
    print('  ', ANTENA_QUE_FALLA, 'termina con', bajo_umbral, 'horas por debajo de', CAIDA, 'GB/min')
    if '--solo-csv' in sys.argv:
        return
    print('Cargando en BigQuery...')
    subprocess.run(['bq', 'load', '--source_format=CSV', '--replace',
                    'telecorp.telemetria', str(SALIDA),
                    'antena_id:STRING,zona_id:STRING,ts:TIMESTAMP,gb_min:FLOAT,estado:STRING'],
                   check=True)
    print('Listo. Ahora ejecuta: bq query --use_legacy_sql=false < gcp/modelo_prediccion.sql')


if __name__ == '__main__':
    main()
