-- La traza de cada estación cuadra con las entradas del MB51 por destino
-- (ADR-038): lo que lavado no regresa a vacíos entra a reparación, y lo que
-- reparación no regresa a vacíos entra a scrap. Si el destino se perdiera,
-- un contenedor dañado regresaría a vacíos en el gemelo.
with lotes as (
    select planta, material, fecha,
        sum(cantidad) filter (where estacion = 'lavado' and not a_vacios)      as a_reparacion,
        sum(cantidad) filter (where estacion = 'reparacion' and not a_vacios)  as a_scrap
    from {{ ref('int_sim_lotes') }}
    group by planta, material, fecha
),

entradas as (
    select planta, material, fecha,
        sum(delta) filter (where estado = 'reparacion' and evento = 'traslado_bloqueado') as a_reparacion,
        sum(delta) filter (where estado = 'scrap' and evento = 'traslado_bloqueado')      as a_scrap
    from {{ ref('int_mov_stock') }}
    where delta > 0
    group by planta, material, fecha
)

select planta, material, fecha
from lotes l
full join entradas e using (planta, material, fecha)
where coalesce(l.a_reparacion, 0) <> coalesce(e.a_reparacion, 0)
   or coalesce(l.a_scrap, 0) <> coalesce(e.a_scrap, 0)
