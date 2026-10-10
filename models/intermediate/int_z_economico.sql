-- z por tipo de empaque y escenario, escogida por costo y no por convención
-- (ADR-025, ADR-026). Nivel de servicio económico (razón crítica): un
-- contenedor de más evita quiebres solo los días en que faltaría, y cuesta
-- capital todos los días.
--   costo de quedarse corto, por contenedor y día: desechable × factor / ciclo
--     (un contenedor hace 1/ciclo viajes al día; sin él, ese viaje va en desechable)
--   costo de pasarse, por contenedor y día: costo unitario × costo de capital / 365
--   objetivo de días con quiebre = 1 − corto / (corto + pasarse)
-- La z es la menor de int_curva_z que no rebasa el objetivo. Sin z que
-- alcance queda nula y el test truena. Un escenario con z_fija usa ese valor.
with calibracion as (
    select * from {{ ref('int_variabilidad_uso') }} where ventana = 'calibracion'
),

costos as (
    -- Fuente única de costos: int_tco_por_material (ADR-010).
    select
        tipo_material,
        max(costo_unitario_usd)                         as costo_unitario_usd,
        max(desechable_equiv_usd)                       as desechable_equiv_usd
    from {{ ref('int_tco_por_material') }}
    group by tipo_material
),

ciclo as (
    select tipo_material, sum(uso_promedio) / sum(d_ventana) as ciclo_dias
    from calibracion
    group by tipo_material
),

-- Un valor vacío en el escenario toma el de parametros_flota.
escenarios as (
    select
        e.escenario,
        k.tipo_material,
        coalesce(e.factor_costo_quiebre, k.factor_costo_quiebre)            as factor_costo_quiebre,
        coalesce(e.costo_capital_anual_pct, k.costo_capital_anual_pct)      as costo_capital_anual_pct,
        e.z_fija
    from {{ ref('escenarios_brecha') }} e
    cross join {{ ref('parametros_flota') }} k
),

objetivo as (
    select
        e.*,
        t.ciclo_dias,
        c.desechable_equiv_usd * e.factor_costo_quiebre / t.ciclo_dias       as costo_corto_dia,
        c.costo_unitario_usd * e.costo_capital_anual_pct / 100 / 365        as costo_exceso_dia
    from escenarios e
    join costos c using (tipo_material)
    join ciclo t using (tipo_material)
),

con_objetivo as (
    select
        *,
        costo_corto_dia / (costo_corto_dia + costo_exceso_dia)              as razon_critica,
        1 - costo_corto_dia / (costo_corto_dia + costo_exceso_dia)          as objetivo_quiebre
    from objetivo
),

escogida as (
    select o.escenario, o.tipo_material, min(c.z) as z_economica
    from con_objetivo o
    join {{ ref('int_curva_z') }} c
        on c.tipo_material = o.tipo_material and c.quiebre <= o.objetivo_quiebre
    group by o.escenario, o.tipo_material
)

select
    o.escenario,
    o.tipo_material,
    o.factor_costo_quiebre,
    o.costo_capital_anual_pct,
    o.z_fija,
    round(o.ciclo_dias, 2)                              as ciclo_dias,
    o.costo_corto_dia,
    o.costo_exceso_dia,
    round(o.razon_critica, 4)                           as razon_critica,
    round(o.objetivo_quiebre, 4)                        as objetivo_quiebre,
    coalesce(o.z_fija, e.z_economica)                   as z_servicio,
    c.quiebre                                           as quiebre_calibracion
from con_objetivo o
left join escogida e
    on e.escenario = o.escenario and e.tipo_material = o.tipo_material
left join {{ ref('int_curva_z') }} c
    on c.tipo_material = o.tipo_material
    and abs(c.z - coalesce(o.z_fija, e.z_economica)) < 1e-9
