with ciclo as (
    select * from {{ ref('int_ciclo_retorno') }}
),

rotacion as (
    select
        planta,
        date_trunc('month', fecha_salida)       as mes,
        count(*)                                as salidas_totales,
        count(fecha_retorno)                    as retornos_totales,
        count(*) - count(fecha_retorno)         as mermas_totales,
        round(
            (count(*) - count(fecha_retorno)) * 100.0 / count(*), 2
        )                                       as tasa_merma_pct,
        round(avg(dias_ciclo), 1)               as ciclo_promedio_dias,
        round(percentile_cont(0.5)
            within group (order by dias_ciclo), 1
        )                                       as ciclo_p50_dias,
        round(percentile_cont(0.9)
            within group (order by dias_ciclo), 1
        )                                       as ciclo_p90_dias
    from ciclo
    group by planta, date_trunc('month', fecha_salida)
)

select * from rotacion
order by planta, mes