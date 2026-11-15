import boto3
import json
import pathlib
import sys

# Uso: python crear-secreto.py dev
# Lee gcp-key.json y gcp-salida.env de la raiz del repo (los entrega el responsable de GCP)
stage = sys.argv[1] if len(sys.argv) > 1 else 'dev'
raiz = pathlib.Path(__file__).resolve().parent.parent
variables = dict(linea.split('=', 1) for linea in (raiz / 'gcp-salida.env').read_text().split() if '=' in linea)

secreto = {
    'project_id': variables['GCP_PROJECT_ID'],
    'topic': variables['PUBSUB_TOPIC'],
    'clasificador_url': variables['CLASIFICADOR_URL'],
    'clasificador_api_key': variables['CLASIFICADOR_API_KEY'],
    'service_account': json.loads((raiz / 'gcp-key.json').read_text())
}
nombre = stage + '-secreto_gcp'
secretsmanager = boto3.client('secretsmanager', region_name='us-east-1')
try:
    secretsmanager.create_secret(Name=nombre, SecretString=json.dumps(secreto))
    print('Secreto creado:', nombre)
except secretsmanager.exceptions.ResourceExistsException:
    secretsmanager.put_secret_value(SecretId=nombre, SecretString=json.dumps(secreto))
    print('Secreto actualizado:', nombre)
