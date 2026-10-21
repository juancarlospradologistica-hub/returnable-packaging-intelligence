-- Flujos de la flota por planta, tipo de empaque, semana y tramo del ciclo
-- (ADR-039): de qué estado a qué estado se movieron cuántos contenedores. Es
-- el grosor de cada tramo del anillo en el dashboard. Semana de lunes a
-- domingo, igual que mart_flota_semanal; estados y eventos salen de los seeds.
-- Los traslados se emparejan por documento: la posición que sale y la que
-- entra. Con el cliente no hay pareja: 621 va de llenos a cliente, 622 de
-- cliente a sucios y 702 de cliente a faltante. La baja 555 va de scrap a
-- baja.
with mov as (
    select
        m.planta,
        m.anio_contable,
        m.doc_material,
        m.material,
        m.tipo_material,
        cast(date_trunc('week', m.fecha_contab) as date)    as semana,
        m.cantidad,
        a.estado,
        c.evento
    from {{ ref('stg_mb51') }} m
    join {{ ref('clases_movimiento') }} c on c.bwart = m.mov_type
    left join {{ ref('almacenes') }} a on a.lgort = m.almacen
    where m.tipo_material in ('KLT', 'RACK')
),

traslados as (
    select
        s.planta,
        s.tipo_material,
        s.semana,
        s.estado                                            as origen,
        e.estado                                            as destino,
        -sum(s.cantidad)                                    as contenedores
    from mov s
    join mov e
        on  e.planta = s.planta
        and e.anio_contable = s.anio_contable
        and e.doc_material = s.doc_material
        and e.material = s.material
        and e.cantidad > 0
    where s.cantidad < 0
      and s.evento in ('traslado', 'traslado_bloqueado')
      and s.estado <> e.estado
    group by all
),

con_cliente as (
    select
        planta,
        tipo_material,
        semana,
        case evento
            when 'salida_cliente' then 'llenos'
            when 'baja' then 'scrap'
            else 'cliente'
        end                                                 as origen,
        case evento
            when 'salida_cliente' then 'cliente'
            when 'recogida_cliente' then 'sucios'
            when 'faltante_cliente' then 'faltante'
            else 'baja'
        end                                                 as destino,
        sum(abs(cantidad))                                  as contenedores
    from mov
    where evento in ('salida_cliente', 'recogida_cliente', 'faltante_cliente', 'baja')
    group by all
)

select planta, tipo_material, semana, origen, destino, cast(contenedores as bigint) as contenedores
from traslados
union all
select planta, tipo_material, semana, origen, destino, cast(contenedores as bigint)
from con_cliente
