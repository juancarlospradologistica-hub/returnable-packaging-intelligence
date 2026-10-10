-- Validación fuera de muestra de la z económica del escenario base (ADR-021,
-- ADR-025). La z se escogió en el tramo de calibración; aquí se estima la
-- necesidad con la ventana de backtest y se cuentan los quiebres en la prueba,
-- las semanas siguientes: días en que el stock en uso del material supera la
-- necesidad, o sea, vacíos en negativo. Falla si un tipo rebasa su objetivo de días con
-- quiebre por más de la tolerancia. Con días de cobertura solos (ADR-017)
-- truena en cualquier dataset.
with est as (
    select v.*, k.dias_cobertura, z.z_servicio, z.objetivo_quiebre
    from {{ ref('int_variabilidad_uso') }} v
    join {{ ref('parametros_flota') }} k using (tipo_material)
    join {{ ref('int_z_economico') }} z
        on z.tipo_material = v.tipo_material and z.escenario = 'base'
    where v.ventana = 'backtest'
),

necesidad as (
    select
        planta,
        material,
        tipo_material,
        objetivo_quiebre,
        {{ necesidad_flota('d_base', 'ciclo_dias', 'sigma_uso', 'd_base', 'z_servicio', 'dias_cobertura') }}
            as necesidad
    from est
),

prueba as (
    select
        n.tipo_material,
        max(n.objetivo_quiebre)                                     as objetivo_quiebre,
        count(*)                                                    as dias,
        count(*) filter (where u.en_uso > n.necesidad)              as dias_quiebre
    from necesidad n
    join {{ ref('int_uso_diario') }} u
        on u.planta = n.planta and u.material = n.material
    cross join {{ ref('int_calendario_necesidad') }} c
    where u.fecha between c.inicio_prueba and c.fin_base
    group by n.tipo_material
)

select
    *,
    round(100.0 * dias_quiebre / dias, 2)                           as pct_quiebre,
    round(100.0 * objetivo_quiebre, 2)                              as pct_objetivo
from prueba
where 100.0 * dias_quiebre / dias > 100.0 * objetivo_quiebre + {{ var('backtest_tolerancia_pp') }}
   or dias = 0
   or objetivo_quiebre is null
