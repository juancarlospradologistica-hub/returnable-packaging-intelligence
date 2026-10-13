-- Cada clave de cifra_afectada existe en el seed cifras (ADR-031, punto 1).
-- Una clave mal escrita dejaría la cifra sin bloqueo y nadie lo notaría.
with claves as (
    select regla, unnest(string_split(cifra_afectada, ' ')) as cifra
    from {{ ref('reglas_calidad') }}
    where cifra_afectada is not null
)

select regla, cifra
from claves
where cifra <> 'todas'
  and cifra not in (select cifra from {{ ref('cifras') }})
