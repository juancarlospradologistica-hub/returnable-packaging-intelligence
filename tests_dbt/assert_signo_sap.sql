-- Salidas negativas, entradas positivas (ADR-011). En los traslados dentro de la
-- planta la posición 1 sale y la 2 entra; en 344 y 343 las dos van al mismo
-- almacén y el signo marca el tipo de stock (ADR-017, punto 3). La suma cero
-- por documento se valida en pytest.
select *
from {{ ref('stg_mb51') }}
where (mov_type in ('102', '261', '555', '601', '621', '702') and cantidad >= 0)
   or (mov_type in ('101', '622') and cantidad <= 0)
   or (mov_type in ('311', '325', '343', '344') and posicion = 1 and cantidad >= 0)
   or (mov_type in ('311', '325', '343', '344') and posicion = 2 and cantidad <= 0)
   or (mov_type in ('311', '325', '343', '344') and posicion not in (1, 2))
