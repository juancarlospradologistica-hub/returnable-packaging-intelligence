-- Insumos del TCO por planta y tipo de material (ADR-011, punto 8).
-- El costo unitario sale del maestro (ADR-028), ponderado por viaje: con un
-- precio por material, el costo por planta y tipo es el de la flota que viaja.
-- Vida útil, mantenimiento y desechable equivalente son política y viven en
-- parametros_flota (ADR-010, ADR-028). El cartón ya no entra: es desechable y
-- sale con 601 (ADR-011, punto 10).
-- Tasa por ventana conciliada (ADR-012): faltantes entre salidas con la
-- antigüedad de conciliación antes de la última conciliación, con la marca de
-- int_merma_conciliable (ADR-036). Viajes: todas las salidas del horizonte.
with flujo as (
    select
        planta,
        tipo_material,
        sum(cantidad_abs) filter (where mov_type = '621')               as viajes,
        sum(cantidad_abs) filter (where mov_type = '621' and en_tasa)   as salidas_conciliadas,
        coalesce(sum(cantidad_abs) filter (where mov_type = '702' and en_tasa), 0) as faltantes,
        coalesce(sum(cantidad_abs * costo_unitario_usd)
            filter (where mov_type = '702'), 0)                         as perdida_reconocida_usd,
        sum(cantidad_abs * costo_unitario_usd) filter (where mov_type = '621')
            / sum(cantidad_abs) filter (where mov_type = '621')         as costo_unitario_usd
    from {{ ref('int_merma_conciliable') }}
    group by planta, tipo_material
),

tasa as (
    select
        *,
        faltantes * 1.0 / nullif(salidas_conciliadas, 0)                as p_merma
    from flujo
)

select
    t.planta,
    t.tipo_material,
    t.viajes,
    t.salidas_conciliadas,
    t.faltantes,
    round(t.p_merma * 100, 3)                                           as tasa_merma_pct,
    t.perdida_reconocida_usd,
    t.costo_unitario_usd,
    p.vida_util_ciclos,
    p.mant_por_ciclo_usd,
    p.desechable_equiv_usd,
    -- Viajes promedio antes de perderse o llegar a la vida útil:
    -- E[vida] = (1 − (1 − p)^V) / p; sin merma, E[vida] = V.
    case
        when coalesce(t.p_merma, 0) = 0 then p.vida_util_ciclos
        else (1 - power(1 - t.p_merma, p.vida_util_ciclos)) / t.p_merma
    end                                                                 as vida_esperada_ciclos
from tasa t
join {{ ref('parametros_flota') }} p on p.tipo_material = t.tipo_material
