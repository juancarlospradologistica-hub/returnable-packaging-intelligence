-- Lo que la necesidad de flota toma del plan y de la historia, sin redondear,
-- por planta, material y semana del plan (ADR-021, ADR-026). d_plan sale del
-- plan en piezas entre piezas por contenedor; el ciclo y la variabilidad, del
-- stock en uso histórico. Un material sin historia propia toma el ciclo de su
-- planta y tipo.
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

ciclo_planta as (
    select distinct planta, tipo_material, ciclo_dias from historia
)

select
    p.planta,
    p.material,
    p.tipo_material,
    p.semana,
    p.d_plan,
    h.d_base,
    coalesce(h.ciclo_dias, c.ciclo_dias)                    as ciclo_dias,
    h.sigma_uso,
    k.dias_cobertura,
    coalesce(h.d_base, 0) > 0 and h.sigma_uso is not null   as con_historia
from plan p
left join historia h
    on h.planta = p.planta and h.material = p.material
left join ciclo_planta c
    on c.planta = p.planta and c.tipo_material = p.tipo_material
join {{ ref('parametros_flota') }} k
    on k.tipo_material = p.tipo_material
