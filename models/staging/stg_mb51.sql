-- Sin filtro de Bwart: un código fuera del contrato debe fallar el test del source,
-- no desaparecer en silencio.
with source as (
    select * from {{ source('raw', 'raw_mb51') }}
),

cleaned as (
    select
        mblnr                                           as doc_material,
        cast(zeile as integer)                          as posicion,
        werks                                           as planta,
        lgort                                           as almacen,
        matnr                                           as material,
        maktx                                           as material_desc,
        case
            when matnr like 'KLT-%' then 'KLT'
            when matnr like 'RCK-%' then 'RACK'
            when matnr like 'CTN-%' then 'CARTON'
        end                                             as tipo_material,
        bwart                                           as mov_type,
        mjahr                                           as anio_contable,
        cast(budat as date)                             as fecha_contab,
        cast(cpudt as date)                             as fecha_registro,
        cputm                                           as hora_registro,
        menge                                           as cantidad,
        meins                                           as unidad,
        lifnr                                           as proveedor,
        kunnr                                           as cliente,
        xblnr                                           as ref_externa,
        costo_usd                                       as costo_usd,
        datediff('day', cast(budat as date), cast(cpudt as date)) as lag_dias,
        datediff('day', cast(budat as date), cast(cpudt as date)) > 2 as flag_tardio
    from source
)

select * from cleaned
