-- Parte con plan cuyo empaque no salió a su cliente en las semanas base previas
-- al plan (ADR-017, reglas de calidad). Un plan sin historia de embarques no
-- tiene ciclo ni variabilidad medidos: o la parte es nueva y hay que tratarla
-- aparte, o el maestro apunta al cliente equivocado.
with inicio as (
    select min(semana) as primera from {{ ref('stg_plan_produccion') }}
),

embarques as (
    select distinct m.planta, m.material, m.cliente
    from {{ ref('stg_mb51') }} m
    join {{ ref('clases_movimiento') }} c on c.bwart = m.mov_type
    cross join inicio
    where c.evento = 'salida_cliente'
      and m.fecha_contab >= inicio.primera - 7 * {{ var('ventana_base_semanas') }}
      and m.fecha_contab < inicio.primera
)

select p.planta, p.parte, p.cliente, i.material
from {{ ref('stg_partes') }} p
join {{ ref('stg_instruccion_empaque') }} i
    on i.planta = p.planta and i.parte = p.parte
left join embarques e
    on e.planta = p.planta and e.material = i.material and e.cliente = p.cliente
where e.material is null
