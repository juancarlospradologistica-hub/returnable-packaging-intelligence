select
    werks                                           as planta,
    parte,
    cast(semana as date)                            as semana,
    piezas
from {{ source('raw', 'raw_plan_produccion') }}
