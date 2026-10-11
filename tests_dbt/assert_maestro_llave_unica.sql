-- Una fila por planta y material en el maestro: un material repetido duplica
-- cada movimiento que lo cruza en staging.
select planta, material, count(*) as filas
from {{ ref('stg_maestro_materiales') }}
group by planta, material
having count(*) > 1
