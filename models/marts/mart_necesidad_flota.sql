-- Contenedores que necesita cada material, por planta y semana del plan, en
-- el escenario base (ADR-021, ADR-025, ADR-026). El cálculo vive en
-- int_necesidad_escenario; aquí se publica redondeado. La comparación contra la
-- flota real vive en mart_brecha_flota.
select
    planta,
    material,
    tipo_material,
    semana,
    round(d_plan, 4)                                        as d_plan,
    round(d_base, 4)                                        as d_base,
    round(ciclo_dias, 2)                                    as ciclo_dias,
    round(sigma_uso, 2)                                     as sigma_uso,
    con_historia,
    round(uso_plan, 1)                                      as uso_plan,
    round(stock_seguridad, 1)                               as stock_seguridad,
    round(stock_seguridad / nullif(d_plan, 0), 1)           as stock_seguridad_dias,
    necesidad
from {{ ref('int_necesidad_escenario') }}
where escenario = 'base'
