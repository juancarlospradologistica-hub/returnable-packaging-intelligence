-- Cada escenario y tipo de empaque tiene una z de la rejilla, y la económica
-- cumple su objetivo en el tramo de calibración (ADR-025). Una z nula quiere
-- decir que ni 4σ alcanza: la historia es corta o los costos están mal. Una
-- fila repetida duplicaría la necesidad del escenario. Base es lo que publican
-- los marts: no puede traer valores propios.
with z as (
    select * from {{ ref('int_z_economico') }}
)

select escenario, tipo_material, 'fila repetida' as motivo
from z group by escenario, tipo_material having count(*) > 1
union all
select escenario, tipo_material, 'z fuera de la rejilla'
from z where z_servicio is null or z_servicio >= 4.0 or quiebre_calibracion is null
union all
select escenario, tipo_material, 'objetivo inválido o incumplido'
from z
where z_fija is null
  and (objetivo_quiebre <= 0 or objetivo_quiebre >= 1 or quiebre_calibracion > objetivo_quiebre)
union all
select 'base', 'KLT', 'falta el escenario base'
where not exists (select 1 from z where escenario = 'base')
union all
select z.escenario, z.tipo_material, 'base con valores propios'
from z
join {{ ref('parametros_flota') }} k using (tipo_material)
where z.escenario = 'base'
  and (z.z_fija is not null
       or z.ajuste_ciclo_dias <> 0
       or z.factor_costo_quiebre <> k.factor_costo_quiebre
       or z.costo_capital_anual_pct <> k.costo_capital_anual_pct)
