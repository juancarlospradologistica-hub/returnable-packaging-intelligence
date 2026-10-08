-- Una fila por planta, almacén y material, con cantidad positiva (ADR-018, punto 8).
-- Una fila repetida duplica flota; una en cero o negativa no existe en MB5B.
select werks, lgort, matnr, count(*) as filas, min(menge) as menge_min
from {{ source('raw', 'raw_stock_inicial') }}
group by werks, lgort, matnr
having count(*) > 1 or min(menge) <= 0
