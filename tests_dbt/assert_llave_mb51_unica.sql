-- Werks + Mjahr + Mblnr + Zeile identifica una posición de documento (ADR-011).
select
    planta,
    anio_contable,
    doc_material,
    posicion,
    count(*) as repeticiones
from {{ ref('stg_mb51') }}
group by planta, anio_contable, doc_material, posicion
having count(*) > 1
