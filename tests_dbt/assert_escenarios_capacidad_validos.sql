-- Cada fila de escenarios_capacidad da la capacidad de una sola forma
-- (utilización o contenedores por día, o ninguna para sin límite), una
-- utilización entre 0 y 1, y no se repite por escenario, estación, tipo y
-- planta: si se repitiera, la capacidad dependería del orden del seed.
select escenario, estacion, tipo_material, planta, 'fila inválida' as falla
from {{ ref('escenarios_capacidad') }}
where (utilizacion is not null and contenedores_dia is not null)
   or utilizacion <= 0 or utilizacion > 1
   or contenedores_dia <= 0
   or paro_dias < 0

union all
select escenario, estacion, tipo_material, planta, 'fila repetida'
from {{ ref('escenarios_capacidad') }}
group by all
having count(*) > 1
