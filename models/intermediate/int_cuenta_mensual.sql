-- Saldo de stock especial V por cuenta a fin de cada mes y saldo esperado
-- (ADR-012): cada salida 621 aporta su cantidad por la probabilidad de seguir
-- en cliente a su edad. El exceso sobre el esperado es merma todavía no
-- reconocida en conciliación. El esperado es aditivo: se puede sumar a ruta
-- o planta sin recalcular.
with movimientos as (
    select * from {{ ref('int_mov_cuenta') }}
),

supervivencia as (
    select * from {{ ref('int_supervivencia_retorno') }}
),

-- Cierre en el último día hábil del mes. Los 621 y 622 solo se contabilizan
-- lunes a viernes; si el mes termina en fin de semana, el saldo real es el del
-- viernes y el esperado por días naturales ya descontaría recogidas que aún no
-- se registran. Ese desfase daba +7% de exceso en toda la flota los domingos.
meses as (
    select
        cast(mes as date)                                           as mes,
        cast(last_day(mes) - case isodow(last_day(mes))
            when 6 then 1
            when 7 then 2
            else 0
        end as date)                                                as fin_mes
    from (
        select unnest(generate_series(
            date_trunc('month', min(fecha_contab)),
            date_trunc('month', max(fecha_contab)),
            interval 1 month
        )) as mes
        from movimientos
    )
),

cuentas as (
    select
        planta,
        cliente,
        material,
        tipo_material,
        min(fecha_contab)                               as primera_salida
    from movimientos
    group by planta, cliente, material, tipo_material
),

-- Una fila por cuenta y mes desde su primer movimiento: el saldo existe
-- aunque ese mes no haya movimientos.
base as (
    select c.planta, c.cliente, c.material, c.tipo_material, m.mes, m.fin_mes
    from cuentas c
    join meses m on m.fin_mes >= c.primera_salida
),

por_mes as (
    select
        planta,
        cliente,
        material,
        date_trunc('month', fecha_contab)                               as mes,
        sum(cantidad_abs) filter (where mov_type = '621')               as salidas,
        sum(cantidad_abs) filter (where mov_type = '622')               as recogidas,
        sum(cantidad_abs) filter (where mov_type = '702')               as faltantes,
        sum(delta_saldo)                                                as delta
    from movimientos
    group by planta, cliente, material, date_trunc('month', fecha_contab)
),

salidas_dia as (
    select
        planta,
        cliente,
        material,
        tipo_material,
        fecha_contab,
        sum(cantidad_abs)                               as cantidad
    from movimientos
    where mov_type = '621'
    group by planta, cliente, material, tipo_material, fecha_contab
),

horizonte as (
    select max(edad) as max_edad from supervivencia
),

-- Cada salida aporta a los fines de mes que caen dentro del horizonte de la
-- curva. Se parte de las salidas y no de cuenta × mes × edad: con 14 plantas
-- ese producto no cabe en memoria.
aportes as (
    select
        s.planta,
        s.cliente,
        s.material,
        m.mes,
        s.cantidad * v.prob_en_cliente                  as aporte
    from salidas_dia s
    cross join horizonte h
    join meses m
        on m.fin_mes between s.fecha_contab and s.fecha_contab + h.max_edad
    join supervivencia v
        on  v.tipo_material = s.tipo_material
        and v.edad = m.fin_mes - s.fecha_contab
),

esperado as (
    select planta, cliente, material, mes, sum(aporte) as saldo_esperado
    from aportes
    group by planta, cliente, material, mes
),

armado as (
    select
        b.planta,
        b.cliente,
        b.material,
        b.tipo_material,
        b.mes,
        b.fin_mes,
        coalesce(p.salidas, 0)                          as salidas,
        coalesce(p.recogidas, 0)                        as recogidas,
        coalesce(p.faltantes, 0)                        as faltantes,
        sum(coalesce(p.delta, 0)) over (
            partition by b.planta, b.cliente, b.material
            order by b.mes
            rows between unbounded preceding and current row
        )                                               as saldo_fin_mes,
        coalesce(e.saldo_esperado, 0)                   as saldo_esperado
    from base b
    left join por_mes p
        on  p.planta = b.planta
        and p.cliente = b.cliente
        and p.material = b.material
        and p.mes = b.mes
    left join esperado e
        on  e.planta = b.planta
        and e.cliente = b.cliente
        and e.material = b.material
        and e.mes = b.mes
)

select
    *,
    saldo_fin_mes - saldo_esperado                      as exceso_saldo
from armado
