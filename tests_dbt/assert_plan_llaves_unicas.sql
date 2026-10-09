-- Una fila por parte en partes e instrucción, y por parte y semana en el plan.
-- Una instrucción repetida duplica la necesidad de la parte.
select 'stg_partes' as tabla, planta, parte, null as semana, count(*) as filas
from {{ ref('stg_partes') }}
group by planta, parte
having count(*) > 1

union all

select 'stg_instruccion_empaque', planta, parte, null, count(*)
from {{ ref('stg_instruccion_empaque') }}
group by planta, parte
having count(*) > 1

union all

select 'stg_plan_produccion', planta, parte, semana, count(*)
from {{ ref('stg_plan_produccion') }}
group by planta, parte, semana
having count(*) > 1
