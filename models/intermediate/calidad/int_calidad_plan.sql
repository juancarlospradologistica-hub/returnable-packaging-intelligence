-- Reglas por causa sobre partes, instrucción de empaque y plan (ADR-017,
-- reglas de calidad; ADR-028, ADR-030). Sin costo posible: las unidades son
-- piezas del plan en el horizonte.
with plan as (
    select planta, parte, sum(piezas) as piezas
    from {{ ref('stg_plan_produccion') }}
    group by planta, parte
),

instruccion as (
    select * from {{ ref('stg_instruccion_empaque') }}
),

en_planta as (
    select distinct planta, material from {{ ref('stg_mb51') }}
),

sin_instruccion as (
    select
        case when i.parte is null then 'parte_sin_instruccion' else 'parte_sin_registro' end as regla,
        p.planta, p.parte, p.piezas,
        coalesce(i.material, '-')                           as material
    from plan p
    left join instruccion i on i.planta = p.planta and i.parte = p.parte
    left join {{ ref('stg_partes') }} r on r.planta = p.planta and r.parte = p.parte
    where i.parte is null or r.parte is null
),

reglas_instruccion as (
    select
        case
            when i.piezas_por_contenedor <= 0 then 'piezas_en_cero'
            when i.tipo_material = 'CARTON' then 'instruccion_a_desechable'
            when e.material is null then 'instruccion_fuera_de_planta'
        end                                                 as regla,
        i.planta, i.parte, coalesce(p.piezas, 0) as piezas, i.material
    from instruccion i
    left join plan p on p.planta = i.planta and p.parte = i.parte
    left join en_planta e on e.planta = i.planta and e.material = i.material
),

llaves as (
    select 'stg_partes' as tabla, planta, parte, count(*) as filas
    from {{ ref('stg_partes') }} group by planta, parte having count(*) > 1
    union all
    select 'stg_instruccion_empaque', planta, parte, count(*)
    from instruccion group by planta, parte having count(*) > 1
    union all
    select 'stg_plan_produccion', planta, parte, count(*)
    from {{ ref('stg_plan_produccion') }} group by planta, parte, semana having count(*) > 1
)

select
    regla, planta, material,
    cast(null as bigint)                                    as anio_contable,
    cast(null as varchar)                                   as doc_material,
    cast(null as integer)                                   as posicion,
    parte,
    cast(piezas as double)                                  as unidades,
    cast(null as double)                                    as usd_expuesto,
    piezas || ' piezas en el horizonte'                     as detalle
from sin_instruccion
union all
select
    regla, planta, material, null, null, null, parte,
    cast(piezas as double), null,
    piezas || ' piezas en el horizonte'
from reglas_instruccion
where regla is not null
union all
select
    'llave_plan_duplicada', planta, null, null, null, null, parte,
    cast(filas as double), null,
    filas || ' filas en ' || tabla
from llaves
