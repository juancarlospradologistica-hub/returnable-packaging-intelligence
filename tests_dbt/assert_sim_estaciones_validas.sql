-- Cada estación del gemelo (ADR-038): lo listo por día es la traza de
-- int_sim_lotes, nada sale antes de estar listo y lo liberado no pasa de la
-- capacidad del día: cero en sábado y domingo, que se calculan aquí de la
-- fecha, y en los días de paro.
with diario as (
    select * from {{ ref('int_sim_diario') }}
),

lotes as (
    select planta, tipo_material, fecha,
        sum(cantidad) filter (where estacion = 'lavado')       as lavado,
        sum(cantidad) filter (where estacion = 'reparacion')   as reparacion
    from {{ ref('int_sim_lotes') }}
    group by all
),

habiles as (
    select fecha, habil,
        sum(habil::int) over (order by fecha)                  as n_habil
    from {{ ref('int_sim_calendario') }}
),

capacidad as (
    select
        p.escenario, p.planta, p.tipo_material, h.fecha,
        case when isodow(h.fecha) > 5 then 0 else p.capacidad_lavado end       as cap_lavado,
        case when isodow(h.fecha) > 5 then 0 else p.capacidad_reparacion end   as cap_reparacion,
        p.paro_dias > 0
            and h.habil
            and h.fecha >= p.inicio_paro
            and h.n_habil - i.n_habil < p.paro_dias                       as en_paro
    from {{ ref('int_sim_peor_inicio') }} p
    cross join habiles h
    left join habiles i on i.fecha = p.inicio_paro
),

acumulado as (
    select *,
        sum(listo_lavado) over w        as listo_lav_acum,
        sum(liberado_lavado) over w     as lib_lav_acum,
        sum(listo_reparacion) over w    as listo_rep_acum,
        sum(liberado_reparacion) over w as lib_rep_acum
    from diario
    window w as (partition by escenario, planta, tipo_material order by fecha)
)

select 'listo distinto a la traza' as falla, d.escenario, d.planta, d.tipo_material, d.fecha
from diario d
left join lotes l using (planta, tipo_material, fecha)
where d.listo_lavado <> coalesce(l.lavado, 0) or d.listo_reparacion <> coalesce(l.reparacion, 0)

union all
select 'sale antes de estar listo', escenario, planta, tipo_material, fecha
from acumulado
where lib_lav_acum > listo_lav_acum + 1e-6 or lib_rep_acum > listo_rep_acum + 1e-6

union all
select 'pasa la capacidad', d.escenario, d.planta, d.tipo_material, d.fecha
from diario d
join capacidad c using (escenario, planta, tipo_material, fecha)
where d.liberado_lavado > coalesce(case when c.en_paro then 0 else c.cap_lavado end, 'inf'::double) + 1e-6
   or d.liberado_reparacion > coalesce(c.cap_reparacion, 'inf'::double) + 1e-6
