-- Brecha de flota y su costo en USD por planta y material (ADR-016, ADR-025),
-- con los tres niveles de escalamiento en orden:
--   1. préstamo entre plantas (int_prestamos), con flete por contenedor;
--   2. compra al corte de lo que el préstamo no cubre, en contenedores enteros;
--   3. desechable en las semanas en que la compra todavía no llega: cada
--      contenedor que falta deja de hacer 7 / ciclo viajes a la semana.
-- Lo que sobra después de prestar es capital ocioso, a costo unitario.
-- Costos de int_tco_por_material (ADR-010); política de parametros_flota.
with prestamos as (
    select * from {{ ref('int_prestamos') }}
),

costos as (
    select planta, tipo_material, costo_unitario_usd, desechable_equiv_usd
    from {{ ref('int_tco_por_material') }}
),

semanal as (
    select
        s.planta,
        s.material,
        s.necesidad - s.flota_proyectada                                    as deficit,
        row_number() over (partition by s.planta, s.material order by s.semana) as n_semana
    from {{ ref('int_flota_proyectada') }} s
),

-- Viajes que van en desechable mientras llega la compra: déficit de la
-- semana menos lo recibido en préstamo, que llega antes de la semana 1.
desechable as (
    select
        p.planta,
        p.material,
        sum(
            greatest(s.deficit - p.recibido_mismo_pais - p.recibido_otro_pais, 0)
            * 7 / p.ciclo_dias
        ) filter (where s.n_semana <= k.lead_time_semanas)                   as viajes_desechable
    from prestamos p
    join semanal s on s.planta = p.planta and s.material = p.material
    join {{ ref('parametros_flota') }} k on k.tipo_material = p.tipo_material
    group by p.planta, p.material
),

calculo as (
    select
        p.*,
        k.lead_time_semanas,
        c.costo_unitario_usd,
        c.desechable_equiv_usd,
        k.flete_mismo_pais_pct,
        k.flete_otro_pais_pct,
        -- Se compran contenedores enteros; el épsilon evita comprar uno por
        -- redondeo cuando el préstamo cubre el déficit exacto.
        cast(ceil(greatest(
            p.deficit_pico - p.recibido_mismo_pais - p.recibido_otro_pais - 1e-6, 0
        )) as bigint)                                                       as compra,
        coalesce(d.viajes_desechable, 0)                                    as viajes_desechable,
        p.sobrante - p.prestado_mismo_pais - p.prestado_otro_pais           as sobrante_final
    from prestamos p
    join costos c on c.planta = p.planta and c.tipo_material = p.tipo_material
    join {{ ref('parametros_flota') }} k on k.tipo_material = p.tipo_material
    left join desechable d on d.planta = p.planta and d.material = p.material
)

select
    planta,
    pais,
    material,
    tipo_material,
    round(deficit_pico, 1)                                                  as deficit_pico,
    round(sobrante, 1)                                                      as sobrante,
    round(recibido_mismo_pais, 1)                                           as recibido_mismo_pais,
    round(recibido_otro_pais, 1)                                            as recibido_otro_pais,
    round(prestado_mismo_pais, 1)                                           as prestado_mismo_pais,
    round(prestado_otro_pais, 1)                                            as prestado_otro_pais,
    compra,
    round(viajes_desechable, 1)                                             as viajes_desechable,
    round(sobrante_final, 1)                                                as sobrante_final,
    round(
        costo_unitario_usd * (recibido_mismo_pais * flete_mismo_pais_pct
                              + recibido_otro_pais * flete_otro_pais_pct) / 100, 2
    )                                                                       as usd_flete,
    round(cast(compra * costo_unitario_usd as double), 2)                   as usd_compra,
    round(viajes_desechable * desechable_equiv_usd, 2)                      as usd_desechable,
    round(sobrante_final * costo_unitario_usd, 2)                           as usd_capital_ocioso
from calculo
