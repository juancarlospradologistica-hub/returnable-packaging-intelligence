-- Déficit y sobrante de cada material en el horizonte del plan (ADR-025).
-- deficit_pico: lo más que llega a faltar en una semana; es lo que hay que
-- conseguir para cubrir todo el horizonte. sobrante: lo que sobra en la peor
-- semana; es lo que la planta puede prestar sin quedarse corta en ninguna.
with semanal as (
    select * from {{ ref('int_flota_proyectada') }}
)

select
    s.planta,
    p.pais,
    s.material,
    s.tipo_material,
    greatest(max(s.necesidad - s.flota_proyectada), 0)                  as deficit_pico,
    greatest(min(s.flota_proyectada - s.necesidad), 0)                  as sobrante,
    max(s.ciclo_dias)                                                   as ciclo_dias
from semanal s
join {{ ref('plantas') }} p on p.planta = s.planta
group by s.planta, p.pais, s.material, s.tipo_material
