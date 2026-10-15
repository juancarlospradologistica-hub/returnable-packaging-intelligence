-- Toda cifra que un defecto mueve más que la materialidad está en cifra_afectada
-- de su regla (ADR-031, punto 7). Si no, el bloqueo de publicación la deja
-- pasar con ese defecto presente.
select defecto, regla, nivel, medida, valor_limpio, valor, delta_pct
from {{ ref('mart_impacto_defectos') }}
where tipo = 'cifra'
  and supera_materialidad
  and not declarada
