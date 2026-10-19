-- Una fila por planta, almacén o cliente y material, con cantidad positiva
-- (ADR-018, punto 8; ADR-036). Una fila repetida duplica flota; una en cero o
-- negativa no existe en MB5B ni en MSKU.
select werks, lgort, kunnr, matnr, count(*) as filas, min(menge) as menge_min
from {{ source('raw', 'raw_stock_inicial') }}
group by werks, lgort, kunnr, matnr
having count(*) > 1 or min(menge) <= 0
