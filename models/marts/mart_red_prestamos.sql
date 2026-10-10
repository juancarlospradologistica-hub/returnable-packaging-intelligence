-- Flujos de préstamo entre plantas en el escenario base (ADR-026). El reparto
-- es proporcional dentro de cada etapa (int_prestamos), así que cada receptor
-- recibe de cada donante de su pool en proporción a lo que ese donante presta:
--   flujo(donante → receptor) = recibido del receptor × prestado del donante
--                               / total prestado en el pool
-- Pool de la etapa de país: material y país. Pool entre países: material.
with p as (
    select * from {{ ref('int_prestamos') }} where escenario = 'base'
),

costos as (
    select planta, tipo_material, costo_unitario_usd from {{ ref('int_tco_por_material') }}
),

pais as (
    select
        d.planta as planta_origen, d.pais as pais_origen,
        r.planta as planta_destino, r.pais as pais_destino,
        r.material, r.tipo_material, 'mismo_pais' as etapa,
        r.recibido_mismo_pais * d.prestado_mismo_pais
            / sum(d.prestado_mismo_pais) over (partition by r.planta, r.material)  as contenedores
    from p r
    join p d
        on d.material = r.material and d.pais = r.pais and d.prestado_mismo_pais > 0
    where r.recibido_mismo_pais > 0
),

otro_pais as (
    select
        d.planta, d.pais, r.planta, r.pais, r.material, r.tipo_material, 'otro_pais',
        r.recibido_otro_pais * d.prestado_otro_pais
            / sum(d.prestado_otro_pais) over (partition by r.planta, r.material)
    from p r
    join p d
        on d.material = r.material and d.prestado_otro_pais > 0
    where r.recibido_otro_pais > 0
),

flujos as (
    select * from pais
    union all
    select * from otro_pais
)

select
    f.planta_origen,
    f.pais_origen,
    f.planta_destino,
    f.pais_destino,
    f.tipo_material,
    f.etapa,
    count(distinct f.material)                                              as materiales,
    round(sum(f.contenedores), 1)                                           as contenedores,
    round(sum(f.contenedores * c.costo_unitario_usd
        * case f.etapa when 'mismo_pais' then k.flete_mismo_pais_pct
                       else k.flete_otro_pais_pct end) / 100, 2)            as usd_flete
from flujos f
join costos c on c.planta = f.planta_destino and c.tipo_material = f.tipo_material
join {{ ref('parametros_flota') }} k on k.tipo_material = f.tipo_material
group by f.planta_origen, f.pais_origen, f.planta_destino, f.pais_destino, f.tipo_material, f.etapa
