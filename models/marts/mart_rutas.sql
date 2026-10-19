-- Todas las rutas planta × cliente con salidas 621, con su tasa de merma,
-- ciclo y la marca de ruta rota (ADR-012, punto 4; ADR-015). Es el universo
-- de rutas: el "de N" de los KPIs sale de aquí.
-- Tasa de merma = faltante 702 entre salidas 621 que ya pasaron por una
-- conciliación (antigüedad en la var antiguedad_conciliacion_dias).
with parametros as (
    select
        1.0     as umbral_merma_pct,   -- rango 0.8–1.5 %
        45.0    as umbral_ciclo_dias
),

-- La tasa cuenta las salidas y faltantes que marca int_merma_conciliable; la
-- pérdida acumulada, todos los 702 (ADR-036).
merma as (
    select
        planta,
        cliente,
        cast(sum(cantidad_abs) filter (where mov_type = '621') as bigint)
                                                                    as contenedores_salida,
        cast(sum(cantidad_abs) filter (where mov_type = '621' and en_tasa) as bigint)
                                                                    as salidas_conciliadas,
        cast(coalesce(sum(cantidad_abs) filter (where mov_type = '702' and en_tasa), 0) as bigint)
                                                                    as faltantes,
        coalesce(round(sum(cantidad_abs * costo_unitario_usd)
            filter (where mov_type = '702'), 2), 0)                 as perdida_acum_usd
    from {{ ref('int_merma_conciliable') }}
    group by planta, cliente
),

ciclo as (
    select
        planta,
        cliente,
        round(sum(cantidad * dias) * 1.0 / sum(cantidad), 1)        as ciclo_promedio_dias
    from {{ ref('int_tramos_fifo') }}
    where tipo_cierre = '622' and not salida_en_foto
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

select
    r.*,
    coalesce(r.tasa_merma_pct > p.umbral_merma_pct, false)          as rota_por_merma,
    coalesce(r.ciclo_promedio_dias > p.umbral_ciclo_dias, false)    as rota_por_ciclo,
    coalesce(r.tasa_merma_pct > p.umbral_merma_pct, false)
        or coalesce(r.ciclo_promedio_dias > p.umbral_ciclo_dias, false) as ruta_rota
from rutas r
cross join parametros p
order by r.perdida_acum_usd desc
