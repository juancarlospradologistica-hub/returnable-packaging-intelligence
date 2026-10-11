-- Maestro de materiales por planta (MARA/MARC/MBEW). Fuente única del tipo de
-- empaque y del costo unitario (ADR-028): el tipo sale del grupo de artículos
-- vía el seed grupos_material, el costo de Verpr entre Peinh. El pipeline
-- reporta en USD: un precio en otra moneda lo para el test de moneda, no se
-- convierte aquí.
select
    m.werks                                         as planta,
    m.matnr                                         as material,
    m.maktx                                         as material_desc,
    m.mtart                                         as tipo_material_sap,
    m.matkl                                         as grupo_articulos,
    g.tipo_material,
    m.meins                                         as unidad,
    m.verpr                                         as precio,
    m.peinh                                         as unidad_precio,
    m.waers                                         as moneda,
    m.verpr / m.peinh                               as costo_unitario_usd
from {{ source('raw', 'raw_maestro_materiales') }} m
left join {{ ref('grupos_material') }} g on g.matkl = m.matkl
