{{ config(materialized='view') }}

-- Cada movimiento de retornable con su efecto sobre el stock de una ubicación:
-- un almacén del ciclo o el stock especial V en cliente (estado 'cliente', sin
-- Lgort, igual que MSKU). Un 621 da dos renglones: sale de llenos y entra a
-- cliente. Estado y evento salen de los seeds; aquí no hay códigos SAP
-- (ADR-017, punto 5).
with movimientos as (
    select * from {{ ref('stg_mb51') }}
),

almacenes as (
    select * from {{ ref('almacenes') }}
),

clases as (
    select * from {{ ref('clases_movimiento') }}
),

en_almacen as (
    select
        m.planta,
        m.material,
        m.tipo_material,
        a.estado,
        -- ADR-017, punto 3, por evento: el traslado entre almacenes bloqueados
        -- y la baja siempre son bloqueado; el bloqueo entra a bloqueado y el
        -- desbloqueo sale de bloqueado. Lo demás es libre utilización.
        case
            when c.evento in ('traslado_bloqueado', 'baja')    then 'bloqueado'
            when c.evento = 'bloqueo' and m.cantidad > 0        then 'bloqueado'
            when c.evento = 'desbloqueo' and m.cantidad < 0     then 'bloqueado'
            else 'libre'
        end                                             as tipo_stock,
        c.evento,
        m.fecha_contab                                  as fecha,
        m.cantidad                                      as delta
    from movimientos m
    join almacenes a on a.lgort = m.almacen
    join clases c on c.bwart = m.mov_type
    where a.estado <> 'fuera_ciclo'
),

-- Mismo signo que int_mov_cuenta: la salida a cliente sube el saldo V, la
-- recogida y el faltante lo bajan.
en_cliente as (
    select
        m.planta,
        m.material,
        m.tipo_material,
        'cliente'                                       as estado,
        'libre'                                         as tipo_stock,
        c.evento,
        m.fecha_contab                                  as fecha,
        case c.evento
            when 'salida_cliente' then abs(m.cantidad)
            else -abs(m.cantidad)
        end                                             as delta
    from movimientos m
    join clases c on c.bwart = m.mov_type
    where c.evento in ('salida_cliente', 'recogida_cliente', 'faltante_cliente')
),

-- La foto inicial entra como un movimiento más en su fecha: el saldo de cada
-- ubicación es una sola suma desde ahí. MB5B no trae tipo de stock; reparación
-- y scrap viven en bloqueado (ADR-017, punto 1).
apertura as (
    select
        s.planta,
        s.material,
        s.tipo_material,
        a.estado,
        case
            when a.estado in ('reparacion', 'scrap') then 'bloqueado'
            else 'libre'
        end                                             as tipo_stock,
        'apertura'                                      as evento,
        s.fecha,
        s.cantidad                                      as delta
    from {{ ref('stg_stock_inicial') }} s
    join almacenes a on a.lgort = s.almacen
)

select * from en_almacen
union all
select * from en_cliente
union all
select * from apertura
