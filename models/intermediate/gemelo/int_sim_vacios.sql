-- Cambio neto de vacíos por material y día, con la apertura de la foto en su
-- fecha (ADR-020). Es la traza que el gemelo corrige con la capacidad de cada
-- estación (ADR-038).
select
    planta,
    tipo_material,
    material,
    fecha,
    cast(sum(delta) as bigint)                                          as delta
from {{ ref('int_stock_diario') }}
where estado = 'vacios'
group by all
