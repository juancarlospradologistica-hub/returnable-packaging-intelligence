-- El cartón es desechable: sale con 601 y no participa en 621/622/702 (ADR-011).
select *
from {{ ref('stg_mb51') }}
where tipo_material = 'CARTON'
  and mov_type in ('621', '622', '702')
