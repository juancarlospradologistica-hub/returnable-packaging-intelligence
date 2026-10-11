-- Reglas por causa sobre la foto de stock inicial (ADR-028, ADR-030).
with foto as (
    select * from {{ ref('stg_stock_inicial') }}
),

almacen as (
    select
        'lgort_fuera_de_catalogo'                           as regla,
        f.planta, f.material,
        cast(null as bigint)                                as anio_contable,
        cast(null as varchar)                               as doc_material,
        cast(null as integer)                               as posicion,
        cast(null as varchar)                               as parte,
        f.cantidad                                          as unidades,
        f.cantidad * m.costo_unitario_usd                   as usd_expuesto,
        'foto en ' || f.almacen                             as detalle
    from foto f
    left join {{ ref('stg_maestro_materiales') }} m
        on m.planta = f.planta and m.material = f.material
    where f.almacen is not null
      and f.almacen not in (select lgort from {{ ref('almacenes') }})
),

-- Retornable que se mueve dentro de la planta sin foto inicial. Si su primer
-- movimiento es una entrada de flota nueva, arrancó en la ventana y no le
-- falta foto. El faltante es lo más negativo que llega su stock en planta.
sin_foto as (
    select m.planta, m.material
    from {{ ref('stg_mb51') }} m
    where m.tipo_material in ('KLT', 'RACK') and m.almacen is not null
    group by m.planta, m.material
    except
    select planta, material from foto
),

lineas as (
    select m.planta, m.material, m.fecha_contab, m.cantidad, m.costo_unitario_usd, e.evento
    from {{ ref('stg_mb51') }} m
    join sin_foto s on s.planta = m.planta and s.material = m.material
    left join {{ ref('clases_movimiento') }} e on e.bwart = m.mov_type
    where m.almacen is not null
),

primero as (
    select planta, material, arg_min(evento, fecha_contab) as primer_evento
    from lineas
    group by planta, material
),

diario as (
    select
        planta, material, fecha_contab,
        sum(sum(cantidad)) over (
            partition by planta, material order by fecha_contab
        )                                                   as stock,
        max(costo_unitario_usd)                             as costo
    from lineas
    group by planta, material, fecha_contab
),

faltante as (
    select
        'material_sin_foto'                                 as regla,
        d.planta, d.material,
        cast(null as bigint)                                as anio_contable,
        cast(null as varchar)                               as doc_material,
        cast(null as integer)                               as posicion,
        cast(null as varchar)                               as parte,
        greatest(-min(d.stock), 0)                          as unidades,
        greatest(-min(d.stock), 0) * max(d.costo)           as usd_expuesto,
        'primer movimiento: ' || coalesce(max(p.primer_evento), 'sin evento') as detalle
    from diario d
    join primero p on p.planta = d.planta and p.material = d.material
    where p.primer_evento is distinct from 'entrada_compra'
    group by d.planta, d.material
)

select * from almacen
union all select * from faltante
