-- Días del gemelo (ADR-038): de la foto inicial a la fecha de extracción.
-- La capacidad sale de la salida media de los días hábiles de la ventana
-- estable, la misma que usa la necesidad (ADR-023). Un paro puede arrancar
-- cualquier lunes de esa ventana que deje cuatro semanas para recuperarse
-- antes del fin de la base.
with v as (
    select apertura, corte, inicio_estable, fin_base
    from {{ ref('int_calendario_necesidad') }}
)

select
    cast(d.fecha as date)                                               as fecha,
    isodow(d.fecha) <= 5                                                as habil,
    d.fecha between v.inicio_estable and v.fin_base                     as estable,
    isodow(d.fecha) = 1
        and d.fecha between v.inicio_estable and v.fin_base - 28        as inicio_paro
from v, generate_series(v.apertura, v.corte, interval 1 day) as d(fecha)
