-- Sin filtro de Bwart: un código fuera del contrato debe fallar el test del source,
-- no desaparecer en silencio.
-- Tipo de empaque y costo unitario salen del maestro (ADR-028). Costo_usd del
-- documento queda como costo_documento_usd: ninguna cifra lo usa.
with source as (
    select * from {{ source('raw', 'raw_mb51') }}
),

maestro as (
    select planta, material, tipo_material, costo_unitario_usd
    from {{ ref('stg_maestro_materiales') }}
),

cleaned as (
    select
        s.mblnr                                         as doc_material,
        cast(s.zeile as integer)                        as posicion,
        s.werks                                         as planta,
        s.lgort                                         as almacen,
        s.matnr                                         as material,
        s.maktx                                         as material_desc,
        m.tipo_material,
        s.bwart                                         as mov_type,
        s.mjahr                                         as anio_contable,
        cast(s.budat as date)                           as fecha_contab,
        cast(s.cpudt as date)                           as fecha_registro,
        s.cputm                                         as hora_registro,
        s.menge                                         as cantidad,
        s.meins                                         as unidad,
        s.lifnr                                         as proveedor,
        s.kunnr                                         as cliente,
        s.xblnr                                         as ref_externa,
        m.costo_unitario_usd,
        s.costo_usd                                     as costo_documento_usd,
        datediff('day', cast(s.budat as date), cast(s.cpudt as date)) as lag_dias,
        datediff('day', cast(s.budat as date), cast(s.cpudt as date)) > 2 as flag_tardio
    from source s
    left join maestro m on m.planta = s.werks and m.material = s.matnr
)

select * from cleaned
