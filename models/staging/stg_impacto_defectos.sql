-- Mediciones del arnés con sus tipos (ADR-031, punto 5).
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
from {{ source('calidad', 'impacto_defectos') }}
