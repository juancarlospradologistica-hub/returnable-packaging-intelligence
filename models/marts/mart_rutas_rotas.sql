with ciclo as (
    select * from {{ ref('int_ciclo_retorno') }}
),

rutas as (
    select
        planta,
        cliente,
        count(*)                                as salidas,
        count(*) filter (where es_merma)        as mermas,
        round(
            count(*) filter (where es_merma) * 100.0 / count(*), 2
        )                                       as tasa_merma_pct,
        round(avg(dias_ciclo), 1)               as ciclo_promedio_dias,
        round(
            sum(costo_usd) filter (where es_merma), 2
        )                                       as perdida_acum_usd
    from ciclo
    group by planta, cliente
),

rotas as (
    select *
    from rutas
    where tasa_merma_pct > 5.0
       or ciclo_promedio_dias > 45.0
)

select * from rotas
order by perdida_acum_usd desc