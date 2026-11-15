import json
import random
import sys
import urllib.request
from datetime import datetime

# Uso: python generar-reportes.py <API_URL> [ZONA] [CANTIDAD] [EMAIL] [CELULAR]
# Simula usuarios distintos reportando en la misma zona (incidente colectivo)
api = sys.argv[1].rstrip('/')
zona = sys.argv[2] if len(sys.argv) > 2 else 'Z-JESUSMARIA'
cantidad = int(sys.argv[3]) if len(sys.argv) > 3 else 10
email = sys.argv[4] if len(sys.argv) > 4 else 'demo@example.com'
celular = sys.argv[5] if len(sys.argv) > 5 else ''

descripciones = [
    ('SIN_SERVICIO', 'No tengo internet desde hace media hora, el celular dice sin servicio'),
    ('LLAMADAS', 'Las llamadas se cortan apenas contestan'),
    ('INTERNET_LENTO', 'Internet carga lentisimo, no abren ni los mensajes'),
    ('SMS', 'No puedo enviar SMS, aparece solo llamadas de emergencia'),
    ('SIN_SERVICIO', 'Perdi la señal por completo en mi casa')
]

for i in range(cantidad):
    tipo, descripcion = random.choice(descripciones)
    reporte = {
        'dni': '7' + str(random.randint(1000000, 9999999)),
        'nombre': 'Usuario Demo ' + str(i + 1),
        'numero_servicio': '9' + str(random.randint(10000000, 99999999)),
        'email': email,
        'telefono': celular,
        'zona_id': zona,
        'fecha_hora': datetime.now().isoformat(timespec='minutes'),
        'tipo_problema': tipo,
        'descripcion': descripcion
    }
    peticion = urllib.request.Request(api + '/reporte/crear', data=json.dumps(reporte).encode(),
                                      headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(peticion) as r:
        print(i + 1, json.loads(r.read()))
