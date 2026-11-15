"""Funciones compartidas por todas las Lambdas de api-telecorp."""
import datetime
import decimal
import json
import os
import re
import time
import smtplib
import uuid
from email.message import EmailMessage

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

dynamodb = boto3.resource('dynamodb')
stepfunctions = boto3.client('stepfunctions')
sns = boto3.client('sns')

# Reglas del caso
ESTADOS_REPORTE = ['REGISTRADA', 'EN_REVISION', 'EN_ATENCION', 'SOLUCIONADA', 'CERRADA']
TIPOS_PROBLEMA = ['SIN_SERVICIO', 'INTERNET_LENTO', 'LLAMADAS', 'SMS', 'COBERTURA', 'OTRO']
SEVERIDAD = {'INHABILITADA': 3, 'CAIDA': 2, 'SATURADA': 1}
PESO_ZONA = {'MEDICA': 5, 'CRITICA': 5, 'EDUCATIVA': 4, 'INDUSTRIAL': 3, 'COMERCIAL': 2, 'RESIDENCIAL': 1}


def clasificar_trafico(gb):
    # 0 se evalua primero porque tambien es menor que 60
    if gb == 0:
        return 'INHABILITADA'
    if gb < 60:
        return 'CAIDA'
    if gb > 129:
        return 'SATURADA'
    return 'NORMAL'


# ---------------------------------------------------------------- basicos
def tabla(variable):
    return dynamodb.Table(os.environ[variable])


def ahora_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')


def ahora_ts():
    return int(time.time())


def nuevo_id(prefijo):
    return prefijo + '-' + str(uuid.uuid4())[:8].upper()


def a_decimal(numero):
    return decimal.Decimal(str(numero))


def limpiar(objeto):
    """Convierte Decimal en int/float para devolver JSON."""
    return json.loads(json.dumps(objeto, default=lambda o: int(o) if o % 1 == 0 else float(o)))


def respuesta(codigo, clave, valor):
    # Mismo formato del taller: integration lambda, statusCode dentro del JSON
    return {'statusCode': codigo, clave: limpiar(valor)}


def escanear(tabla_dynamo, **kwargs):
    items = []
    r = tabla_dynamo.scan(**kwargs)
    items += r['Items']
    while 'LastEvaluatedKey' in r:
        r = tabla_dynamo.scan(ExclusiveStartKey=r['LastEvaluatedKey'], **kwargs)
        items += r['Items']
    return items


def consultar(tabla_dynamo, **kwargs):
    items = []
    r = tabla_dynamo.query(**kwargs)
    items += r['Items']
    while 'LastEvaluatedKey' in r:
        r = tabla_dynamo.query(ExclusiveStartKey=r['LastEvaluatedKey'], **kwargs)
        items += r['Items']
    return items


def es_condicional(error):
    return error.response['Error']['Code'] == 'ConditionalCheckFailedException'


# ---------------------------------------------------------------- historial
def registrar_historial(entidad_id, estado, detalle='', extra=None):
    item = {
        'entidad_id': entidad_id,
        'fecha': ahora_iso() + '#' + str(uuid.uuid4())[:6],
        'estado': estado,
        'detalle': detalle,
        'epoch': ahora_ts()
    }
    if extra:
        item.update({k: v for k, v in extra.items() if v is not None})
    tabla('TABLA_HISTORIAL').put_item(Item=item)


def historial_de(entidad_id):
    items = consultar(tabla('TABLA_HISTORIAL'), KeyConditionExpression=Key('entidad_id').eq(entidad_id))
    return [{'fecha': i['fecha'].split('#')[0], 'estado': i['estado'], 'detalle': i.get('detalle', '')} for i in items]


# ---------------------------------------------------------------- secreto de GCP
_secreto = None


def secreto_gcp():
    """Lee una sola vez el secreto con la configuracion de GCP (Secrets Manager)."""
    global _secreto
    if _secreto is None:
        try:
            valor = boto3.client('secretsmanager').get_secret_value(SecretId=os.environ['SECRETO_GCP'])
            _secreto = json.loads(valor['SecretString'])
        except Exception as e:
            print('No se pudo leer el secreto de GCP:', e)
            _secreto = {}
    return _secreto


_correo = None


def secreto_correo():
    """Lee una sola vez la cuenta Gmail (Secrets Manager) usada para enviar correos."""
    global _correo
    if _correo is None:
        try:
            valor = boto3.client('secretsmanager').get_secret_value(SecretId=os.environ['SECRETO_CORREO'])
            _correo = json.loads(valor['SecretString'])
        except Exception as e:
            print('No se pudo leer el secreto de correo:', e)
            _correo = {}
    return _correo


