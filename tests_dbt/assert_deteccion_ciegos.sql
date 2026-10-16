-- Los ciegos se midieron dos veces con la misma inyección: antes de escribir su
-- regla y después (ADR-034). Mismos casos en las dos, sin detección antes y
-- 100% por su regla después, en los dos niveles, y una fila del mart por corrida.
with antes as (
    select defecto, nivel, max(casos) as casos, max(detectados) as detectados
    from {{ ref('stg_ciegos_antes') }}
    where nivel <> 'limpio'
    group by defecto, nivel
),

despues as (
    select defecto, nivel, max(casos) as casos, max(detectados) as detectados
    from {{ ref('stg_impacto_defectos') }}
    where defecto in (select defecto from antes)
    group by defecto, nivel
)

select
    coalesce(a.defecto, d.defecto) as defecto,
    coalesce(a.nivel, d.nivel)     as nivel,
    'medición'                     as problema
from antes a
full join despues d on d.defecto = a.defecto and d.nivel = a.nivel
where a.casos is distinct from d.casos
   or a.detectados is not null
   or d.detectados is distinct from d.casos

union all

select defecto, nivel, 'mart'
from {{ ref('mart_deteccion_ciegos') }}
group by defecto, nivel
having count(*) <> 1

union all

select 'todas', null, 'filas del mart'
from {{ ref('mart_deteccion_ciegos') }}
having count(*) <> (select count(*) from antes)
