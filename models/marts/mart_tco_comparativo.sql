with tco as (
    select * from {{ ref('int_tco_por_material') }}
),

perdidas as (
    select
        planta,
        material,
        sum(unidades_perdidas) as unidades_perdidas_total,
        sum(perdida_usd)       as perdida_acum_usd
    from {{ ref('mart_perdidas_usd') }}
    group by planta, material
),

joined as (
    select
        t.planta,
        t.tipo_material,
        t.costo_unitario_usd,
        t.vida_util_ciclos,
        t.mant_por_ciclo_usd,
        t.desechable_equiv_usd,
        t.amortizacion_por_ciclo_usd,
        t.costo_retornable_por_ciclo_usd,
        t.ahorro_por_ciclo_vs_desechable_usd,
        t.ciclos_payback,
        t.ciclos_observados,
        t.ciclo_promedio_dias,
        coalesce(p.unidades_perdidas_total, 0) as unidades_perdidas,
        coalesce(p.perdida_acum_usd, 0)        as perdida_acum_usd
    from tco t
    left join perdidas p
        on t.planta = p.planta and t.material = p.material
),

agregado as (
    select
        planta,
        tipo_material,
        max(costo_unitario_usd)                 as costo_unitario_usd,
        max(vida_util_ciclos)                   as vida_util_ciclos,
        max(mant_por_ciclo_usd)                 as mant_por_ciclo_usd,
        max(desechable_equiv_usd)               as desechable_equiv_usd,
        max(amortizacion_por_ciclo_usd)         as amortizacion_por_ciclo_usd,
        max(costo_retornable_por_ciclo_usd)     as costo_retornable_por_ciclo_usd,
        max(ahorro_por_ciclo_vs_desechable_usd) as ahorro_por_ciclo_usd,
        max(ciclos_payback)                     as ciclos_payback,
        sum(ciclos_observados)                  as ciclos_totales_observados,
        round(avg(ciclo_promedio_dias), 1)      as ciclo_promedio_dias,
        sum(unidades_perdidas)                  as unidades_perdidas,
        round(sum(perdida_acum_usd), 2)         as perdida_acum_usd,
        round(
            sum(ciclos_observados)
            * max(ahorro_por_ciclo_vs_desechable_usd),
            2
        )                                       as ahorro_total_vs_desechable_usd,
        round(
            sum(ciclos_observados)
            * max(ahorro_por_ciclo_vs_desechable_usd)
            - sum(perdida_acum_usd),
            2
        )                                       as ahorro_neto_usd
    from joined
    group by planta, tipo_material
)

select *
from agregado
where tipo_material != 'OTRO'
order by tipo_material, planta