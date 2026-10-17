-- Detección de los defectos ciegos antes y después de escribir sus reglas
-- (ADR-033, ADR-034). Antes: docs/calidad/ciegos_antes.csv, sin regla propia y
-- con el corte inferido del dato. Después: la medición del arnés con las reglas
-- y la fecha de extracción como var. Una fila por ciego y nivel.
with medidas as (
    select 'antes' as fuente, * from {{ ref('stg_ciegos_antes') }}
    union all
    select 'despues', * from {{ ref('stg_impacto_defectos') }}
),

ciegos as (
    select distinct defecto from {{ ref('stg_ciegos_antes') }} where defecto is not null
),

corridas as (
    select fuente, defecto, nivel, max(casos) as casos, max(detectados) as detectados
    from medidas
    where defecto in (select defecto from ciegos)
    group by fuente, defecto, nivel
),

-- Cada medición contra su propio limpio.
movimiento as (
    select
        m.fuente, m.defecto, m.nivel, m.medida,
        -- Cuatro decimales, como mart_impacto_defectos: la misma cifra se publica igual.
        round(100 * (m.valor / nullif(l.valor, 0) - 1), 4) as delta_pct
    from medidas m
    join medidas l
        on l.fuente = m.fuente and l.nivel = 'limpio'
       and l.tipo = 'cifra' and l.medida = m.medida
    where m.tipo = 'cifra' and m.defecto in (select defecto from ciegos)
),

mayor as (
    select fuente, defecto, nivel, medida, delta_pct
    from movimiento
    qualify row_number() over (
        partition by fuente, defecto, nivel
        order by abs(delta_pct) desc nulls first, medida
    ) = 1
),

-- Reglas que reportan algo en la corrida del ciego y no son la suya. El limpio
-- no tiene violaciones: todo lo que aparece lo causó el ciego.
reglas as (
    select defecto, regla from {{ ref('reglas_calidad') }} where defecto is not null
),

otras as (
    select
        m.fuente, m.defecto, m.nivel,
        string_agg(m.medida || ' ' || cast(m.valor as bigint), ', ' order by m.medida) as reglas
    from medidas m
    left join reglas r on r.defecto = m.defecto and r.regla = m.medida
    where m.tipo = 'regla' and m.valor > 0 and r.regla is null
      and m.defecto in (select defecto from ciegos)
    group by m.fuente, m.defecto, m.nivel
)

select
    a.defecto,
    r.regla,
    a.nivel,
    a.casos,
    a.detectados                                            as detectados_antes,
    oa.reglas                                               as otras_reglas_antes,
    d.detectados                                            as detectados_despues,
    round(100.0 * d.detectados / nullif(a.casos, 0), 2)     as pct_detectados_despues,
    od.reglas                                               as otras_reglas_despues,
    ma.medida                                               as cifra_antes,
    ma.delta_pct                                            as delta_pct_antes,
    md.medida                                               as cifra_despues,
    md.delta_pct                                            as delta_pct_despues
from corridas a
left join corridas d on d.fuente = 'despues' and d.defecto = a.defecto and d.nivel = a.nivel
left join reglas r on r.defecto = a.defecto
left join otras oa on oa.fuente = 'antes' and oa.defecto = a.defecto and oa.nivel = a.nivel
left join otras od on od.fuente = 'despues' and od.defecto = a.defecto and od.nivel = a.nivel
left join mayor ma on ma.fuente = 'antes' and ma.defecto = a.defecto and ma.nivel = a.nivel
left join mayor md on md.fuente = 'despues' and md.defecto = a.defecto and md.nivel = a.nivel
where a.fuente = 'antes'
