-- Reglas por causa sobre el maestro de materiales (ADR-028, ADR-030). Valor
-- expuesto, siempre sobre la flota de la foto inicial: un precio fuera de
-- banda o de otra familia, su diferencia contra la mediana que le toca; un
-- material sin tipo o en otra moneda, todo su valor, porque no se puede leer
-- en USD.
with maestro as (
    select * from {{ ref('stg_maestro_materiales') }}
),

foto as (
    select planta, material, sum(cantidad) as flota
    from {{ ref('stg_stock_inicial') }}
    group by planta, material
),

-- Mediana por grupo y moneda: una planta en moneda local no mueve la banda
-- de las demás y su propia unidad de precio se mide contra sus pares.
banda as (
    select grupo_articulos, moneda, median(costo_unitario_usd) as mediana
    from maestro
    group by grupo_articulos, moneda
),

banda_tipo as (
    select tipo_material, moneda, median(costo_unitario_usd) as mediana
    from maestro
    where tipo_material is not null
    group by tipo_material, moneda
),

base as (
    select
        m.*,
        b.mediana,
        t.mediana                                           as mediana_codigo,
        coalesce(f.flota, 0)                                as flota,
        g.tipo_material                                     as tipo_codigo,
        m.grupo_articulos in (select matkl from {{ ref('grupos_material') }}) as grupo_conocido
    from maestro m
    left join banda b on b.grupo_articulos = m.grupo_articulos and b.moneda = m.moneda
    left join foto f on f.planta = m.planta and f.material = m.material
    left join {{ ref('prefijos_material') }} g on starts_with(m.material, g.prefijo)
    left join banda_tipo t on t.tipo_material = g.tipo_material and t.moneda = m.moneda
),

-- Las reglas del maestro son independientes: un material en moneda local
-- también puede tener la unidad de precio mal.
reglas as (
    select 'grupo_fuera_de_catalogo' as regla, * from base where not grupo_conocido
    union all
    select 'moneda_distinta', * from base where moneda <> 'USD'
    union all
    select 'unidad_de_precio', * from base
    where unidad_precio <> 1
      and (costo_unitario_usd < mediana / {{ var('calidad_banda_precio') }}
           or costo_unitario_usd > mediana * {{ var('calidad_banda_precio') }})
    union all
    select 'grupo_contradice_codigo', * from base
    where tipo_codigo is not null and tipo_codigo is distinct from tipo_material
      and grupo_conocido
),

llave as (
    select planta, material, count(*) as filas
    from maestro
    group by planta, material
    having count(*) > 1
),

-- Lo que se mueve, está en la foto o en una instrucción sin fila en el maestro.
-- Sin maestro no hay costo: la flota de la foto se valora al precio del
-- documento, si lo trae.
usados as (
    select planta, material from {{ ref('stg_mb51') }}
    union
    select planta, material from foto
    union
    select planta, material from {{ ref('stg_instruccion_empaque') }}
),

precio_documento as (
    select planta, material, avg(costo_documento_usd) as costo
    from {{ ref('stg_mb51') }}
    where costo_documento_usd > 0
    group by planta, material
),

sin_maestro as (
    select
        u.planta, u.material,
        coalesce(f.flota, 0)                                as unidades,
        coalesce(f.flota, 0) * d.costo                      as usd
    from usados u
    left join maestro m on m.planta = u.planta and m.material = u.material
    left join foto f on f.planta = u.planta and f.material = u.material
    left join precio_documento d on d.planta = u.planta and d.material = u.material
    where m.material is null
)

select
    regla, planta, material,
    cast(null as bigint)                                    as anio_contable,
    cast(null as varchar)                                   as doc_material,
    cast(null as integer)                                   as posicion,
    cast(null as varchar)                                   as parte,
    cast(flota as double)                                   as unidades,
    case regla
        when 'unidad_de_precio' then abs(costo_unitario_usd - mediana) * flota
        when 'grupo_contradice_codigo' then abs(costo_unitario_usd - mediana_codigo) * flota
        else costo_unitario_usd * flota
    end                                                     as usd_expuesto,
    grupo_articulos || ' ' || precio || ' ' || moneda || ' por ' || unidad_precio as detalle
from reglas
union all
select
    'llave_maestro_duplicada', planta, material, null, null, null, null,
    cast(filas as double), null, filas || ' filas'
from llave
union all
select
    'material_sin_maestro', planta, material, null, null, null, null,
    cast(unidades as double), usd, 'sin fila en el maestro'
from sin_maestro
