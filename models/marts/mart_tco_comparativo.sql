-- TCO retornable contra desechable por planta y tipo (ADR-011, punto 8).
-- La merma ya está en el costo por ciclo vía vida esperada: no se resta aparte.
-- perdida_reconocida_usd es el KPI de Fase 1 y solo se muestra como contexto.
with tco as (
    select * from {{ ref('int_tco_por_material') }}
),

costos as (
    select
        *,
        costo_unitario_usd / vida_esperada_ciclos                       as amortizacion_por_ciclo_usd,
        costo_unitario_usd / vida_esperada_ciclos + mant_por_ciclo_usd  as costo_retornable_por_ciclo_usd
    from tco
)

select
    planta,
    tipo_material,
    cast(viajes as bigint)                                              as viajes,
    cast(salidas_conciliadas as bigint)                                 as salidas_conciliadas,
    cast(faltantes as bigint)                                           as faltantes,
    tasa_merma_pct,
    vida_util_ciclos,
    round(vida_esperada_ciclos, 1)                                      as vida_esperada_ciclos,
    costo_unitario_usd,
    mant_por_ciclo_usd,
    desechable_equiv_usd,
    round(amortizacion_por_ciclo_usd, 4)                                as amortizacion_por_ciclo_usd,
    round(costo_retornable_por_ciclo_usd, 4)                            as costo_retornable_por_ciclo_usd,
    round(desechable_equiv_usd - costo_retornable_por_ciclo_usd, 4)     as ahorro_por_ciclo_usd,
    -- Ciclos para recuperar la compra con el ahorro contra el desechable.
    cast(ceil(costo_unitario_usd / (desechable_equiv_usd - mant_por_ciclo_usd)) as integer)
                                                                        as ciclos_payback,
    ceil(costo_unitario_usd / (desechable_equiv_usd - mant_por_ciclo_usd))
        <= vida_esperada_ciclos                                         as recupera_inversion,
    round(viajes * (desechable_equiv_usd - costo_retornable_por_ciclo_usd), 2)
                                                                        as ahorro_neto_usd,
    round(perdida_reconocida_usd, 2)                                    as perdida_reconocida_usd
from costos
order by tipo_material, planta