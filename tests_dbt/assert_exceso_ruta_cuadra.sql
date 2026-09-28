-- El saldo y el esperado por ruta suman lo mismo que int_cuenta_mensual:
-- el mart solo agrega, no filtra cuentas.
with mart as (
    select mes, sum(saldo_fin_mes) as saldo, sum(saldo_esperado) as esperado
    from {{ ref('mart_exceso_saldo_ruta') }}
    group by mes
),

cuenta as (
    select mes, sum(saldo_fin_mes) as saldo, sum(saldo_esperado) as esperado
    from {{ ref('int_cuenta_mensual') }}
    group by mes
)

select *
from mart m
full outer join cuenta c using (mes)
where m.saldo is distinct from c.saldo
   or abs(m.esperado - c.esperado) > 1