def enviar_correo_gmail(destino, asunto, texto):
    """Envia el correo por SMTP de Gmail (credenciales en Secrets Manager)."""
    cuenta = secreto_correo()
    if not cuenta.get('usuario'):
        return False
    mensaje = EmailMessage()
    mensaje['From'] = 'Red TeleCorp <' + cuenta['usuario'] + '>'
    mensaje['To'] = destino
    mensaje['Subject'] = asunto
    mensaje.set_content(texto)
    with smtplib.SMTP_SSL('smtp.gmail.com', 465, timeout=10) as servidor:
        servidor.login(cuenta['usuario'], cuenta['clave'])
        servidor.send_message(mensaje)
    return True


# ---------------------------------------------------------------- panel en tiempo real
def avisar_operadores(evento):
    endpoint = os.environ.get('WS_ENDPOINT')
    if not endpoint:
        return
    api = boto3.client('apigatewaymanagementapi', endpoint_url=endpoint)
    conexiones = tabla('TABLA_CONEXIONES')
    datos = json.dumps(limpiar({**evento, 'fecha': ahora_iso()})).encode()
    for c in escanear(conexiones):
        try:
            api.post_to_connection(ConnectionId=c['conexion_id'], Data=datos)
        except api.exceptions.GoneException:
            conexiones.delete_item(Key={'conexion_id': c['conexion_id']})
        except Exception as e:
            print('No se pudo avisar a', c['conexion_id'], e)


# ---------------------------------------------------------------- notificaciones
MENSAJES = {
    'EN_EVALUACION': ('Red TeleCorp: estamos evaluando tu reporte',
                      'Hola {nombre}: recibimos reportes similares en {zona}. Estamos evaluando el inconveniente. Codigo de reporte: {codigo}.'),
    'INCIDENCIA_IDENTIFICADA': ('Red TeleCorp: incidencia identificada en tu zona',
                                'Hola {nombre}: identificamos una incidencia que afecta a {zona}. Nuestro equipo ya esta trabajando en ella. Codigo: {codigo}.'),
    'RESTABLECIDO': ('Red TeleCorp: servicio restablecido',
                     'Hola {nombre}: el servicio en {zona} ha sido restablecido. Gracias por tu paciencia. Codigo: {codigo}.'),
    'ESTADO_ACTUALIZADO': ('Red TeleCorp: actualizacion de tu reporte',
                           'Hola {nombre}: tu reporte {codigo} cambio al estado {estado}.')
}


def normalizar_telefono(telefono):
    digitos = re.sub(r'\D', '', telefono or '')
    if len(digitos) == 9 and digitos.startswith('9'):
        return '+51' + digitos
    return '+' + digitos if digitos else None


def notificar_usuario(reporte, tipo, zona_nombre='tu zona', estado=None):
    asunto, plantilla = MENSAJES[tipo]
    texto = plantilla.format(nombre=reporte.get('nombre', ''), zona=zona_nombre,
                             codigo=reporte['reporte_id'], estado=estado or '')
    canales = []
    if reporte.get('email'):
        try:
            if enviar_correo_gmail(reporte['email'], asunto, texto):
                canales.append('CORREO')
        except Exception as e:
            print('Gmail fallo:', e)
    telefono = normalizar_telefono(reporte.get('telefono'))
    if telefono:
        try:
            sns.publish(PhoneNumber=telefono, Message=texto)
            canales.append('SMS')
        except Exception as e:
            print('SNS fallo:', e)
    registrar_historial(reporte['reporte_id'], 'NOTIFICACION',
                        tipo + ' enviado por ' + (', '.join(canales) if canales else 'ningun canal (revisar Gmail/SNS)'))
    return canales


# ---------------------------------------------------------------- reportes
def actualizar_estado_reporte(reporte_id, estado, detalle, incidente_id=None):
    expresion = 'SET estado = :e, actualizado = :t'
    valores = {':e': estado, ':t': ahora_iso()}
    if incidente_id:
        expresion += ', incidente_id = :i'
        valores[':i'] = incidente_id
    tabla('TABLA_REPORTES').update_item(Key={'reporte_id': reporte_id}, UpdateExpression=expresion,
                                        ExpressionAttributeValues=valores)
    registrar_historial(reporte_id, estado, detalle, {'tipo': 'REPORTE'})


# ---------------------------------------------------------------- incidentes
def obtener_zona(zona_id):
    return tabla('TABLA_ZONAS').get_item(Key={'zona_id': zona_id}).get('Item')


def obtener_incidente(incidente_id):
    return tabla('TABLA_INCIDENTES').get_item(Key={'incidente_id': incidente_id}).get('Item')


