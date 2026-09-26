-- Pérdida reconocida en conciliación (702 con stock especial V), por mes de
-- reconocimiento: es el mes en que contabilidad ve el faltante (ADR-012).
-- La tasa de merma vive en mart_rutas_rotas: aquí no hay denominador limpio.
select
    planta,
    material,
    material_desc,
    tipo_material,
    cast(date_trunc('month', fecha_contab) as date)     as mes,
    cast(sum(abs(cantidad)) as bigint)                  as unidades_perdidas,
    max(costo_usd)                                      as costo_unitario_usd,
    round(sum(abs(cantidad) * costo_usd), 2)            as perdida_usd
from {{ ref('stg_mb51') }}
where mov_type = '702'
group by planta, material, material_desc, tipo_material, date_trunc('month', fecha_contab)