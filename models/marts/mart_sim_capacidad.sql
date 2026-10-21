-- Gemelo de la red RPL (ADR-038): cada escenario de capacidad de lavado de
-- empaques y reparación por planta y tipo de empaque. Un escenario con paro
-- trae su peor inicio y la mediana de todos los inicios posibles.
-- El faltante es lo que sale en desechable porque no hubo vacío; se valúa
-- igual que el desechable de la brecha (ADR-025): desechable equivalente por
-- el factor de quiebre.
with sim as (
    select * from {{ ref('int_sim_planta') }}
),

peor as (
    select * from {{ ref('int_sim_peor_inicio') }}
),

mediana as (
    select
        escenario,
        planta,
        tipo_material,
        count(*)                                        as inicios,
        median(faltante)                                as faltante_mediana,
        median(flota_falta)                             as flota_falta_mediana
    from sim
    group by all
),

quiebre as (
    select tipo_material, desechable_equiv_usd * factor_costo_quiebre as costo_quiebre_usd
    from {{ ref('parametros_flota') }}
),

salidas as (
    select m.planta, m.tipo_material, sum(abs(m.cantidad)) as salidas
    from {{ ref('stg_mb51') }} m
    join {{ ref('clases_movimiento') }} c on c.bwart = m.mov_type
    where c.evento = 'salida_cliente'
    group by all
)

select
    p.escenario,
    p.planta,
    p.tipo_material,
    p.paro_dias,
    cast(m.inicios as bigint)                           as inicios,
    p.inicio_paro                                       as inicio_peor,
    p.salida_media_lavado,
    p.capacidad_lavado,
    p.salida_media_reparacion,
    p.capacidad_reparacion,
    cast(round(p.faltante) as bigint)                   as faltante,
    cast(round(m.faltante_mediana) as bigint)           as faltante_mediana,
    round(p.faltante * q.costo_quiebre_usd, 2)          as faltante_usd,
    round(m.faltante_mediana * q.costo_quiebre_usd, 2)  as faltante_mediana_usd,
    round(100 * p.faltante / s.salidas, 4)              as faltante_pct_salidas,
    cast(p.dias_con_faltante as bigint)                 as dias_con_faltante,
    cast(p.materiales as bigint)                        as materiales,
    cast(p.materiales_con_faltante as bigint)           as materiales_con_faltante,
    cast(round(p.flota_falta) as bigint)                as flota_falta,
    round(p.flota_falta_usd, 2)                         as flota_falta_usd,
    cast(round(m.flota_falta_mediana) as bigint)        as flota_falta_mediana,
    cast(round(p.flota_sobra) as bigint)                as flota_sobra,
    round(p.flota_sobra_usd, 2)                         as flota_sobra_usd,
    round(p.cola_lavado_media, 1)                       as cola_lavado_media,
    cast(round(p.cola_lavado_max) as bigint)            as cola_lavado_max,
    round(p.espera_lavado_dias, 2)                      as espera_lavado_dias,
    round(p.cola_reparacion_media, 1)                   as cola_reparacion_media,
    cast(round(p.cola_reparacion_max) as bigint)        as cola_reparacion_max,
    round(p.espera_reparacion_dias, 2)                  as espera_reparacion_dias
from peor p
join mediana m using (escenario, planta, tipo_material)
join quiebre q using (tipo_material)
left join salidas s using (planta, tipo_material)
