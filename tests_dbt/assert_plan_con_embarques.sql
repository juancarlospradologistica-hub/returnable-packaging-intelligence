-- Parte con plan cuyo empaque no salió a su cliente en la ventana base del
-- plan (ADR-017, reglas de calidad). Un plan sin historia de embarques no
-- tiene ciclo ni variabilidad medidos: o la parte es nueva y hay que tratarla
-- aparte, o el maestro apunta al cliente equivocado. La ventana es la misma
-- que da la base del plan (int_calendario_necesidad), no las semanas previas
-- al plan: entre las dos queda la semana del corte.
with embarques as (
    select distinct m.planta, m.material, m.cliente
    from {{ ref('stg_mb51') }} m
    join {{ ref('clases_movimiento') }} c on c.bwart = m.mov_type
    cross join {{ ref('int_calendario_necesidad') }} k
    where c.evento = 'salida_cliente'
      and m.fecha_contab between k.inicio_base and k.fin_base
)

select p.planta, p.parte, p.cliente, i.material
from {{ ref('stg_partes') }} p
join {{ ref('stg_instruccion_empaque') }} i
    on i.planta = p.planta and i.parte = p.parte
left join embarques e
    on e.planta = p.planta and e.material = i.material and e.cliente = p.cliente
where e.material is null
