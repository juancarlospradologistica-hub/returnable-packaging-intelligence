-- El cierre mensual cae en día hábil y dentro de su mes. Un cierre en fin de
-- semana mide el saldo del viernes contra un esperado de domingo.
select distinct mes, fin_mes
from {{ ref('int_cuenta_mensual') }}
where isodow(fin_mes) > 5
   or date_trunc('month', fin_mes) <> mes
