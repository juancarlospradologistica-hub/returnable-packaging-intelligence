-- Todas las violaciones de las reglas de calidad con su severidad y la cifra
-- que afectan (ADR-028, punto 7). La severidad sale del seed reglas_calidad al
-- correr: los tests calidad_sin_violaciones filtran por ella.
with violaciones as (
    select * from {{ ref('int_calidad_mb51') }}
    union all select * from {{ ref('int_calidad_stock_inicial') }}
    union all select * from {{ ref('int_calidad_plan') }}
    union all select * from {{ ref('int_calidad_maestro') }}
    union all
    select
        'error_de_schema', null, null, null, null, null, null,
        1.0, null,
        tabla || '.' || coalesce(columna, '-') || ' ' || "check" || ': ' || coalesce(valor, 'nulo')
            || coalesce(' (fila ' || fila || ')', '')
    from {{ source('raw', 'raw_errores_schema') }}
)

select
    v.regla,
    r.defecto,
    r.objeto,
    r.unidad,
    r.severidad,
    r.cifra_afectada,
    v.planta,
    v.material,
    v.anio_contable,
    v.doc_material,
    v.posicion,
    v.parte,
    v.unidades,
    v.usd_expuesto,
    v.detalle
from violaciones v
left join {{ ref('reglas_calidad') }} r on r.regla = v.regla
