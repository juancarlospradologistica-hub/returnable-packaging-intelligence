-- La serie diaria es la misma corrida que el resumen (ADR-038): el desechable
-- de los días suma el del escenario y la cola llega al mismo máximo. Si la
-- serie tomara otro inicio de paro, el dashboard dibujaría un caso y el mart
-- publicaría otro.
with dia as (
    select escenario, planta, tipo_material,
        sum(faltante)           as faltante,
        max(cola_lavado)        as cola_lavado_max,
        max(cola_reparacion)    as cola_reparacion_max
    from {{ ref('int_sim_diario') }}
    group by escenario, planta, tipo_material
)

select p.escenario, p.planta, p.tipo_material
from {{ ref('int_sim_peor_inicio') }} p
full join dia d using (escenario, planta, tipo_material)
where d.faltante is null or p.faltante is null
   or abs(p.faltante - d.faltante) > 1e-6
   or abs(p.cola_lavado_max - d.cola_lavado_max) > 1e-6
   or abs(p.cola_reparacion_max - d.cola_reparacion_max) > 1e-6
