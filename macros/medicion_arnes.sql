-- Tipos de una medición versionada del arnés. El CSV entra como texto: la
-- detección automática cambiaría con el contenido del archivo (ADR-031).
{% macro medicion_arnes(relacion) -%}
select
    nullif(defecto, '')                         as defecto,
    nivel,
    nullif(parametro, '')                       as parametro,
    cast(casos as bigint)                       as casos,
    cast(nullif(detectados, '') as bigint)      as detectados,
    cast(segundos as bigint)                    as segundos,
    tipo,
    medida,
    cast(nullif(valor, '') as double)           as valor,
    cast(nullif(usd_expuesto, '') as double)    as usd_expuesto,
    cast(plantas as bigint)                     as plantas,
    cast(meses as bigint)                       as meses,
    cast(seed as bigint)                        as seed
from {{ relacion }}
{%- endmacro %}
