-- Foto de stock al cierre del día anterior a la ventana (MB5B), con los mismos
-- nombres que stg_mb51. El tipo de empaque sale del maestro (ADR-028).
select
    s.werks                                         as planta,
    s.lgort                                         as almacen,
    s.matnr                                         as material,
    m.tipo_material,
    s.kunnr                                         as cliente,
    s.menge                                         as cantidad,
    cast(s.fecha as date)                           as fecha
from {{ source('raw', 'raw_stock_inicial') }} s
left join {{ ref('stg_maestro_materiales') }} m
    on m.planta = s.werks and m.material = s.matnr
