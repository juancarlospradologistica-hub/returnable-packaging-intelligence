-- El tipo del empaque sale del maestro de la planta (ADR-028).
select
    i.werks                                         as planta,
    i.parte,
    i.matnr                                         as material,
    m.tipo_material,
    i.piezas                                        as piezas_por_contenedor
from {{ source('raw', 'raw_instruccion_empaque') }} i
left join {{ ref('stg_maestro_materiales') }} m
    on m.planta = i.werks and m.material = i.matnr
