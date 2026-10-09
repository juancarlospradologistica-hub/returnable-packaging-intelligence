-- Ninguna ubicación queda negativa al cierre del día, en ningún tipo de stock
-- (ADR-018, punto 9). Con stock_inicial bien calculado la flota alcanza; un
-- traslado sin su pareja o una foto inicial corta aparecen aquí.
select *
from {{ ref('int_stock_diario') }}
where saldo < 0
