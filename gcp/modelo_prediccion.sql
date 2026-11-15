-- IA sobre la analitica: predecir la degradacion de una antena ANTES de que caiga.
-- Ejecutar:  bq query --use_legacy_sql=false < gcp/modelo_prediccion.sql
-- Entrena un modelo por antena; con 12 antenas tarda unos 3-5 minutos.

CREATE OR REPLACE MODEL `telecorp.modelo_trafico`
OPTIONS (
  model_type            = 'ARIMA_PLUS',
  time_series_timestamp_col = 'ts',
  time_series_data_col  = 'gb_min',
  time_series_id_col    = 'antena_id',
  data_frequency        = 'HOURLY',
  horizon               = 24,
  auto_arima            = TRUE
) AS
SELECT antena_id, ts, gb_min
FROM `telecorp.telemetria`;

-- Pronostico de las proximas 24 horas por antena
CREATE OR REPLACE VIEW `telecorp.v_pronostico` AS
SELECT
  antena_id,
  forecast_timestamp                AS momento,
  ROUND(forecast_value, 2)          AS gb_min_previsto,
  ROUND(prediction_interval_lower_bound, 2) AS limite_inferior,
  ROUND(prediction_interval_upper_bound, 2) AS limite_superior
FROM ML.FORECAST(MODEL `telecorp.modelo_trafico`,
                 STRUCT(24 AS horizon, 0.90 AS confidence_level));

-- Alerta anticipada: antenas que el modelo ve cayendo bajo el umbral de 60 GB/min.
-- Esta es la consulta que reduce el tiempo de deteccion: avisa antes del primer reporte.
CREATE OR REPLACE VIEW `telecorp.v_alerta_predictiva` AS
SELECT
  antena_id,
  MIN(momento)                      AS primera_hora_en_riesgo,
  ROUND(MIN(gb_min_previsto), 2)    AS minimo_previsto,
  COUNT(*)                          AS horas_en_riesgo
FROM `telecorp.v_pronostico`
WHERE limite_inferior < 60
GROUP BY antena_id
ORDER BY minimo_previsto;
