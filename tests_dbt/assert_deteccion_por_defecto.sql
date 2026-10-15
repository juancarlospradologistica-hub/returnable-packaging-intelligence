-- Con cada defecto solo, la regla de su defecto reporta todo lo que la
-- bitácora registra, en los dos niveles (ADR-031, punto 3).
select distinct defecto, nivel, casos, detectados
from {{ ref('mart_impacto_defectos') }}
where detectados is distinct from casos
