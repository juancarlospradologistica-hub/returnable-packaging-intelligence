-- Probabilidad de que un contenedor que sí regresa siga en cliente a cierta
-- edad, por tipo de material (ADR-012). Se estima con los tramos FIFO cerrados
-- por 622, ponderados por cantidad. Los faltantes 702 no entran: la curva
-- describe el ciclo sano, contra el que se mide el exceso de saldo.
with cerrados as (
    select tipo_material, dias, sum(cantidad) as cantidad
    from {{ ref('int_tramos_fifo') }}
    where tipo_cierre = '622'
    group by tipo_material, dias
),

totales as (
    select tipo_material, sum(cantidad) as total, max(dias) as max_dias
    from cerrados
    group by tipo_material
),

edades as (
    select tipo_material, unnest(range(0, max_dias + 1)) as edad
    from totales
),

por_edad as (
    select e.tipo_material, e.edad, coalesce(c.cantidad, 0) as cantidad
    from edades e
    left join cerrados c
        on  c.tipo_material = e.tipo_material
        and c.dias = e.edad
)

select
    p.tipo_material,
    cast(p.edad as integer)                             as edad,
    1 - sum(p.cantidad) over (
        partition by p.tipo_material
        order by p.edad
        rows between unbounded preceding and current row
    ) / t.total                                         as prob_en_cliente
from por_edad p
join totales t on t.tipo_material = p.tipo_material
