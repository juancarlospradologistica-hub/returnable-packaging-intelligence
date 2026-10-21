-- La capacidad del gemelo sale de vacíos, igual que la flota (ADR-038, punto
-- 12): toda regla que declara flota declara capacidad. Si no, el bloqueo de
-- publicación dejaría pasar el gemelo con un defecto que mueve la flota.
select regla, cifra_afectada
from {{ ref('reglas_calidad') }}
where list_contains(string_split(cifra_afectada, ' '), 'flota')
  and not list_contains(string_split(cifra_afectada, ' '), 'capacidad')
