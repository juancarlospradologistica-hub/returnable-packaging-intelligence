-- El saldo del último mes de cada cuenta es igual a la suma de sus movimientos
-- y a la cantidad en tramos FIFO abiertos: dos caminos, mismo número.
with ultimo as (
    select planta, cliente, material, saldo_fin_mes
    from {{ ref('int_cuenta_mensual') }}
    qualify mes = max(mes) over ()
),

movimientos as (
    select planta, cliente, material, sum(delta_saldo) as saldo
    from {{ ref('int_mov_cuenta') }}
    group by planta, cliente, material
),

abiertos as (
    select planta, cliente, material, sum(cantidad) as saldo
    from {{ ref('int_tramos_fifo') }}
    where tipo_cierre is null
    group by planta, cliente, material
)

select *
from ultimo u
full outer join movimientos m using (planta, cliente, material)
left join abiertos a using (planta, cliente, material)
where coalesce(u.saldo_fin_mes, -1) <> m.saldo
   or m.saldo <> coalesce(a.saldo, 0)
