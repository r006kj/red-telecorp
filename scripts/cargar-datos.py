import boto3
import sys

# Uso: python cargar-datos.py dev
stage = sys.argv[1] if len(sys.argv) > 1 else 'dev'
dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
t_zonas = dynamodb.Table(stage + '-t_zonas')
t_antenas = dynamodb.Table(stage + '-t_antenas')

# (zona_id, nombre, tipo, usuarios estimados por antena)
zonas = [
    ('Z-MIRAFLORES', 'Miraflores', 'RESIDENCIAL', 4000),
    ('Z-SURCO', 'Santiago de Surco', 'RESIDENCIAL', 3500),
    ('Z-ATE', 'Ate - Zona industrial', 'INDUSTRIAL', 1500),
    ('Z-BARRANCO', 'Barranco - Campus universitario', 'EDUCATIVA', 2500),
    ('Z-JESUSMARIA', 'Jesus Maria - Hospitales', 'MEDICA', 2000),
    ('Z-SANISIDRO', 'San Isidro - Centro financiero', 'CRITICA', 5000)
]

for zona_id, nombre, tipo, usuarios in zonas:
    antenas = ['ANT-' + zona_id[2:] + '-1', 'ANT-' + zona_id[2:] + '-2']
    t_zonas.put_item(Item={'zona_id': zona_id, 'nombre': nombre, 'tipo': tipo, 'antenas': antenas})
    for antena_id in antenas:
        t_antenas.put_item(Item={'antena_id': antena_id, 'zona_id': zona_id, 'estado': 'NORMAL',
                                 'modo_simulacion': 'normal', 'usuarios_estimados': usuarios})
print('Cargadas', len(zonas), 'zonas y', len(zonas) * 2, 'antenas en', stage)
