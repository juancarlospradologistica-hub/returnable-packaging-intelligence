with movimientos as (
    select * from {{ ref('stg_mb51') }}
),

salidas as (
    select
        planta,
        material,
        material_desc,
        cliente,
        fecha_contab    as fecha_salida,
        cantidad,
        costo_usd,
        doc_material,
        posicion
    from movimientos
    where mov_type = '601'
),

retornos as (
    select
        planta,
        material,
        cliente,
        fecha_contab    as fecha_retorno,
        doc_material,
        posicion
    from movimientos
    where mov_type = '602'
),

ciclo as (
    select
        s.planta,
        s.material,
        s.material_desc,
        s.cliente,
        s.fecha_salida,
        r.fecha_retorno,
        datediff('day', s.fecha_salida, r.fecha_retorno)    as dias_ciclo,
        s.cantidad,
        s.costo_usd,
        s.doc_material                                      as doc_salida,
        r.doc_material                                      as doc_retorno,
        case
            when r.fecha_retorno is null then true
            else false
        end                                                 as es_merma
    from salidas s
    left join retornos r
        on  s.planta   = r.planta
        and s.material = r.material
        and s.cliente  = r.cliente
        and r.fecha_retorno between s.fecha_salida
            and date_add(s.fecha_salida, interval 120 days)
)

select * from ciclo