-- Foto de stock al cierre del día anterior a la ventana (MB5B), con los mismos
-- nombres que stg_mb51.
select
    werks                                           as planta,
    lgort                                           as almacen,
    matnr                                           as material,
    {{ tipo_material('matnr') }}                    as tipo_material,
    kunnr                                           as cliente,
    menge                                           as cantidad,
    cast(fecha as date)                             as fecha
from {{ source('raw', 'raw_stock_inicial') }}
