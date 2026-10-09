-- La flota solo baja por faltante en cliente (702) y por baja (555): inicial
-- menos faltantes menos bajas acumulados al cierre = stock en almacenes más
-- stock V. El lado derecho sale del mart; el izquierdo, de la foto y de
-- staging por evento, sin pasar por int_stock_diario. Un traslado sin pareja,
-- un Lgort fuera del ciclo o un estado sin columna en el mart rompen la suma.
-- También valida una fila por planta, material y semana.
with mart as (
    select
        planta,
        material,
        semana,
        fecha_cierre,
        count(*)                                        as filas,
        sum(recepcion + vacios + linea + llenos + sucios + reparacion + scrap
            + cliente)                                  as flota
    from {{ ref('mart_flota_semanal') }}
    group by planta, material, semana, fecha_cierre
),

inicial as (
    select planta, material, sum(cantidad) as cantidad
    from {{ ref('stg_stock_inicial') }}
    group by planta, material
),

perdidas as (
    select m.planta, m.material, m.fecha_contab as fecha, sum(abs(m.cantidad)) as cantidad
    from {{ ref('stg_mb51') }} m
    join {{ ref('clases_movimiento') }} c on c.bwart = m.mov_type
    where c.evento in ('faltante_cliente', 'baja')
    group by m.planta, m.material, m.fecha_contab
),

esperado as (
    select
        k.planta,
        k.material,
        k.semana,
        coalesce(i.cantidad, 0) - coalesce(sum(p.cantidad), 0) as flota
    from mart k
    left join inicial i
        on i.planta = k.planta and i.material = k.material
    left join perdidas p
        on p.planta = k.planta and p.material = k.material and p.fecha <= k.fecha_cierre
    group by k.planta, k.material, k.semana, i.cantidad
)

select k.*, e.flota as flota_esperada
from mart k
left join esperado e
    on e.planta = k.planta and e.material = k.material and e.semana = k.semana
where k.filas <> 1
   or e.flota is null
   or k.flota <> e.flota
