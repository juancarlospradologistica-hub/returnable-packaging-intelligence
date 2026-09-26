-- Mismo concepto, misma cifra: la pérdida del mart es la suma de los 702
-- valorizados en staging, en contenedores y en USD. La tolerancia en USD
-- es un centavo por fila del mart, por el redondeo de perdida_usd.
with mart as (
    select sum(unidades_perdidas) as unidades, sum(perdida_usd) as usd
    from {{ ref('mart_perdidas_usd') }}
),

origen as (
    select sum(abs(cantidad)) as unidades, sum(abs(cantidad) * costo_usd) as usd
    from {{ ref('stg_mb51') }}
    where mov_type = '702'
)

select *
from mart, origen
where mart.unidades <> origen.unidades
   or abs(mart.usd - origen.usd) > 0.01 * (select count(*) from {{ ref('mart_perdidas_usd') }})
