-- Rutas planta × cliente con merma o ciclo fuera de umbral (ADR-012).
-- Tasa de merma = faltante 702 entre salidas 621 que ya pasaron por una
-- conciliación con 120 días de antigüedad.
with parametros as (
    select
        1.0     as umbral_merma_pct,   -- rango 0.8–1.5 %
        45.0    as umbral_ciclo_dias,
        120     as dias_para_conciliar
),

movimientos as (
    select * from {{ ref('stg_mb51') }}
    where mov_type in ('621', '702')
),

ultima_conciliacion as (
    select max(fecha_contab) as fecha
    from movimientos
    where mov_type = '702'
),

merma as (
    select
        m.planta,
        m.cliente,
        cast(sum(abs(m.cantidad)) filter (where m.mov_type = '621') as bigint)
                                                                    as contenedores_salida,
        cast(sum(abs(m.cantidad)) filter (
            where m.mov_type = '621'
              and m.fecha_contab <= u.fecha - p.dias_para_conciliar
        ) as bigint)                                                as salidas_conciliadas,
        cast(coalesce(sum(abs(m.cantidad)) filter (where m.mov_type = '702'), 0) as bigint)
                                                                    as faltantes,
        coalesce(round(sum(abs(m.cantidad) * m.costo_usd)
            filter (where m.mov_type = '702'), 2), 0)               as perdida_acum_usd
    from movimientos m
    cross join ultima_conciliacion u
    cross join parametros p
    group by m.planta, m.cliente
),

ciclo as (
    select
        planta,
        cliente,
        round(sum(cantidad * dias) * 1.0 / sum(cantidad), 1)        as ciclo_promedio_dias
    from {{ ref('int_tramos_fifo') }}
    where tipo_cierre = '622'
    group by planta, cliente
),

rutas as (
    select
        m.planta,
        m.cliente,
        m.contenedores_salida,
        m.salidas_conciliadas,
        m.faltantes,
        round(m.faltantes * 100.0 / nullif(m.salidas_conciliadas, 0), 3) as tasa_merma_pct,
        c.ciclo_promedio_dias,
        m.perdida_acum_usd
    from merma m
    left join ciclo c
        on c.planta = m.planta and c.cliente = m.cliente
)

select r.*
from rutas r
cross join parametros p
where r.tasa_merma_pct > p.umbral_merma_pct
   or r.ciclo_promedio_dias > p.umbral_ciclo_dias
order by r.perdida_acum_usd desc