-- Mismo concepto, misma cifra: el escenario base de mart_sensibilidad_brecha
-- es mart_brecha_flota sumado por tipo, y su necesidad de la semana 1 es la de
-- mart_necesidad_flota.
with sens as (
    select * from {{ ref('mart_sensibilidad_brecha') }} where escenario = 'base'
),

brecha as (
    select
        tipo_material,
        sum(compra)                                                         as compra,
        sum(usd_flete + usd_compra + usd_desechable)                        as usd_brecha,
        sum(usd_capital_ocioso)                                             as usd_capital_ocioso
    from {{ ref('mart_brecha_flota') }}
    group by tipo_material
),

necesidad as (
    select tipo_material, sum(necesidad) as necesidad_semana_1
    from {{ ref('mart_necesidad_flota') }}
    where semana = (select min(semana) from {{ ref('mart_necesidad_flota') }})
    group by tipo_material
)

select s.tipo_material, s.compra, b.compra, s.usd_brecha, b.usd_brecha
from sens s
join brecha b using (tipo_material)
join necesidad n using (tipo_material)
where s.compra <> b.compra
   or abs(s.usd_brecha - b.usd_brecha) > 1
   or abs(s.usd_capital_ocioso - b.usd_capital_ocioso) > 1
   or s.necesidad_semana_1 <> n.necesidad_semana_1
