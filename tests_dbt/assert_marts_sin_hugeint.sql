-- depends_on: {{ ref('mart_perdidas_usd') }}
-- depends_on: {{ ref('mart_rutas_rotas') }}
-- depends_on: {{ ref('mart_rotacion_planta') }}
-- depends_on: {{ ref('mart_exceso_saldo_ruta') }}
-- depends_on: {{ ref('mart_tco_comparativo') }}
-- Los marts entregan conteos en BIGINT. Polars no maneja HUGEINT y cada
-- consumidor tendría que castear por su cuenta.
select table_name, column_name, data_type
from information_schema.columns
where table_schema = '{{ target.schema }}'
  and starts_with(table_name, 'mart_')
  and data_type = 'HUGEINT'