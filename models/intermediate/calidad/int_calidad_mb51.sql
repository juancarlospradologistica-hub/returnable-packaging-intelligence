-- Reglas por causa sobre MB51 (ADR-028, ADR-030). Una fila por línea que
-- viola una regla, salvo llave_duplicada (una por llave repetida) y
-- precio_documento_distinto (una por material). Las clases de movimiento se
-- leen por evento del seed, no por código: un extracto real se mapea ahí.
--
-- lineas no se materializa (ADR-032): seis CTEs la leen y DuckDB la guardaría
-- completa, 21M filas, dentro del mismo tope de 4 GB que comparten los modelos
-- que dbt corre en paralelo. Releer stg_mb51 cuesta menos que guardarla.
with lineas as not materialized (
    select m.*, e.evento
    from {{ ref('stg_mb51') }} m
    left join {{ ref('clases_movimiento') }} e on e.bwart = m.mov_type
),

llave as (
    select
        'llave_duplicada'                                   as regla,
        planta, material, anio_contable, doc_material, posicion,
        cast(null as varchar)                               as parte,
        sum(abs(cantidad)) - max(abs(cantidad))             as unidades,
        (sum(abs(cantidad)) - max(abs(cantidad))) * max(costo_unitario_usd) as usd_expuesto,
        count(*) || ' filas con la misma llave'             as detalle
    from lineas
    group by planta, material, anio_contable, doc_material, posicion
    having count(*) > 1
),

por_linea as (
    select
        case
            when evento is null then 'bwart_fuera_de_catalogo'
            when almacen is not null
                and almacen not in (select lgort from {{ ref('almacenes') }})
                then 'lgort_fuera_de_catalogo'
            when evento in ('salida_cliente', 'recogida_cliente', 'faltante_cliente', 'salida_desechable')
                and cliente is null
                then 'cliente_vacio'
            when (evento in ('storno_compra', 'consumo', 'baja', 'salida_desechable',
                             'salida_cliente', 'faltante_cliente') and cantidad >= 0)
                or (evento in ('entrada_compra', 'recogida_cliente') and cantidad <= 0)
                or (evento in ('traslado', 'traslado_bloqueado', 'bloqueo', 'desbloqueo')
                    and (posicion not in (1, 2)
                         or (posicion = 1 and cantidad >= 0)
                         or (posicion = 2 and cantidad <= 0)))
                then 'signo_invertido'
        end                                                 as regla,
        *
    from lineas
),

reglas_linea as (
    select
        regla, planta, material, anio_contable, doc_material, posicion,
        cast(null as varchar)                               as parte,
        abs(cantidad)                                       as unidades,
        abs(cantidad) * costo_unitario_usd                  as usd_expuesto,
        mov_type || ' ' || coalesce(almacen, '-') || ' ' || cantidad as detalle
    from por_linea
    where regla is not null
),

-- Contenedores capturados en piezas: la cantidad de la salida es múltiplo de
-- las piezas por contenedor del material y no menor que ellas. Supone menos
-- contenedores por línea que piezas por contenedor (ADR-028, Consecuencias).
piezas as (
    select planta, material, min(piezas_por_contenedor) as piezas
    from {{ ref('stg_instruccion_empaque') }}
    where piezas_por_contenedor > 0
    group by planta, material
),

en_piezas as (
    select
        'cantidad_en_piezas'                                as regla,
        l.planta, l.material, l.anio_contable, l.doc_material, l.posicion,
        cast(null as varchar)                               as parte,
        abs(l.cantidad) - abs(l.cantidad) / p.piezas        as unidades,
        (abs(l.cantidad) - abs(l.cantidad) / p.piezas) * l.costo_unitario_usd as usd_expuesto,
        abs(l.cantidad) || ' con ' || p.piezas || ' piezas por contenedor' as detalle
    from lineas l
    join piezas p on p.planta = l.planta and p.material = l.material
    where l.evento = 'salida_cliente'
      and abs(l.cantidad) >= p.piezas
      and abs(l.cantidad) % p.piezas = 0
),

-- Saldo de la cuenta planta × cliente × material al cierre de cada día, con la
-- foto inicial de stock especial V si la trae. Se reporta la recogida del día
-- en que la cuenta cruza a negativo, o la de una cuenta que nunca recibió el
-- material. Los días siguientes en negativo son consecuencia, no otra causa.
cuenta as (
    select planta, cliente, material, fecha_contab as fecha,
        case evento when 'salida_cliente' then abs(cantidad) else -abs(cantidad) end as delta,
        case evento when 'salida_cliente' then abs(cantidad) else 0 end as entrada
    from lineas
    where evento in ('salida_cliente', 'recogida_cliente', 'faltante_cliente')
      and cliente is not null
    union all
    select planta, cliente, material, fecha, cantidad, cantidad
    from {{ ref('stg_stock_inicial') }}
    where cliente is not null
),

