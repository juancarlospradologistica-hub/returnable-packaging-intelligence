-- Déficit y sobrante de cada material en el horizonte del plan, por escenario
-- (ADR-025, ADR-026). deficit_pico: lo más que llega a faltar en una semana;
-- es lo que hay que conseguir para cubrir todo el horizonte. sobrante: lo que
-- sobra en la peor semana; es lo que la planta puede prestar sin quedarse
-- corta en ninguna. Un material con flota y sin plan necesita cero.
with escenarios as (
    select distinct escenario from {{ ref('int_z_economico') }}
),

semanal as (
    select
        e.escenario,
        f.planta,
        f.material,
        f.tipo_material,
        f.semana,
        f.ciclo_dias,
        f.flota_proyectada,
        coalesce(n.necesidad, 0)                                            as necesidad
    from {{ ref('int_flota_proyectada') }} f
    cross join escenarios e
    left join {{ ref('int_necesidad_escenario') }} n
        on n.escenario = e.escenario
        and n.planta = f.planta
        and n.material = f.material
        and n.semana = f.semana
)

select
    s.escenario,
    s.planta,
    p.pais,
    s.material,
    s.tipo_material,
    greatest(max(s.necesidad - s.flota_proyectada), 0)                  as deficit_pico,
    greatest(min(s.flota_proyectada - s.necesidad), 0)                  as sobrante,
    max(s.ciclo_dias)                                                   as ciclo_dias
from semanal s
join {{ ref('plantas') }} p on p.planta = s.planta
group by s.escenario, s.planta, p.pais, s.material, s.tipo_material
