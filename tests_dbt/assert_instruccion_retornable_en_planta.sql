-- La instrucción apunta a un retornable que la planta mueve (ADR-017, reglas de
-- calidad). Un cartón no tiene flota y un material sin movimientos en la planta
-- no tiene flota contra la cual medir la necesidad.
with en_planta as (
    select distinct planta, material from {{ ref('stg_mb51') }}
)

select i.*
from {{ ref('stg_instruccion_empaque') }} i
left join en_planta e
    on e.planta = i.planta and e.material = i.material
where i.tipo_material is distinct from 'KLT' and i.tipo_material is distinct from 'RACK'
   or e.material is null
