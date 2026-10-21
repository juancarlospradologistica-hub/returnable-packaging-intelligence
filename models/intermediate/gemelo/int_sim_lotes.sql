-- Lo que salió de cada estación por día según el MB51: la traza del gemelo
-- (ADR-038). Lavado de empaques = salidas de sucios; reparación = salidas de
-- reparación. Estado y evento salen de los seeds, no de códigos SAP. El
-- destino es la posición que entra en el mismo documento: solo lo que regresa
-- a vacíos mueve la flota disponible.
with mov as (
    select
        m.planta,
        m.anio_contable,
        m.doc_material,
        m.material,
        m.tipo_material,
        m.fecha_contab,
        m.cantidad,
        a.estado
    from {{ ref('stg_mb51') }} m
    join {{ ref('almacenes') }} a on a.lgort = m.almacen
    join {{ ref('clases_movimiento') }} c on c.bwart = m.mov_type
    where c.evento in ('traslado', 'traslado_bloqueado')
),

sale as (
    select * from mov
    where cantidad < 0 and estado in ('sucios', 'reparacion')
),

entra as (
    select planta, anio_contable, doc_material, material, estado as destino
    from mov
    where cantidad > 0
)

select
    s.planta,
    s.tipo_material,
    s.material,
    case s.estado when 'sucios' then 'lavado' else 'reparacion' end     as estacion,
    coalesce(e.destino = 'vacios', false)                               as a_vacios,
    s.fecha_contab                                                      as fecha,
    cast(-sum(s.cantidad) as bigint)                                    as cantidad
from sale s
left join entra e using (planta, anio_contable, doc_material, material)
group by all
