select
    werks                                           as planta,
    parte,
    matnr                                           as material,
    {{ tipo_material('matnr') }}                    as tipo_material,
    piezas                                          as piezas_por_contenedor
from {{ source('raw', 'raw_instruccion_empaque') }}
