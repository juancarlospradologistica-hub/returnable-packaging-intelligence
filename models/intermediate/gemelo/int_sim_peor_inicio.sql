-- Peor inicio de paro por escenario, planta y tipo de empaque (ADR-038, punto
-- 8): el que más contenedores manda a desechable; empate, el que deja más
-- flota faltante, y luego el más temprano. Un escenario sin paro tiene una
-- sola fila con inicio nulo.
select *
from {{ ref('int_sim_planta') }}
qualify row_number() over (
    partition by escenario, planta, tipo_material
    order by faltante desc, flota_falta desc, inicio_paro nulls first
) = 1
