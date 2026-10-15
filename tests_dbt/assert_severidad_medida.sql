-- La severidad del seed es la que mide el arnés (ADR-031, punto 6): bloquea si
-- en algún nivel el defecto rompe una identidad, tumba el pipeline o mueve una
-- cifra publicada más que la materialidad; alerta en lo demás.
with medida as (
    select
        defecto,
        any_value(regla)                                    as regla,
        any_value(severidad)                                as severidad,
        case when bool_or(supera_materialidad) then 'bloquea' else 'alerta' end
                                                            as severidad_medida
    from {{ ref('mart_impacto_defectos') }}
    where tipo in ('cifra', 'identidad', 'error')
    group by defecto
)

select *
from medida
where severidad is distinct from severidad_medida
