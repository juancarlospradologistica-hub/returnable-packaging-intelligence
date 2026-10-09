-- Las ventanas de la necesidad cierran en domingo antes del corte, no entran
-- al arranque del saldo V y quedan en orden. Una var mal puesta (ventana más
-- larga que el dataset) deja una ventana vacía o invertida y la σ sale de nada.
select *
from {{ ref('int_calendario_necesidad') }}
where isodow(fin_base) <> 7
   or fin_base >= corte
   or isodow(inicio_sigma) <> 1
   or inicio_sigma < inicio_estable
   or inicio_base < inicio_sigma
   or inicio_estimacion < inicio_estable
   or inicio_estimacion >= fin_estimacion
   or fin_estimacion + 1 <> inicio_prueba
   or fin_base - inicio_sigma + 1 > 7 * {{ var('ventana_sigma_semanas') }}
