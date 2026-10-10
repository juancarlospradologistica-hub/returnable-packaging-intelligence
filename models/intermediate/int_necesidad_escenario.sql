-- Necesidad de flota por escenario, planta, material y semana (ADR-021,
-- ADR-026): d_plan × ciclo más stock de seguridad por variabilidad, con días
-- de cobertura como piso. El escenario base es el que publica
-- mart_necesidad_flota; los demás alimentan mart_sensibilidad_brecha con el
-- mismo cálculo. El ajuste de ciclo del escenario solo entra al uso del plan
-- (ley de Little: un día más en el ciclo inmoviliza un día más de demanda); la
-- σ queda la medida.
with demanda as (
    select * from {{ ref('int_demanda_plan') }}
),

z as (
    select escenario, tipo_material, z_servicio, ajuste_ciclo_dias from {{ ref('int_z_economico') }}
)

select
    z.escenario,
    d.*,
    z.z_servicio,
    z.ajuste_ciclo_dias,
    d.d_plan * (d.ciclo_dias + z.ajuste_ciclo_dias)                         as uso_plan,
    {{ stock_seguridad('d.d_plan', 'd.sigma_uso', 'd.d_base', 'z.z_servicio', 'd.dias_cobertura') }}
                                                                            as stock_seguridad,
    cast(ceil(
        {{ necesidad_flota('d.d_plan', 'd.ciclo_dias + z.ajuste_ciclo_dias', 'd.sigma_uso', 'd.d_base', 'z.z_servicio', 'd.dias_cobertura') }}
    ) as bigint)                                                            as necesidad
from demanda d
join z on z.tipo_material = d.tipo_material
