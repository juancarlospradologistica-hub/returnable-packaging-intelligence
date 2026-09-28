-- Cantidad positiva, cierre nunca antes de la salida, y fecha y tipo
-- de cierre presentes o ausentes juntos.
select *
from {{ ref('int_tramos_fifo') }}
where cantidad <= 0
   or dias < 0
   or (tipo_cierre is null) <> (fecha_cierre is null)
