-- Salidas negativas, entradas positivas (ADR-011). Los traslados 311
-- llevan una posición de cada signo y se validan por documento en pytest.
select *
from {{ ref('stg_mb51') }}
where (mov_type in ('102', '261', '601', '621', '702') and cantidad >= 0)
   or (mov_type in ('101', '622') and cantidad <= 0)
