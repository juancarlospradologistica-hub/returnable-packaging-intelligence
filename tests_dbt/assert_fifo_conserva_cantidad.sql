-- Por cuenta, los tramos reparten exactamente lo que hay en los movimientos:
-- salidas 621 = total de tramos; 622 y 702 = tramos cerrados por cada uno.
with movimientos as (
    select
        planta,
        cliente,
        material,
        coalesce(sum(cantidad_abs) filter (where mov_type = '621'), 0) as salidas,
        coalesce(sum(cantidad_abs) filter (where mov_type = '622'), 0) as recogidas,
        coalesce(sum(cantidad_abs) filter (where mov_type = '702'), 0) as faltantes
    from {{ ref('int_mov_cuenta') }}
    group by planta, cliente, material
),

tramos as (
    select
        planta,
        cliente,
        material,
        sum(cantidad)                                               as salidas,
        coalesce(sum(cantidad) filter (where tipo_cierre = '622'), 0) as recogidas,
        coalesce(sum(cantidad) filter (where tipo_cierre = '702'), 0) as faltantes
    from {{ ref('int_tramos_fifo') }}
    group by planta, cliente, material
)

select *
from movimientos m
full outer join tramos t
    using (planta, cliente, material)
where coalesce(m.salidas, 0)   <> coalesce(t.salidas, 0)
   or coalesce(m.recogidas, 0) <> coalesce(t.recogidas, 0)
   or coalesce(m.faltantes, 0) <> coalesce(t.faltantes, 0)
