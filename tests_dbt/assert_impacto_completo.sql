-- La medición versionada trae el limpio y cada defecto del seed en los dos
-- niveles, con todas las cifras que mide el arnés y nada fuera de ellas
-- (ADR-031, punto 7). Un CSV a medias no publica.
with esperado as (
    select r.defecto, n.nivel, c.cifra
    from {{ ref('reglas_calidad') }} r
    cross join (values ('tasa'), ('techo')) as n(nivel)
    cross join {{ ref('cifras') }} c
    where r.defecto is not null and c.medida_en_arnes

    union all

    select null, 'limpio', cifra
    from {{ ref('cifras') }}
    where medida_en_arnes
),

medido as (
    select defecto, nivel, medida as cifra
    from {{ ref('stg_impacto_defectos') }}
    where tipo = 'cifra'
)

select coalesce(e.defecto, m.defecto) as defecto,
       coalesce(e.nivel, m.nivel) as nivel,
       coalesce(e.cifra, m.cifra) as cifra,
       case when m.cifra is null then 'falta' else 'sobra' end as problema
from esperado e
full join medido m
    on e.defecto is not distinct from m.defecto
   and e.nivel = m.nivel
   and e.cifra = m.cifra
where e.cifra is null or m.cifra is null
