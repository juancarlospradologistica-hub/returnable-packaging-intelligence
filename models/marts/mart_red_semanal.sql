-- La red planta × cliente por semana (ADR-039): salidas 621, recogidas 622 y
-- faltante 702 por tipo de empaque. Es el grosor de cada ruta en la vista de
-- la red del dashboard.
select
    m.planta,
    m.cliente,
    m.tipo_material,
    cast(date_trunc('week', m.fecha_contab) as date)                        as semana,
    cast(coalesce(sum(abs(m.cantidad)) filter (where c.evento = 'salida_cliente'), 0) as bigint)
                                                                            as salidas,
    cast(coalesce(sum(abs(m.cantidad)) filter (where c.evento = 'recogida_cliente'), 0) as bigint)
                                                                            as recogidas,
    cast(coalesce(sum(abs(m.cantidad)) filter (where c.evento = 'faltante_cliente'), 0) as bigint)
                                                                            as faltante
from {{ ref('stg_mb51') }} m
join {{ ref('clases_movimiento') }} c on c.bwart = m.mov_type
where c.evento in ('salida_cliente', 'recogida_cliente', 'faltante_cliente')
  and m.tipo_material in ('KLT', 'RACK')
group by all
