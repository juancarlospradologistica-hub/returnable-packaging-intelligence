-- Un escenario limitado a un tipo de empaque deja al otro igual que base
-- (ADR-026). KLT y Rack no comparten material ni préstamo: si el otro tipo se
-- mueve, el filtro de tipo_material se perdió en algún join.
with sens as (
    select * from {{ ref('mart_sensibilidad_brecha') }}
),

limitados as (
    select escenario, tipo_material
    from {{ ref('escenarios_brecha') }}
    where tipo_material is not null
)

select s.escenario, s.tipo_material, s.usd_brecha, b.usd_brecha as usd_brecha_base
from sens s
join limitados l on l.escenario = s.escenario and l.tipo_material <> s.tipo_material
join sens b on b.escenario = 'base' and b.tipo_material = s.tipo_material
where s.z_servicio <> b.z_servicio
   or s.necesidad_semana_1 <> b.necesidad_semana_1
   or abs(s.usd_brecha - b.usd_brecha) > 0.01
   or abs(s.usd_capital_ocioso - b.usd_capital_ocioso) > 0.01