def bloquear_zona(zona_id, incidente_id):
    """Un solo incidente activo por zona. Devuelve el id del incidente que quedo activo."""
    try:
        tabla('TABLA_ZONAS').update_item(
            Key={'zona_id': zona_id},
            UpdateExpression='SET incidente_activo = :i',
            ConditionExpression='attribute_not_exists(incidente_activo)',
            ExpressionAttributeValues={':i': incidente_id})
        return incidente_id
    except ClientError as e:
        if not es_condicional(e):
            raise
        return obtener_zona(zona_id)['incidente_activo']


def crear_incidente(incidente_id, origen, zona_id, antena_id=None, severidad=None,
                    usuarios_estimados=0, reportes=None, usuarios=None):
    zona = obtener_zona(zona_id) or {}
    incidente = {
        'incidente_id': incidente_id,
        'origen': origen,
        'zona_id': zona_id,
        'zona_nombre': zona.get('nombre', zona_id),
        'zona_tipo': zona.get('tipo', 'RESIDENCIAL'),
        'estado': 'DETECTADO',
        'inicio': ahora_iso(),
        'reportes': reportes or [],
        'usuarios': usuarios or [],
        'usuarios_reportantes': len(usuarios or []),
        'usuarios_estimados': int(usuarios_estimados or 0)
    }
    if antena_id:
        incidente['antena_id'] = antena_id
    if severidad:
        incidente['severidad'] = severidad
    tabla('TABLA_INCIDENTES').put_item(Item=incidente)
    registrar_historial(incidente_id, 'DETECTADO', 'Origen: ' + origen, {'tipo': 'INCIDENTE', 'zona_id': zona_id})
    avisar_operadores({'tipo': 'INCIDENTE', 'incidente_id': incidente_id, 'estado': 'DETECTADO',
                       'zona_id': zona_id, 'origen': origen})
    return incidente


def iniciar_flujo(incidente_id):
    r = stepfunctions.start_execution(stateMachineArn=os.environ['SF_INCIDENTE_COLECTIVO'], name=incidente_id,
                                      input=json.dumps({'incidente_id': incidente_id}))
    tabla('TABLA_INCIDENTES').update_item(Key={'incidente_id': incidente_id},
                                          UpdateExpression='SET execution_arn = :a',
                                          ExpressionAttributeValues={':a': r['executionArn']})


def completar_espera(incidente, salida):
    """Reanuda la Step Function que espera (task token)."""
    token = incidente.get('task_token')
    if not token:
        return False
    try:
        stepfunctions.send_task_success(taskToken=token, output=json.dumps(salida))
    except Exception as e:
        print('Token vencido o invalido:', e)
    tabla('TABLA_INCIDENTES').update_item(Key={'incidente_id': incidente['incidente_id']},
                                          UpdateExpression='REMOVE task_token, fase')
    registrar_historial(incidente['incidente_id'], 'ESPERA_COMPLETADA', json.dumps(salida), {'tipo': 'INCIDENTE'})
    return True


MENSAJE_POR_ESTADO = {'DETECTADO': 'EN_EVALUACION', 'EN_EVALUACION': 'EN_EVALUACION',
                      'IDENTIFICADO': 'INCIDENCIA_IDENTIFICADA'}


def vincular_reporte(incidente_id, reporte):
    """Agrega un reporte nuevo a un incidente de zona que ya esta abierto."""
    incidente = obtener_incidente(incidente_id)
    if not incidente or incidente['estado'] in ('RESTABLECIDO', 'CERRADO', 'DESCARTADO', 'VENCIDO'):
        return False
    expresion = 'SET reportes = list_append(reportes, :r)'
    valores = {':r': [reporte['reporte_id']]}
    if reporte['dni'] not in incidente.get('usuarios', []):
        expresion += ', usuarios = list_append(usuarios, :u), usuarios_reportantes = usuarios_reportantes + :uno'
        valores.update({':u': [reporte['dni']], ':uno': 1})
    tabla('TABLA_INCIDENTES').update_item(Key={'incidente_id': incidente_id}, UpdateExpression=expresion,
                                          ExpressionAttributeValues=valores)
    estado_reporte = 'EN_ATENCION' if incidente['estado'] == 'IDENTIFICADO' else 'EN_REVISION'
    actualizar_estado_reporte(reporte['reporte_id'], estado_reporte, 'Vinculado al incidente ' + incidente_id, incidente_id)
    notificar_usuario(reporte, MENSAJE_POR_ESTADO.get(incidente['estado'], 'EN_EVALUACION'),
                      incidente.get('zona_nombre', 'tu zona'))
    return True
