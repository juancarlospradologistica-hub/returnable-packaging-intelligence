-- Días con quiebre en el tramo de calibración para cada z de la rejilla, por
-- tipo de empaque (ADR-025). Es la curva que traduce un nivel de servicio en
-- z sin pasar por la normal. La usan int_z_economico, sus escenarios y el
-- notebook 04.
with cal as (
    select * from {{ ref('int_calendario_necesidad') }}
),

calibracion as (
    select v.*, k.dias_cobertura
    from {{ ref('int_variabilidad_uso') }} v
    join {{ ref('parametros_flota') }} k using (tipo_material)
    where v.ventana = 'calibracion'
),

rejilla as (
    select cast(z as double) / 100 as z from range(100, 405, 5) as t(z)
),

dias as (
    select u.planta, u.material, u.en_uso
    from {{ ref('int_uso_diario') }} u
    cross join cal
    where u.fecha between cal.inicio_calibracion and cal.inicio_prueba - 1
)

select
    v.tipo_material,
    r.z,
    avg(case when d.en_uso > {{ necesidad_flota('v.d_base', 'v.ciclo_dias', 'v.sigma_uso', 'v.d_base', 'r.z', 'v.dias_cobertura') }}
        then 1.0 else 0.0 end)                                              as quiebre
from calibracion v
join dias d on d.planta = v.planta and d.material = v.material
cross join rejilla r
group by v.tipo_material, r.z
