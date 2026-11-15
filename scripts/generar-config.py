import boto3
import pathlib
import sys

# Uso: python generar-config.py dev
# Lee las salidas del stack y escribe frontend/config.js
stage = sys.argv[1] if len(sys.argv) > 1 else 'dev'
cloudformation = boto3.client('cloudformation', region_name='us-east-1')
stack = cloudformation.describe_stacks(StackName='api-telecorp-' + stage)['Stacks'][0]
salidas = {o['OutputKey']: o['OutputValue'] for o in stack['Outputs']}

config = '''window.CONFIG = {
  API_URL: "%s",
  WS_URL: "%s",
  REGION: "us-east-1",
  COGNITO_CLIENT_ID: "%s"
};
''' % (salidas['ServiceEndpoint'], salidas['ServiceEndpointWebsocket'], salidas['UserPoolClientId'])
(pathlib.Path(__file__).resolve().parent.parent / 'frontend' / 'config.js').write_text(config)
print(config)
print('URL del portal (Amplify):', salidas['AmplifyUrl'])
print('User Pool:', salidas['UserPoolId'])
