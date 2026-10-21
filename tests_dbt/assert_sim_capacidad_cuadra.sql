-- La capacidad de cada estación es su salida media entre la utilización del
-- escenario (ADR-038, punto 5). La salida media se calcula aquí, con los días
-- hábiles de la ventana estable de int_calendario_necesidad, sin pasar por el
-- simulador. Solo filas generales del seed: una fila por planta o tipo daría
-- otra capacidad.
with v as (
    select inicio_estable, fin_base from {{ ref('int_calendario_necesidad') }}
),

dias as (
    select count(*) as n
    from v, generate_series(v.inicio_estable, v.fin_base, interval 1 day) d(fecha)
    where isodow(d.fecha) <= 5
),

media as (
    select l.planta, l.tipo_material, l.estacion, sum(l.cantidad) / any_value(d.n) as media
    from {{ ref('int_sim_lotes') }} l, v, dias d
    where l.fecha between v.inicio_estable and v.fin_base
    group by l.planta, l.tipo_material, l.estacion
),

esc as (
    select escenario, estacion, utilizacion
    from {{ ref('escenarios_capacidad') }}
    where planta is null and tipo_material is null and utilizacion is not null
),

sim as (
    select escenario, planta, tipo_material, 'lavado' as estacion, capacidad_lavado as capacidad
    from {{ ref('mart_sim_capacidad') }}
    union all
    select escenario, planta, tipo_material, 'reparacion', capacidad_reparacion
    from {{ ref('mart_sim_capacidad') }}
)

select s.escenario, s.planta, s.tipo_material, s.estacion, s.capacidad, m.media / e.utilizacion as esperada
from sim s
join esc e using (escenario, estacion)
join media m using (planta, tipo_material, estacion)
where abs(s.capacidad - m.media / e.utilizacion) > 1e-6