saldo_dia as (
    select
        planta, cliente, material, fecha,
        sum(sum(delta)) over w                              as saldo,
        sum(sum(entrada)) over w                            as entradas
    from cuenta
    group by planta, cliente, material, fecha
    window w as (partition by planta, cliente, material order by fecha)
),

cruce as (
    select
        *,
        coalesce(lag(saldo) over (
            partition by planta, cliente, material order by fecha
        ), 0)                                               as saldo_anterior
    from saldo_dia
),

sin_saldo as (
    select
        'recogida_sin_saldo'                                as regla,
        l.planta, l.material, l.anio_contable, l.doc_material, l.posicion,
        cast(null as varchar)                               as parte,
        abs(l.cantidad)                                     as unidades,
        abs(l.cantidad) * l.costo_unitario_usd              as usd_expuesto,
        'saldo al cierre ' || s.saldo                       as detalle
    from lineas l
    join cruce s
        on s.planta = l.planta and s.cliente = l.cliente
       and s.material = l.material and s.fecha = l.fecha_contab
    where l.evento = 'recogida_cliente'
      and (s.entradas = 0 or (s.saldo < 0 and s.saldo_anterior >= 0))
),

tardio as (
    select
        'registro_despues_del_cierre'                       as regla,
        planta, material, anio_contable, doc_material, posicion,
        cast(null as varchar)                               as parte,
        abs(cantidad)                                       as unidades,
        abs(cantidad) * costo_unitario_usd                  as usd_expuesto,
        'registrado ' || fecha_registro || ', contabilizado ' || fecha_contab as detalle
    from lineas
    where fecha_registro > last_day(fecha_contab) + {{ var('calidad_dias_cierre') }}
),

-- Solo cuando el documento trae valor y el maestro está en USD: con LEIH
-- estándar el documento no lleva importe y no hay nada que comparar. El valor
-- expuesto es la diferencia de precio por la flota de la foto inicial, igual
-- que en el maestro; por línea contaría cada traslado interno.
foto as (
    select planta, material, sum(cantidad) as flota
    from {{ ref('stg_stock_inicial') }}
    group by planta, material
),

precio as (
    select
        'precio_documento_distinto'                         as regla,
        l.planta, l.material,
        cast(null as bigint)                                as anio_contable,
        cast(null as varchar)                               as doc_material,
        cast(null as integer)                               as posicion,
        cast(null as varchar)                               as parte,
        cast(max(coalesce(f.flota, 0)) as double)           as unidades,
        max(abs(l.costo_documento_usd - l.costo_unitario_usd)) * max(coalesce(f.flota, 0))
                                                            as usd_expuesto,
        'documento ' || min(l.costo_documento_usd) || ' a ' || max(l.costo_documento_usd)
            || ', maestro ' || max(l.costo_unitario_usd)    as detalle
    from lineas l
    join {{ ref('stg_maestro_materiales') }} m
        on m.planta = l.planta and m.material = l.material and m.moneda = 'USD'
    left join foto f on f.planta = l.planta and f.material = l.material
    where l.costo_documento_usd > 0
      and abs(l.costo_documento_usd - l.costo_unitario_usd)
          > l.costo_unitario_usd * {{ var('calidad_tolerancia_precio_pct') }} / 100
    group by l.planta, l.material
),

-- Ciegos (ADR-033, ADR-034). Contabilizada después de la fecha del extracto.
despues_del_corte as (
    select
        'budat_despues_del_corte'                           as regla,
        planta, material, anio_contable, doc_material, posicion,
        cast(null as varchar)                               as parte,
        abs(cantidad)                                       as unidades,
        abs(cantidad) * costo_unitario_usd                  as usd_expuesto,
        'contabilizado ' || fecha_contab || ', extracto al ' || {{ fecha_extraccion() }} as detalle
    from lineas
    where fecha_contab > {{ fecha_extraccion() }}
),

