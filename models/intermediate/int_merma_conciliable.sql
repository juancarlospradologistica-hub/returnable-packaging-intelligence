{{ config(materialized='view') }}

-- Salidas 621 y faltantes 702 con la marca de si entran a la tasa de merma
-- (ADR-012, ADR-036). Una conciliación reconoce el faltante de las salidas con
-- más de antiguedad_conciliacion_dias, así que la tasa es faltantes entre
-- salidas que ya pasaron por una conciliación.
--
-- Si la ruta abrió con stock en cliente en la foto, las primeras
-- conciliaciones de la ventana reconocen faltantes de salidas anteriores a la
-- foto, que no están en el denominador: la tasa salía 27% alta en una ventana
-- recortada. En esas rutas cuenta desde la primera conciliación cuyas salidas
-- caen enteras después de la foto. Sin stock en cliente al abrir, todo entra.
with movimientos as (
    select * from {{ ref('stg_mb51') }}
    where mov_type in ('621', '702')
),

ultima_conciliacion as (
    select max(fecha_contab) as fecha
    from movimientos
    where mov_type = '702'
),

-- Rutas que abrieron con stock V, y la fecha de la foto de su planta.
abre_con_stock as (
    select distinct f.planta, f.cliente, p.fecha as fecha_foto
    from {{ ref('stg_stock_inicial') }} f
    join (
        select planta, min(fecha) as fecha
        from {{ ref('stg_stock_inicial') }}
        group by planta
    ) p on p.planta = f.planta
    where f.cliente is not null
),

conciliaciones as (
    select
        planta,
        fecha_contab                                        as fecha,
        lag(fecha_contab) over (partition by planta order by fecha_contab) as anterior
    from (select distinct planta, fecha_contab from movimientos where mov_type = '702')
),

-- Primera conciliación cuyas salidas (las posteriores a la conciliación
-- anterior menos la antigüedad) son todas posteriores a la foto.
primera_completa as (
    select
        c.planta,
        min(c.fecha)                                        as fecha,
        arg_min(c.anterior, c.fecha)                        as anterior
    from conciliaciones c
    join (select distinct planta, fecha_foto from abre_con_stock) a on a.planta = c.planta
    where c.anterior - {{ var('antiguedad_conciliacion_dias') }} >= a.fecha_foto
    group by c.planta
)

select
    m.planta,
    m.cliente,
    m.material,
    m.tipo_material,
    m.mov_type,
    m.fecha_contab,
    abs(m.cantidad)                                         as cantidad_abs,
    m.costo_unitario_usd,
    -- Una ruta con stock al abrir y sin conciliación completa en la ventana se
    -- queda sin tasa propia.
    coalesce(case
        when m.mov_type = '702' then
            a.planta is null or m.fecha_contab >= p.fecha
        else
            m.fecha_contab <= u.fecha - {{ var('antiguedad_conciliacion_dias') }}
            and (
                a.planta is null
                or m.fecha_contab > p.anterior - {{ var('antiguedad_conciliacion_dias') }}
            )
    end, false)                                             as en_tasa
from movimientos m
cross join ultima_conciliacion u
left join abre_con_stock a
    on a.planta = m.planta and a.cliente = m.cliente
left join primera_completa p
    on p.planta = m.planta
