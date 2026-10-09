-- La fórmula de necesidad, con los parámetros del seed, no puede dejar más
-- días con quiebre que el umbral (ADR-021, ADR-023). Necesidad estimada con la
-- ventana de backtest y quiebres contados en las semanas siguientes: días en
-- que el stock en uso del material supera la necesidad, o sea, vacíos en
-- negativo. Con días de cobertura solos (ADR-017) truena en cualquier dataset.
with est as (
    select v.*, k.z_servicio, k.dias_cobertura
    from {{ ref('int_variabilidad_uso') }} v
    join {{ ref('parametros_flota') }} k using (tipo_material)
    where v.ventana = 'backtest'
),

necesidad as (
    select
        planta,
        material,
        tipo_material,
        {{ necesidad_flota('d_base', 'ciclo_dias', 'sigma_uso', 'd_base', 'z_servicio', 'dias_cobertura') }}
            as necesidad
    from est
),

prueba as (
    select
        n.tipo_material,
        count(*)                                                    as dias,
        count(*) filter (where u.en_uso > n.necesidad)              as dias_quiebre
    from necesidad n
    join {{ ref('int_uso_diario') }} u
        on u.planta = n.planta and u.material = n.material
    cross join {{ ref('int_calendario_necesidad') }} c
    where u.fecha between c.inicio_prueba and c.fin_base
    group by n.tipo_material
)

select *, round(100.0 * dias_quiebre / dias, 2) as pct_quiebre
from prueba
where 100.0 * dias_quiebre / dias > {{ var('backtest_quiebre_max_pct') }}
   or dias = 0
