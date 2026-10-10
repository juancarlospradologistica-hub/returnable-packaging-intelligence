-- Los flujos de la red suman lo que cada planta recibe y presta en el
-- escenario base, por tipo de empaque y etapa.
with p as (
    select * from {{ ref('int_prestamos') }} where escenario = 'base'
),

red as (
    select * from {{ ref('mart_red_prestamos') }}
),

esperado as (
    select planta, tipo_material, 'mismo_pais' as etapa,
           sum(recibido_mismo_pais) as recibido, sum(prestado_mismo_pais) as prestado
    from p group by planta, tipo_material
    union all
    select planta, tipo_material, 'otro_pais',
           sum(recibido_otro_pais), sum(prestado_otro_pais)
    from p group by planta, tipo_material
),

recibido as (
    select planta_destino as planta, tipo_material, etapa, sum(contenedores) as recibido
    from red group by planta_destino, tipo_material, etapa
),

prestado as (
    select planta_origen as planta, tipo_material, etapa, sum(contenedores) as prestado
    from red group by planta_origen, tipo_material, etapa
)

select e.*, r.recibido as red_recibido, d.prestado as red_prestado
from esperado e
left join recibido r using (planta, tipo_material, etapa)
left join prestado d using (planta, tipo_material, etapa)
where abs(e.recibido - coalesce(r.recibido, 0)) > 0.5
   or abs(e.prestado - coalesce(d.prestado, 0)) > 0.5
