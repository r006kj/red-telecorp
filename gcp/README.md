# Lado Google Cloud

Esta carpeta vive en la raiz del repo, al lado de `api-telecorp/`, `frontend/`,
`arquitectura/` y `scripts/`.

AWS opera (tiempo real, estado, orquestacion). Google Cloud analiza y clasifica
(historico, ML, panel). El puente son dos llamadas que salen de Lambda con
credenciales guardadas en AWS Secrets Manager.

| Pieza | Para que |
|---|---|
| Pub/Sub `telecorp-eventos` | recibe cada cambio de incidentes y reportes |
| BigQuery `telecorp.eventos` | historico, alimentado por suscripcion nativa (sin codigo) |
| BigQuery `telecorp.telemetria` | serie de trafico por antena, para el modelo |
| Cloud Run `clasificador-reporte` | dos rutas: `/` clasifica con Gemini, `/eventos` publica en Pub/Sub |
| BigQuery ML `modelo_trafico` | predice la caida de una antena antes del umbral |
| Looker Studio | panel sobre las vistas |

## Pasos

Todo corre en **Google Cloud Shell** (ya trae `gcloud` y `bq`, no hay que instalar nada).

```bash
git clone https://github.com/r006kj/red-telecorp.git && cd red-telecorp
gcloud config set project TU_PROYECTO

bash gcp/provisionar.sh          # ~8 min: APIs, BigQuery, Pub/Sub, Cloud Run
python gcp/sembrar_historico.py  # ~1 min: 30 dias de telemetria simulada
bq query --use_legacy_sql=false < gcp/modelo_prediccion.sql   # ~4 min: entrena ARIMA
bq query --use_legacy_sql=false < gcp/vistas_looker.sql       # ~10 s: vistas del panel
```

`provisionar.sh` deja un archivo en la raiz: `gcp-salida.env`.
Llevalo a la maquina que tiene credenciales de AWS:

```bash
python scripts/crear-secreto.py dev     # desde la raiz del repo
cd api-telecorp && npx serverless deploy --stage dev
```

Ese archivo no se sube a GitHub (esta en `.gitignore`).

## Por que no hay claves de service account

Las organizaciones suelen bloquear su creacion (`constraints/iam.disableServiceAccountKeyCreation`),
pero mas alla de la politica, mover un JSON de credenciales de Google hacia AWS es la parte
mas fragil de cualquier integracion multinube: no caduca, no se revoca facil y viaja por
canales que nadie controla.

En su lugar, Cloud Run hace de puente. Lambda le manda las filas a `/eventos` con una API key
propia, y Cloud Run las publica en Pub/Sub usando su identidad de GCP, que nunca sale del
proyecto. Si la API key se filtra, se rota con un redespliegue y no da acceso a nada mas
que a ese endpoint.

## Panel de Looker Studio

1. https://lookerstudio.google.com -> Crear -> Fuente de datos -> BigQuery
2. Agrega una fuente por vista: `v_zonas_criticas`, `v_antenas_problematicas`,
   `v_tipos_reportados`, `v_evolucion_diaria`, `v_alerta_predictiva`
3. Compartir -> "Cualquier persona con el enlace puede ver", para que el jurado lo abra

## Verificacion rapida

```bash
# el puente publica en Pub/Sub
curl -s -X POST "$CLASIFICADOR_URL/eventos" -H 'Content-Type: application/json' \
  -H "X-Api-Key: $CLASIFICADOR_API_KEY" \
  -d '{"filas":[{"evento_id":"prueba-1","tabla":"incidentes","zona_id":"Z-ATE"}]}'

# el clasificador responde
curl -s -X POST "$CLASIFICADOR_URL" -H 'Content-Type: application/json' \
  -H "X-Api-Key: $CLASIFICADOR_API_KEY" \
  -d '{"descripcion":"desde anoche no me entra internet ni puedo llamar","tipoDeclarado":"OTRO"}'

# llegan eventos desde AWS
bq query --use_legacy_sql=false 'SELECT tabla, COUNT(*) FROM `telecorp.eventos` GROUP BY tabla'

# que antena predice el modelo que va a caer
bq query --use_legacy_sql=false 'SELECT * FROM `telecorp.v_alerta_predictiva`'
```

## Notas

- El clasificador es publico y se protege con `X-Api-Key`, no con IAM. Es una decision
  consciente para la hackathon: evita gestionar tokens de GCP dentro de Lambda.
- Si Gemini falla o tarda mas de 6 s, devuelve 502 y el Lambda guarda el reporte con el
  tipo del formulario (`fuente_ia = FORMULARIO`). Nunca se pierde un reporte por la IA.
- `VERTEX_MODEL` es variable de entorno. Si `gemini-3.8-flash` no esta disponible en el
  proyecto, revisa Model Garden y redespliega con otro nombre.
