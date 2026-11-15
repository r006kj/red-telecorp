"""Clasificador de reportes con Gemini (Vertex AI) desplegado en Cloud Run.

Entrada : POST {"descripcion": "...", "tipoDeclarado": "SIN_SERVICIO"} + header X-Api-Key
Salida  : {"categoria": "...", "resumen": "..."}  (200)
          Si Gemini no responde se devuelve 502 y el Lambda de AWS usa el tipo del formulario.
"""
import base64
import json
import os
import urllib.error
import urllib.request

import google.auth
import google.auth.transport.requests
from flask import Flask, jsonify, request

TIPOS = ['SIN_SERVICIO', 'INTERNET_LENTO', 'LLAMADAS', 'SMS', 'COBERTURA', 'OTRO']
REGION = os.environ.get('VERTEX_REGION', 'us-central1')
MODELO = os.environ.get('VERTEX_MODEL', 'gemini-2.5-flash')
API_KEY = os.environ.get('API_KEY', '')
# Si el proyecto no tiene acceso a los modelos en Vertex AI, se usa la API de Gemini
# de AI Studio con una clave simple. El cuerpo de la peticion es identico.
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
TOPIC = os.environ.get('PUBSUB_TOPIC', 'telecorp-eventos')

INSTRUCCION = (
    'Eres el clasificador de incidencias de una empresa de telecomunicaciones en Peru. '
    'Lees la descripcion que escribio un cliente y devuelves la categoria tecnica que mejor '
    'corresponde, una sola, de esta lista: ' + ', '.join(TIPOS) + '. '
    'El cliente escribe en lenguaje coloquial y puede equivocarse al elegir su propia categoria: '
    'da mas peso a lo que describe que a lo que declaro. '
    'Devuelve ademas un resumen de una linea, en espanol, maximo 15 palabras, sin datos personales.'
)

app = Flask(__name__)
_credenciales = None
_proyecto = None


def token():
    """Credenciales de la propia cuenta de servicio de Cloud Run (ADC)."""
    global _credenciales, _proyecto
    if _credenciales is None:
        _credenciales, _proyecto = google.auth.default(
            scopes=['https://www.googleapis.com/auth/cloud-platform'])
    if not _credenciales.valid:
        _credenciales.refresh(google.auth.transport.requests.Request())
    return _credenciales.token


def proyecto():
    if _proyecto is None:
        token()
    return os.environ.get('GCP_PROJECT_ID') or _proyecto


def preguntar_a_gemini(descripcion, tipo_declarado):
    if GEMINI_API_KEY:
        url = ('https://generativelanguage.googleapis.com/v1beta/models/' + MODELO
               + ':generateContent?key=' + GEMINI_API_KEY)
        cabeceras = {'Content-Type': 'application/json'}
    else:
        url = ('https://' + REGION + '-aiplatform.googleapis.com/v1/projects/' + proyecto()
               + '/locations/' + REGION + '/publishers/google/models/' + MODELO + ':generateContent')
        cabeceras = {'Authorization': 'Bearer ' + token(), 'Content-Type': 'application/json'}
    cuerpo = {
        'systemInstruction': {'parts': [{'text': INSTRUCCION}]},
        'contents': [{'role': 'user', 'parts': [{'text':
            'Categoria declarada por el cliente: ' + str(tipo_declarado)
            + '\nDescripcion del cliente: ' + str(descripcion)}]}],
        'generationConfig': {
            'temperature': 0,
            'maxOutputTokens': 200,
            'responseMimeType': 'application/json',
            'responseSchema': {
                'type': 'OBJECT',
                'properties': {
                    'categoria': {'type': 'STRING', 'enum': TIPOS},
                    'resumen': {'type': 'STRING'}
                },
                'required': ['categoria', 'resumen']
            }
        }
    }
    peticion = urllib.request.Request(
        url, data=json.dumps(cuerpo).encode(), method='POST', headers=cabeceras)
    with urllib.request.urlopen(peticion, timeout=6) as r:
        respuesta = json.loads(r.read())
    texto = respuesta['candidates'][0]['content']['parts'][0]['text']
    return json.loads(texto)


@app.post('/')
def clasificar():
    if API_KEY and request.headers.get('X-Api-Key') != API_KEY:
        return jsonify({'error': 'no autorizado'}), 401
    datos = request.get_json(silent=True) or {}
    descripcion = (datos.get('descripcion') or '').strip()
    tipo_declarado = datos.get('tipoDeclarado') or 'OTRO'
    if not descripcion:
        return jsonify({'categoria': tipo_declarado, 'resumen': ''}), 200
    try:
        salida = preguntar_a_gemini(descripcion, tipo_declarado)
    except Exception as e:
        print('Gemini no respondio:', repr(e))
        return jsonify({'error': 'gemini no disponible'}), 502
    categoria = salida.get('categoria')
    if categoria not in TIPOS:
        categoria = tipo_declarado
    return jsonify({'categoria': categoria, 'resumen': salida.get('resumen', '')}), 200


@app.post('/eventos')
def eventos():
    """Puente AWS -> Pub/Sub. Lambda manda las filas y este servicio las publica con
    sus propias credenciales, asi ninguna clave de Google sale del proyecto."""
    if API_KEY and request.headers.get('X-Api-Key') != API_KEY:
        return jsonify({'error': 'no autorizado'}), 401
    filas = (request.get_json(silent=True) or {}).get('filas') or []
    if not filas:
        return jsonify({'publicados': 0}), 200
    url = ('https://pubsub.googleapis.com/v1/projects/' + proyecto()
           + '/topics/' + TOPIC + ':publish')
    publicados = 0
    try:
        for i in range(0, len(filas), 100):
            lote = filas[i:i + 100]
            mensajes = [{'data': base64.b64encode(json.dumps(f).encode()).decode()} for f in lote]
            peticion = urllib.request.Request(
                url, data=json.dumps({'messages': mensajes}).encode(), method='POST',
                headers={'Authorization': 'Bearer ' + token(), 'Content-Type': 'application/json'})
            with urllib.request.urlopen(peticion, timeout=15) as r:
                r.read()
            publicados += len(lote)
    except Exception as e:
        print('No se pudo publicar en Pub/Sub:', repr(e))
        return jsonify({'error': 'pubsub no disponible', 'publicados': publicados}), 502
    return jsonify({'publicados': publicados}), 200


@app.get('/salud')
def salud():
    return jsonify({'ok': True, 'modelo': MODELO, 'region': REGION,
                    'via': 'ai-studio' if GEMINI_API_KEY else 'vertex'}), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
