#!/usr/bin/env bash
# Aprovisiona TODO el lado Google Cloud de Red TeleCorp.
# Ejecutar en Google Cloud Shell (ya trae gcloud y bq, no hay nada que instalar):
#   bash gcp/provisionar.sh
set -euo pipefail

PROYECTO="${GCP_PROJECT_ID:-$(gcloud config get-value project 2>/dev/null)}"
REGION="${REGION:-us-central1}"
DATASET="telecorp"
TOPIC="telecorp-eventos"
SUSCRIPCION="telecorp-eventos-bq"
SA_AWS="telecorp-aws"
SA_RUN="telecorp-clasificador"
SERVICIO="clasificador-reporte"
API_KEY="${API_KEY:-$(openssl rand -hex 16)}"
RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ -z "$PROYECTO" ]; then echo "Define GCP_PROJECT_ID o corre: gcloud config set project TU_PROYECTO"; exit 1; fi
gcloud config set project "$PROYECTO" >/dev/null
NUMERO="$(gcloud projects describe "$PROYECTO" --format='value(projectNumber)')"
echo "==> Proyecto $PROYECTO (numero $NUMERO), region $REGION"

echo "==> 1/8 Habilitando APIs (tarda ~1 min)"
gcloud services enable pubsub.googleapis.com bigquery.googleapis.com run.googleapis.com \
  aiplatform.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com

echo "==> 2/8 Dataset y tablas de BigQuery"
bq --location=US mk --dataset --force "$PROYECTO:$DATASET"
bq mk --table --force --time_partitioning_field=ts --time_partitioning_type=DAY \
  "$PROYECTO:$DATASET.eventos" "$RAIZ/gcp/esquema_eventos.json"
bq mk --table --force --time_partitioning_field=ts --time_partitioning_type=DAY \
  "$PROYECTO:$DATASET.telemetria" "$RAIZ/gcp/esquema_telemetria.json"

echo "==> 3/8 Topic de Pub/Sub"
gcloud pubsub topics create "$TOPIC" 2>/dev/null || echo "    (ya existia)"

echo "==> 4/8 Permisos de Pub/Sub sobre BigQuery (paso que todos olvidan)"
AGENTE="service-${NUMERO}@gcp-sa-pubsub.iam.gserviceaccount.com"
gcloud projects add-iam-policy-binding "$PROYECTO" \
  --member="serviceAccount:$AGENTE" --role=roles/bigquery.dataEditor --condition=None >/dev/null
gcloud projects add-iam-policy-binding "$PROYECTO" \
  --member="serviceAccount:$AGENTE" --role=roles/bigquery.jobUser --condition=None >/dev/null

echo "==> 5/8 Suscripcion Pub/Sub -> BigQuery (sin codigo intermedio)"
gcloud pubsub subscriptions create "$SUSCRIPCION" \
  --topic="$TOPIC" \
  --bigquery-table="$PROYECTO:$DATASET.eventos" \
  --use-table-schema \
  --drop-unknown-fields 2>/dev/null || echo "    (ya existia)"

echo "==> 6/8 Cuenta de servicio que usaran los Lambda de AWS"
gcloud iam service-accounts create "$SA_AWS" --display-name="Publicador desde AWS" 2>/dev/null || true
gcloud projects add-iam-policy-binding "$PROYECTO" \
  --member="serviceAccount:${SA_AWS}@${PROYECTO}.iam.gserviceaccount.com" \
  --role=roles/pubsub.publisher --condition=None >/dev/null
if [ ! -f "$RAIZ/gcp-key.json" ]; then
  gcloud iam service-accounts keys create "$RAIZ/gcp-key.json" \
    --iam-account="${SA_AWS}@${PROYECTO}.iam.gserviceaccount.com"
  echo "    clave escrita en gcp-key.json (NO subir a GitHub)"
fi

echo "==> 7/8 Cloud Run: clasificador con Gemini"
gcloud iam service-accounts create "$SA_RUN" --display-name="Clasificador Gemini" 2>/dev/null || true
gcloud projects add-iam-policy-binding "$PROYECTO" \
  --member="serviceAccount:${SA_RUN}@${PROYECTO}.iam.gserviceaccount.com" \
  --role=roles/aiplatform.user --condition=None >/dev/null
gcloud run deploy "$SERVICIO" \
  --source="$RAIZ/gcp/clasificador" \
  --region="$REGION" \
  --service-account="${SA_RUN}@${PROYECTO}.iam.gserviceaccount.com" \
  --set-env-vars="GCP_PROJECT_ID=${PROYECTO},VERTEX_REGION=${REGION},VERTEX_MODEL=${VERTEX_MODEL:-gemini-2.5-flash},API_KEY=${API_KEY}" \
  --allow-unauthenticated \
  --min-instances=0 \
  --max-instances=5 \
  --timeout=30 \
  --quiet
URL="$(gcloud run services describe "$SERVICIO" --region="$REGION" --format='value(status.url)')"

echo "==> 8/8 Archivo de salida para AWS"
cat > "$RAIZ/gcp-salida.env" <<EOF
GCP_PROJECT_ID=$PROYECTO
PUBSUB_TOPIC=$TOPIC
CLASIFICADOR_URL=$URL
CLASIFICADOR_API_KEY=$API_KEY
EOF

echo
echo "LISTO."
echo "  Topic        : $TOPIC  ->  $PROYECTO:$DATASET.eventos"
echo "  Clasificador : $URL"
echo
echo "Prueba el clasificador:"
echo "  curl -s -X POST '$URL' -H 'Content-Type: application/json' -H 'X-Api-Key: $API_KEY' \\"
echo "    -d '{\"descripcion\":\"desde anoche no me entra internet ni puedo llamar\",\"tipoDeclarado\":\"OTRO\"}'"
echo
echo "Luego, en la maquina con credenciales de AWS (desde la raiz del repo):"
echo "  python scripts/crear-secreto.py dev"
echo "  cd api-telecorp && npx serverless deploy --stage dev"
