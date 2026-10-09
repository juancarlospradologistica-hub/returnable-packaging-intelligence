-- Stock por planta, material, ubicación y tipo de stock al cierre de cada día
-- en que cambia. El saldo sigue vigente hasta la siguiente fila de la llave.
-- Se guarda solo el día con cambio: el calendario completo da 23M filas
-- en días hábiles y 33M en naturales sin agregar información (ADR-020).
-- El stock se mide al cierre del día; el orden dentro del día no se modela
-- (ADR-018, punto 9).
with por_dia as (
    select
        planta,
        material,
        tipo_material,
        estado,
        tipo_stock,
        fecha,
        sum(delta)                                      as delta
    from {{ ref('int_mov_stock') }}
    group by planta, material, tipo_material, estado, tipo_stock, fecha
)

select
    planta,
    material,
    tipo_material,
    estado,
    tipo_stock,
    fecha,
    cast(delta as bigint)                               as delta,
    cast(sum(delta) over (
        partition by planta, material, estado, tipo_stock
        order by fecha
        rows between unbounded preceding and current row
    ) as bigint)                                        as saldo
from por_dia
-- Un 344 y su 325 del mismo día dejan SUCI bloqueado igual que estaba.
where delta <> 0