-- La misma salida contabilizada otra vez con otro número: misma entrega
-- (Xblnr), material, cliente, cantidad y fecha. Por contenido solo, el
-- completo tiene 586,939 salidas legítimas iguales a otra del mismo día; con
-- la entrega, ninguna. Se reportan los documentos registrados después del
-- primero. Un mismo documento repetido es llave_duplicada, no esta.
salidas_ref as (
    select
        planta, ref_externa, material, cliente, cantidad, fecha_contab,
        anio_contable, doc_material,
        min(fecha_registro)                                 as registro
    from lineas
    where evento = 'salida_cliente' and ref_externa is not null
    group by all
),

orden_ref as (
    select
        *,
        row_number() over w                                 as n,
        first_value(doc_material) over w                    as primero
    from salidas_ref
    window w as (
        partition by planta, ref_externa, material, cliente, cantidad, fecha_contab
        order by registro, anio_contable, doc_material
    )
),

repetido as (
    select
        'documento_repetido'                                as regla,
        l.planta, l.material, l.anio_contable, l.doc_material, l.posicion,
        cast(null as varchar)                               as parte,
        abs(l.cantidad)                                     as unidades,
        abs(l.cantidad) * l.costo_unitario_usd              as usd_expuesto,
        'entrega ' || o.ref_externa || ', primero en ' || o.primero as detalle
    from lineas l
    join orden_ref o
        on o.planta = l.planta and o.anio_contable = l.anio_contable
       and o.doc_material = l.doc_material and o.ref_externa = l.ref_externa
       and o.material = l.material and o.cliente = l.cliente
       and o.cantidad = l.cantidad and o.fecha_contab = l.fecha_contab
    where o.n > 1 and l.evento = 'salida_cliente'
),

-- Código con ceros a la izquierda que el maestro tiene sin ellos: cambió la
-- conversión del extracto (MATN1 para el material, ALPHA para el cliente).
maestro_codigo as (
    select
        planta, ltrim(material, '0') as codigo,
        min(material)                                       as material,
        max(costo_unitario_usd)                             as costo_unitario_usd
    from {{ ref('stg_maestro_materiales') }}
    group by planta, ltrim(material, '0')
),

matnr_formato as (
    select
        'matnr_con_formato'                                 as regla,
        l.planta, l.material, l.anio_contable, l.doc_material, l.posicion,
        cast(null as varchar)                               as parte,
        abs(l.cantidad)                                     as unidades,
        abs(l.cantidad) * m.costo_unitario_usd              as usd_expuesto,
        'en el maestro como ' || m.material                 as detalle
    from lineas l
    join maestro_codigo m
        on m.planta = l.planta and m.codigo = ltrim(l.material, '0')
       and m.material <> l.material
    where l.tipo_material is null
),

-- La cuenta buena es la que tiene salidas: el cliente con ceros solo aparece
-- en recogidas o faltantes. Si las dos versiones tienen salidas, no hay cómo
-- saber cuál es la buena y la regla no marca ninguna.
clientes_salida as (
    select distinct planta, cliente
    from lineas
    where evento = 'salida_cliente' and cliente is not null
),

cuentas as (
    select planta, ltrim(cliente, '0') as codigo, min(cliente) as cliente
    from clientes_salida
    group by planta, ltrim(cliente, '0')
),

kunnr_formato as (
    select
        'kunnr_con_formato'                                 as regla,
        l.planta, l.material, l.anio_contable, l.doc_material, l.posicion,
        cast(null as varchar)                               as parte,
        abs(l.cantidad)                                     as unidades,
        abs(l.cantidad) * l.costo_unitario_usd              as usd_expuesto,
        'cuenta ' || c.cliente                              as detalle
    from lineas l
    join cuentas c
        on c.planta = l.planta and c.codigo = ltrim(l.cliente, '0')
       and c.cliente <> l.cliente
    left join clientes_salida x on x.planta = l.planta and x.cliente = l.cliente
    where l.evento in ('salida_cliente', 'recogida_cliente', 'faltante_cliente')
      and x.cliente is null
),

-- Una línea con el código en otro formato rompe el saldo de su cuenta, pero la
-- causa es el formato: recogida_sin_saldo no la cuenta otra vez (ADR-034).
con_formato as (
    select planta, anio_contable, doc_material, posicion from matnr_formato
    union
    select planta, anio_contable, doc_material, posicion from kunnr_formato
)

select * from llave
union all select * from reglas_linea
union all select * from en_piezas
union all
select s.*
from sin_saldo s
anti join con_formato f
    on f.planta = s.planta and f.anio_contable = s.anio_contable
   and f.doc_material = s.doc_material and f.posicion = s.posicion
union all select * from tardio
union all select * from precio
union all select * from despues_del_corte
union all select * from repetido
union all select * from matnr_formato
union all select * from kunnr_formato
