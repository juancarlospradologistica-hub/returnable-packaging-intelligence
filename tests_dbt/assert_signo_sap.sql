-- Salidas negativas, entradas positivas (ADR-011). Los traslados 309/311/411
-- llevan una posición de cada signo y se validan por documento en pytest.
select *
from {{ ref('stg_mb51') }}
where (mov_type in ('102', '261', '502', '601', '621', '702') and cantidad >= 0)
   or (mov_type in ('101', '501', '622') and cantidad <= 0)
