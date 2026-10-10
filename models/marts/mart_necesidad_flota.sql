-- Contenedores que necesita cada material, por planta y semana del plan
-- (ADR-021). d_plan sale del plan en piezas entre piezas por contenedor; el
-- ciclo y la variabilidad, del stock en uso histórico. La comparación contra
-- la flota real vive en el mart de brecha (3b.3), no aquí.
with plan as (
    select
        p.planta,
        i.material,
        i.tipo_material,
        p.semana,
        sum(p.piezas * 1.0 / i.piezas_por_contenedor) / 7  as d_plan
    from {{ ref('stg_plan_produccion') }} p
    join {{ ref('stg_instruccion_empaque') }} i
        on i.planta = p.planta and i.parte = p.parte
    group by p.planta, i.material, i.tipo_material, p.semana
),

historia as (
    select * from {{ ref('int_variabilidad_uso') }} where ventana = 'necesidad'
),

-- Un material sin historia propia toma el ciclo de su planta y tipo.
ciclo_planta as (
    select distinct planta, tipo_material, ciclo_dias from historia
),

-- z económica por tipo (ADR-025) y piso de cobertura del seed.
parametros as (
    select k.tipo_material, k.dias_cobertura, z.z_servicio
    from {{ ref('parametros_flota') }} k
    join {{ ref('int_z_economico') }} z using (tipo_material)
),

calculo as (
    select
        p.planta,
        p.material,
        p.tipo_material,
        p.semana,
        p.d_plan,
        h.d_base,
        coalesce(h.ciclo_dias, c.ciclo_dias)                as ciclo_dias,
        h.sigma_uso,
        k.z_servicio,
        k.dias_cobertura,
        coalesce(h.d_base, 0) > 0 and h.sigma_uso is not null  as con_historia
    from plan p
    left join historia h
        on h.planta = p.planta and h.material = p.material
    left join ciclo_planta c
        on c.planta = p.planta and c.tipo_material = p.tipo_material
    join parametros k
        on k.tipo_material = p.tipo_material
)

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
    round(d_plan * ciclo_dias, 1)                           as uso_plan,
    round({{ stock_seguridad('d_plan', 'sigma_uso', 'd_base', 'z_servicio', 'dias_cobertura') }}, 1)
                                                            as stock_seguridad,
    round(
        {{ stock_seguridad('d_plan', 'sigma_uso', 'd_base', 'z_servicio', 'dias_cobertura') }}
        / nullif(d_plan, 0), 1
    )                                                       as stock_seguridad_dias,
    cast(ceil(
        {{ necesidad_flota('d_plan', 'ciclo_dias', 'sigma_uso', 'd_base', 'z_servicio', 'dias_cobertura') }}
    ) as bigint)                                            as necesidad
from calculo
