-- Tramos FIFO por cuenta (ADR-011, ADR-012). Cada 621 abre un intervalo
-- [acum_ini, acum_fin) sobre el acumulado de salidas; cada 622 o 702 cierra
-- un intervalo sobre el acumulado de cierres. Un tramo es la intersección.
-- Lo que queda de un 621 después del último cierre es saldo abierto.
-- Uso: ciclo con tramos cerrados por 622. La merma no se atribuye por FIFO.
with movimientos as (
    select * from {{ ref('int_mov_cuenta') }}
),

salidas as (
    select
        planta,
        cliente,
        material,
        tipo_material,
        fecha_contab                                    as fecha_salida,
        anio_contable                                   as anio_salida,
        doc_material                                    as doc_salida,
        posicion                                        as pos_salida,
        sum(cantidad_abs) over cuenta - cantidad_abs    as acum_ini,
        sum(cantidad_abs) over cuenta                   as acum_fin
    from movimientos
    where mov_type = '621'
    window cuenta as (
        partition by planta, cliente, material
        order by fecha_contab, anio_contable, doc_material, posicion
        rows between unbounded preceding and current row
    )
),

cierres as (
    select
        planta,
        cliente,
        material,
        mov_type                                        as tipo_cierre,
        fecha_contab                                    as fecha_cierre,
        anio_contable                                   as anio_cierre,
        doc_material                                    as doc_cierre,
        sum(cantidad_abs) over cuenta - cantidad_abs    as acum_ini,
        sum(cantidad_abs) over cuenta                   as acum_fin
    from movimientos
    where mov_type in ('622', '702')
    window cuenta as (
        partition by planta, cliente, material
        order by fecha_contab, anio_contable, doc_material, posicion
        rows between unbounded preceding and current row
    )
),

tramos_cerrados as (
    select
        s.planta,
        s.cliente,
        s.material,
        s.tipo_material,
        s.fecha_salida,
        s.anio_salida,
        s.doc_salida,
        s.pos_salida,
        c.tipo_cierre,
        c.fecha_cierre,
        c.anio_cierre,
        c.doc_cierre,
        least(s.acum_fin, c.acum_fin) - greatest(s.acum_ini, c.acum_ini) as cantidad
    from salidas s
    join cierres c
        on  s.planta   = c.planta
        and s.cliente  = c.cliente
        and s.material = c.material
        and c.acum_ini < s.acum_fin
        and s.acum_ini < c.acum_fin
),

total_cerrado as (
    select planta, cliente, material, max(acum_fin) as cerrado
    from cierres
    group by planta, cliente, material
),

tramos_abiertos as (
    select
        s.planta,
        s.cliente,
        s.material,
        s.tipo_material,
        s.fecha_salida,
        s.anio_salida,
        s.doc_salida,
        s.pos_salida,
        cast(null as varchar)                           as tipo_cierre,
        cast(null as date)                              as fecha_cierre,
        cast(null as bigint)                            as anio_cierre,
        cast(null as varchar)                           as doc_cierre,
        s.acum_fin - greatest(s.acum_ini, coalesce(t.cerrado, 0)) as cantidad
    from salidas s
    left join total_cerrado t
        on  s.planta   = t.planta
        and s.cliente  = t.cliente
        and s.material = t.material
    where s.acum_fin > coalesce(t.cerrado, 0)
),

tramos as (
    select * from tramos_cerrados
    union all
    select * from tramos_abiertos
)

select
    *,
    datediff('day', fecha_salida, fecha_cierre)         as dias
from tramos
