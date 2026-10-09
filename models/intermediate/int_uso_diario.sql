-- Stock en uso por planta y material al cierre de cada día natural: todo lo
-- que no está en vacíos (línea, llenos, cliente, sucios, reparación y scrap).
-- Es la flota que el ciclo tiene ocupada; vacíos es lo que queda para cubrir
-- la variación. Calendario completo y no solo días con cambio: la ley de Little
-- y la desviación se promedian por día natural, y un domingo cuenta igual que
-- un lunes (ADR-021).
with diario as (
    select planta, material, tipo_material, fecha, sum(delta) as delta
    from {{ ref('int_stock_diario') }}
    where estado <> 'vacios'
    group by planta, material, tipo_material, fecha
),

salidas as (
    select planta, material, fecha, sum(delta) as salidas
    from {{ ref('int_mov_stock') }}
    where estado = 'cliente' and evento = 'salida_cliente'
    group by planta, material, fecha
),

calendario as (
    select cast(f as date) as fecha
    from {{ ref('int_calendario_necesidad') }} c,
        unnest(generate_series(c.apertura, c.corte, interval 1 day)) as t(f)
),

materiales as (
    select distinct planta, material, tipo_material from {{ ref('int_stock_diario') }}
)

select
    m.planta,
    m.material,
    m.tipo_material,
    k.fecha,
    cast(sum(coalesce(d.delta, 0)) over (
        partition by m.planta, m.material
        order by k.fecha
        rows between unbounded preceding and current row
    ) as bigint)                                        as en_uso,
    cast(coalesce(s.salidas, 0) as bigint)              as salidas
from materiales m
cross join calendario k
left join diario d
    on d.planta = m.planta and d.material = m.material and d.fecha = k.fecha
left join salidas s
    on s.planta = m.planta and s.material = m.material and s.fecha = k.fecha
