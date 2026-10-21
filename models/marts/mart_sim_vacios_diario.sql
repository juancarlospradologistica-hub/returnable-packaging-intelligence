-- Vacíos por día en cada escenario del gemelo contra la traza del MB51
-- (ADR-038), por planta y tipo de empaque, con la cola de cada estación. Un
-- escenario con paro trae su peor inicio. Es lo que dibuja la pestaña de la
-- red en el dashboard.
select
    escenario,
    planta,
    tipo_material,
    fecha,
    cast(round(vacios_replay) as bigint)                as vacios_replay,
    cast(round(vacios) as bigint)                       as vacios,
    cast(round(faltante) as bigint)                     as faltante,
    cast(round(listo_lavado) as bigint)                 as listo_lavado,
    round(liberado_lavado, 2)                           as liberado_lavado,
    cast(round(cola_lavado) as bigint)                  as cola_lavado,
    cast(round(listo_reparacion) as bigint)             as listo_reparacion,
    round(liberado_reparacion, 2)                       as liberado_reparacion,
    cast(round(cola_reparacion) as bigint)              as cola_reparacion
from {{ ref('int_sim_diario') }}
