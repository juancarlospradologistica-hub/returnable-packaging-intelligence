-- La brecha de flota en cada escenario de escenarios_brecha, por tipo de
-- empaque (ADR-026). Mismo cálculo que el escenario base: lo que cambia es la
-- z, por el costo de quiebre, el costo de capital o una z fija. El flete se
-- mueve lineal con su porcentaje y se calcula en el notebook sobre
-- mart_brecha_flota.
with brecha as (
    select * from {{ ref('int_brecha_escenario') }}
),

primera_semana as (
    select n.escenario, n.tipo_material, sum(n.necesidad) as necesidad_semana_1
    from {{ ref('int_necesidad_escenario') }} n
    where n.semana = (select min(semana) from {{ ref('int_necesidad_escenario') }})
    group by n.escenario, n.tipo_material
),

por_tipo as (
    select
        escenario,
        tipo_material,
        count(*) filter (where deficit_pico > 0)                            as materiales_deficit,
        sum(deficit_pico)                                                   as deficit,
        sum(recibido_mismo_pais)                                            as recibido_mismo_pais,
        sum(recibido_otro_pais)                                             as recibido_otro_pais,
        sum(compra)                                                         as compra,
        sum(viajes_desechable)                                              as viajes_desechable,
        sum(usd_flete)                                                      as usd_flete,
        sum(usd_compra)                                                     as usd_compra,
        sum(usd_desechable)                                                 as usd_desechable,
        sum(sobrante_final)                                                 as sobrante_final,
        sum(usd_capital_ocioso)                                             as usd_capital_ocioso
    from brecha
    group by escenario, tipo_material
)

select
    t.escenario,
    t.tipo_material,
    z.factor_costo_quiebre,
    z.costo_capital_anual_pct,
    z.z_fija,
    z.objetivo_quiebre,
    z.z_servicio,
    cast(s.necesidad_semana_1 as bigint)                                    as necesidad_semana_1,
    cast(t.materiales_deficit as bigint)                                    as materiales_deficit,
    round(t.deficit, 1)                                                     as deficit,
    round(t.recibido_mismo_pais, 1)                                         as recibido_mismo_pais,
    round(t.recibido_otro_pais, 1)                                          as recibido_otro_pais,
    cast(t.compra as bigint)                                                as compra,
    round(t.viajes_desechable, 1)                                           as viajes_desechable,
    round(t.usd_flete, 2)                                                   as usd_flete,
    round(t.usd_compra, 2)                                                  as usd_compra,
    round(t.usd_desechable, 2)                                              as usd_desechable,
    round(t.usd_flete + t.usd_compra + t.usd_desechable, 2)                 as usd_brecha,
    round(t.sobrante_final, 1)                                              as sobrante_final,
    round(t.usd_capital_ocioso, 2)                                          as usd_capital_ocioso
from por_tipo t
join {{ ref('int_z_economico') }} z
    on z.escenario = t.escenario and z.tipo_material = t.tipo_material
join primera_semana s
    on s.escenario = t.escenario and s.tipo_material = t.tipo_material
