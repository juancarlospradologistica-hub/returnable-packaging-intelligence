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
    where bwart in ('501','502','601','602','311','411','101','102','261','309')
)

select * from cleaned