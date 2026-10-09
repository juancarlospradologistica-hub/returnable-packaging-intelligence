select
    werks                                           as planta,
    parte,
    kunnr                                           as cliente,
    escenario
from {{ source('raw', 'raw_partes') }}
