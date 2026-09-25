{{ config(materialized='view') }}

-- Movimientos de la cuenta de stock especial V (planta × cliente × material).
-- delta_saldo se asigna por clase de movimiento y no por signo: 621 y 702
-- son salidas para la planta, pero 621 sube el saldo en cliente y 702 lo baja.
select
    planta,
    cliente,
    material,
    tipo_material,
    mov_type,
    fecha_contab,
    anio_contable,
    doc_material,
    posicion,
    abs(cantidad)                                       as cantidad_abs,
    case mov_type
        when '621' then abs(cantidad)
        else -abs(cantidad)
    end                                                 as delta_saldo
from {{ ref('stg_mb51') }}
where mov_type in ('621', '622', '702')
