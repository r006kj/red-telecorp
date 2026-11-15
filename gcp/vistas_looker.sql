-- Vistas para el panel de Looker Studio.
-- Ejecutar:  bq query --use_legacy_sql=false < gcp/vistas_looker.sql
--
-- IMPORTANTE: la tabla eventos recibe una fila por CADA cambio de DynamoDB Streams,
-- asi que un mismo incidente aparece varias veces. Todo lo que cuente incidentes
-- debe partir de v_incidentes, que se queda solo con el ultimo estado de cada uno.

CREATE OR REPLACE VIEW `telecorp.v_incidentes` AS
SELECT * EXCEPT (fila)
FROM (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY entidad_id ORDER BY ts DESC) AS fila
  FROM `telecorp.eventos`
  WHERE tabla = 'incidentes'
)
WHERE fila = 1;

CREATE OR REPLACE VIEW `telecorp.v_reportes` AS
SELECT * EXCEPT (fila)
FROM (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY entidad_id ORDER BY ts DESC) AS fila
  FROM `telecorp.eventos`
  WHERE tabla = 'reportes'
)
WHERE fila = 1;

-- Que zonas presentan mayor cantidad de incidentes
CREATE OR REPLACE VIEW `telecorp.v_zonas_criticas` AS
SELECT
  zona_id,
  ANY_VALUE(zona_nombre)                              AS zona,
  ANY_VALUE(zona_tipo)                                AS tipo_zona,
  COUNT(*)                                            AS incidentes,
  COUNTIF(prioridad IN ('CRITICA', 'ALTA'))           AS incidentes_graves,
  SUM(usuarios_afectados)                             AS usuarios_afectados,
  ROUND(AVG(duracion_min), 1)                         AS duracion_promedio_min
FROM `telecorp.v_incidentes`
WHERE zona_id IS NOT NULL
GROUP BY zona_id
ORDER BY incidentes DESC;

-- Que antenas presentan problemas con mayor frecuencia (problema estructural)
CREATE OR REPLACE VIEW `telecorp.v_antenas_problematicas` AS
SELECT
  antena_id,
  ANY_VALUE(zona_nombre)                              AS zona,
  COUNT(*)                                            AS fallas,
  COUNTIF(severidad = 'INHABILITADA')                 AS veces_inhabilitada,
  COUNTIF(severidad = 'CAIDA')                        AS veces_caida,
  COUNTIF(severidad = 'SATURADA')                     AS veces_saturada,
  ROUND(AVG(duracion_min), 1)                         AS duracion_promedio_min,
  MAX(inicio)                                         AS ultima_falla
FROM `telecorp.v_incidentes`
WHERE antena_id IS NOT NULL
GROUP BY antena_id
ORDER BY fallas DESC;

-- Que tipos de inconveniente se reportan con mayor regularidad,
-- y cuanto corrige Gemini la categoria que eligio el usuario
CREATE OR REPLACE VIEW `telecorp.v_tipos_reportados` AS
SELECT
  tipo_problema                                       AS tipo_final,
  COUNT(*)                                            AS reportes,
  COUNTIF(fuente_ia = 'GEMINI')                       AS clasificados_por_ia,
  COUNTIF(fuente_ia = 'GEMINI' AND tipo_problema != tipo_declarado) AS corregidos_por_ia,
  COUNT(DISTINCT zona_id)                             AS zonas_alcanzadas
FROM `telecorp.v_reportes`
WHERE tipo_problema IS NOT NULL
GROUP BY tipo_problema
ORDER BY reportes DESC;

-- Evolucion diaria, para la serie de tiempo del panel
CREATE OR REPLACE VIEW `telecorp.v_evolucion_diaria` AS
SELECT
  DATE(ts)                                            AS dia,
  COUNTIF(tabla = 'incidentes')                       AS incidentes,
  COUNTIF(tabla = 'reportes')                         AS reportes,
  ROUND(AVG(IF(tabla = 'incidentes', duracion_min, NULL)), 1) AS duracion_promedio_min
FROM (
  SELECT * FROM `telecorp.v_incidentes`
  UNION ALL
  SELECT * FROM `telecorp.v_reportes`
)
GROUP BY dia
ORDER BY dia;
