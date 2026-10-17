{{ config(materialized='view') }}

-- Movimientos de la cuenta de stock especial V (planta × cliente × material).
-- delta_saldo se asigna por clase de movimiento y no por signo: 621 y 702
-- son salidas para la planta, pero 621 sube el saldo en cliente y 702 lo baja.
--
-- La foto inicial abre la cuenta con el stock V que ya estaba en cliente
-- (en_foto). Un extracto real empieza con contenedores afuera: sin la foto,
-- la recogida de uno que salió antes de la ventana deja la cuenta en negativo
-- y el FIFO la empareja con la primera salida de la ventana (ADR-036).
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
    end                                                 as delta_saldo,
    false                                               as en_foto
from {{ ref('stg_mb51') }}
where mov_type in ('621', '622', '702')

union all

select
    planta,
    cliente,
    material,
    tipo_material,
    cast(null as varchar)                               as mov_type,
    fecha                                               as fecha_contab,
    cast(null as bigint)                                as anio_contable,
    cast(null as varchar)                               as doc_material,
    cast(null as integer)                               as posicion,
    cantidad                                            as cantidad_abs,
    cantidad                                            as delta_saldo,
    true                                                as en_foto
from {{ ref('stg_stock_inicial') }}
where cliente is not null
