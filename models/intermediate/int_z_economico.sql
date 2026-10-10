-- z por tipo de empaque escogida por costo y no por convención (ADR-025).
-- Nivel de servicio económico (razón crítica): un contenedor de más evita
-- quiebres solo los días en que faltaría, y cuesta capital todos los días.
--   costo de quedarse corto, por contenedor y día: desechable × factor / ciclo
--     (un contenedor hace 1/ciclo viajes al día; sin él, ese viaje va en desechable)
--   costo de pasarse, por contenedor y día: costo unitario × costo de capital / 365
--   objetivo de días con quiebre = 1 − corto / (corto + pasarse)
-- La z es la menor de la rejilla cuyo tramo de calibración no rebasa el
-- objetivo. Se mide contra el stock en uso y no contra la normal: la cola real
-- es más pesada (ADR-021). Sin z que alcance, queda nula y el test truena.
with cal as (
    select * from {{ ref('int_calendario_necesidad') }}
),

calibracion as (
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

objetivo as (
    select
        k.tipo_material,
        k.dias_cobertura,
        c.costo_unitario_usd,
        c.desechable_equiv_usd,
        t.ciclo_dias,
        c.desechable_equiv_usd * k.factor_costo_quiebre / t.ciclo_dias       as costo_corto_dia,
        c.costo_unitario_usd * k.costo_capital_anual_pct / 100 / 365        as costo_exceso_dia
    from {{ ref('parametros_flota') }} k
    join costos c using (tipo_material)
    join ciclo t using (tipo_material)
),

rejilla as (
    select cast(z as double) / 100 as z from range(100, 405, 5) as t(z)
),

dias as (
    select u.planta, u.material, u.en_uso
    from {{ ref('int_uso_diario') }} u
    cross join cal
    where u.fecha between cal.inicio_calibracion and cal.inicio_prueba - 1
),

curva as (
    select
        v.tipo_material,
        r.z,
        avg(case when d.en_uso > {{ necesidad_flota('v.d_base', 'v.ciclo_dias', 'v.sigma_uso', 'v.d_base', 'r.z', 'o.dias_cobertura') }}
            then 1.0 else 0.0 end)                     as quiebre
    from calibracion v
    join objetivo o using (tipo_material)
    join dias d on d.planta = v.planta and d.material = v.material
    cross join rejilla r
    group by v.tipo_material, r.z
),

con_objetivo as (
    select
        o.*,
        o.costo_corto_dia / (o.costo_corto_dia + o.costo_exceso_dia)        as razon_critica,
        1 - o.costo_corto_dia / (o.costo_corto_dia + o.costo_exceso_dia)    as objetivo_quiebre
    from objetivo o
),

escogida as (
    select c.tipo_material, min(c.z) as z_servicio
    from curva c
    join con_objetivo o using (tipo_material)
    where c.quiebre <= o.objetivo_quiebre
    group by c.tipo_material
)

select
    o.tipo_material,
    round(o.ciclo_dias, 2)                              as ciclo_dias,
    o.costo_corto_dia,
    o.costo_exceso_dia,
    round(o.razon_critica, 4)                           as razon_critica,
    round(o.objetivo_quiebre, 4)                        as objetivo_quiebre,
    e.z_servicio,
    c.quiebre                                           as quiebre_calibracion
from con_objetivo o
left join escogida e using (tipo_material)
left join curva c on c.tipo_material = o.tipo_material and c.z = e.z_servicio
