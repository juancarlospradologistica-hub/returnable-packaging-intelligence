-- Tablero de calidad de un extracto: violaciones por regla, planta y material
-- (ADR-028, punto 1; ADR-031, punto 2). Severidad, unidad y cifras afectadas
-- vienen del seed reglas_calidad. universo_planta es lo que la regla cuenta
-- en la planta (líneas, materiales o partes): la tasa por planta es la suma
-- de violaciones entre ese universo. Con datos limpios el mart sale vacío.
with violaciones as (
    select * from {{ ref('int_calidad_violaciones') }}
),

universo as (
    select planta, 'linea' as unidad, count(*) as universo
    from {{ ref('stg_mb51') }}
    group by planta

    union all

    select planta, 'material', count(*)
    from (
        select planta, material from {{ ref('stg_maestro_materiales') }}
        union
        select distinct planta, material from {{ ref('stg_mb51') }}
    )
    group by planta

    union all

    select planta, 'parte', count(*)
    from (
        select planta, parte from {{ ref('stg_partes') }}
        union
        select planta, parte from {{ ref('stg_plan_produccion') }}
    )
    group by planta
)

select
    v.regla,
    v.defecto,
    v.objeto,
    v.unidad,
    v.severidad,
    v.cifra_afectada,
    v.planta,
    v.material,
    m.tipo_material,
    cast(count(*) as bigint)                                as violaciones,
    sum(v.unidades)                                         as unidades,
    sum(v.usd_expuesto)                                     as usd_expuesto,
    cast(any_value(u.universo) as bigint)                   as universo_planta
from violaciones v
left join {{ ref('stg_maestro_materiales') }} m
    on m.planta = v.planta and m.material = v.material
left join universo u
    on u.planta = v.planta and u.unidad = v.unidad
group by all
