with ciclo as (
    select * from {{ ref('int_ciclo_retorno') }}
),

perdidas as (
    select
        planta,
        material,
        material_desc,
        date_trunc('month', fecha_salida)       as mes,
        count(*)                                as salidas,
        count(*) filter (where es_merma)        as unidades_perdidas,
        round(
            count(*) filter (where es_merma) * 100.0 / count(*), 2
        )                                       as tasa_merma_pct,
        max(costo_usd)                          as costo_unitario_usd,
        round(
            sum(costo_usd) filter (where es_merma), 2
        )                                       as perdida_usd
    from ciclo
    group by planta, material, material_desc,
             date_trunc('month', fecha_salida)
)

select * from perdidas
where unidades_perdidas > 0
order by perdida_usd desc