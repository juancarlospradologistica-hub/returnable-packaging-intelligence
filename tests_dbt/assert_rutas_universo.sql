-- mart_rutas es el universo de rutas (ADR-015): una fila por planta × cliente
-- y las mismas rutas que evalúa la alerta de exceso de saldo. Si difieren, el
-- "de N" de los KPIs depende de qué mart se consulte.
with rutas as (
    select planta, cliente, count(*) as filas
    from {{ ref('mart_rutas') }}
    group by planta, cliente
),

exceso as (
    select distinct planta, cliente
    from {{ ref('mart_exceso_saldo_ruta') }}
)

select 'duplicada' as problema, planta, cliente
from rutas
where filas > 1

union all

select 'sin exceso', r.planta, r.cliente
from rutas r
anti join exceso e using (planta, cliente)

union all

select 'sin ruta', e.planta, e.cliente
from exceso e
anti join rutas r using (planta, cliente)
