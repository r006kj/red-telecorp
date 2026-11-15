import boto3
import io
import pathlib
import subprocess
import sys
import time
import urllib.request
import zipfile

# Uso: python subir-amplify.py dev
# 1) genera frontend/config.js  2) comprime frontend/  3) lo publica en Amplify (despliegue manual, sin GitHub)
stage = sys.argv[1] if len(sys.argv) > 1 else 'dev'
raiz = pathlib.Path(__file__).resolve().parent.parent
subprocess.run([sys.executable, str(raiz / 'scripts' / 'generar-config.py'), stage], check=True)

cloudformation = boto3.client('cloudformation', region_name='us-east-1')
stack = cloudformation.describe_stacks(StackName='api-telecorp-' + stage)['Stacks'][0]
salidas = {o['OutputKey']: o['OutputValue'] for o in stack['Outputs']}
app_id = salidas['AmplifyAppId']

# Zip con index.html en la raiz (Amplify lo exige asi)
buffer = io.BytesIO()
with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as z:
    for archivo in (raiz / 'frontend').iterdir():
        if archivo.is_file() and archivo.name != 'config.example.js':
            z.write(archivo, archivo.name)

amplify = boto3.client('amplify', region_name='us-east-1')
despliegue = amplify.create_deployment(appId=app_id, branchName=stage)
peticion = urllib.request.Request(despliegue['zipUploadUrl'], data=buffer.getvalue(), method='PUT',
                                  headers={'Content-Type': 'application/zip'})
urllib.request.urlopen(peticion).read()
amplify.start_deployment(appId=app_id, branchName=stage, jobId=despliegue['jobId'])

# Espera a que termine (normalmente menos de 1 minuto)
while True:
    estado = amplify.get_job(appId=app_id, branchName=stage, jobId=despliegue['jobId'])['job']['summary']['status']
    print('Estado del despliegue:', estado)
    if estado in ('SUCCEED', 'FAILED', 'CANCELLED'):
        break
    time.sleep(5)
print('Portal de usuarios:', salidas['AmplifyUrl'])
print('Panel de operadores:', salidas['AmplifyUrl'] + '/operador.html')
