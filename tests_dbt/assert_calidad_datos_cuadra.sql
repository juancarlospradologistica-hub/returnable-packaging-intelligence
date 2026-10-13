{{ config(tags=['calidad']) }}
-- El tablero cuenta lo mismo que int_calidad_violaciones, regla por regla, en
-- violaciones, unidades y valor expuesto (ADR-031, punto 2).
with detalle as (
    select regla, count(*) as violaciones, sum(unidades) as unidades,
           coalesce(sum(usd_expuesto), 0) as usd
    from {{ ref('int_calidad_violaciones') }}
    group by regla
),

tablero as (
    select regla, sum(violaciones) as violaciones, sum(unidades) as unidades,
           coalesce(sum(usd_expuesto), 0) as usd
    from {{ ref('mart_calidad_datos') }}
    group by regla
)

select *
from detalle d
full join tablero t using (regla)
where d.violaciones is distinct from t.violaciones
   or abs(d.unidades - t.unidades) > 0.001
   or abs(d.usd - t.usd) > 0.01
   or d.regla is null or t.regla is null
