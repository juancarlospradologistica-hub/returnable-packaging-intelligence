with ciclos as (
    select * from {{ ref('int_ciclo_retorno') }}
    where es_merma = false
      and dias_ciclo is not null
      and dias_ciclo > 0
),

tipo as (
    select
        *,
        case
            when material like 'KLT%' then 'KLT'
            when material like 'RCK%' then 'RACK'
            when material like 'CTN%' then 'CARTON'
            else 'OTRO'
        end as tipo_material
    from ciclos
),

parametros as (
    select 'KLT'    as tipo_material, 25.0  as costo_unitario_usd,
           150      as vida_util_ciclos,    0.20 as mant_por_ciclo_usd,
           4.50     as desechable_equiv_usd
    union all
    select 'RACK',  180.0, 80, 2.50, null
    union all
    select 'CARTON', 8.0,   1, 0.0,  8.0
),

tco_base as (
    select
        t.planta,
        t.material,
        t.tipo_material,
        p.costo_unitario_usd,
        p.vida_util_ciclos,
        p.mant_por_ciclo_usd,
        p.desechable_equiv_usd,
        round(p.costo_unitario_usd / p.vida_util_ciclos, 4)
            as amortizacion_por_ciclo_usd,
        round(
            (p.costo_unitario_usd / p.vida_util_ciclos) + p.mant_por_ciclo_usd,
            4
        )                                       as costo_retornable_por_ciclo_usd,
        count(*)                                as ciclos_observados,
        round(avg(t.dias_ciclo), 1)             as ciclo_promedio_dias
    from tipo t
    join parametros p on t.tipo_material = p.tipo_material
    group by
        t.planta, t.material, t.tipo_material,
        p.costo_unitario_usd, p.vida_util_ciclos,
        p.mant_por_ciclo_usd, p.desechable_equiv_usd
)

select
    *,
    case
        when desechable_equiv_usd is not null
        then round(desechable_equiv_usd - costo_retornable_por_ciclo_usd, 4)
        else null
    end as ahorro_por_ciclo_vs_desechable_usd,
    case
        when desechable_equiv_usd is not null
            and desechable_equiv_usd > mant_por_ciclo_usd
        then ceil(
            costo_unitario_usd / (desechable_equiv_usd - mant_por_ciclo_usd)
        )
        else null
    end as ciclos_payback
from tco_base
order by tipo_material, planta, material
