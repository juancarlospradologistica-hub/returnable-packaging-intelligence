-- Cuánto mueve cada defecto, solo, cada cifra publicada, qué identidad rompe y
-- qué reglas dispara, a la tasa del catálogo y en el techo de su rango
-- (ADR-031, puntos 5 y 6). Lee la medición versionada del arnés; la severidad
-- y las cifras declaradas vienen del seed reglas_calidad, y los tests de este
-- mart revisan que el seed diga lo que el arnés midió.
with medidas as (
    select * from {{ ref('stg_impacto_defectos') }}
),

limpio as (
    select tipo, medida, valor
    from medidas
    where nivel = 'limpio'
),

reglas as (
    select
        regla, defecto, severidad, cifra_afectada,
        string_split(coalesce(cifra_afectada, ''), ' ')    as claves
    from {{ ref('reglas_calidad') }}
    where defecto is not null
)

select
    m.defecto,
    r.regla,
    r.severidad,
    r.cifra_afectada,
    m.nivel,
    m.parametro,
    m.casos,
    m.detectados,
    m.segundos,
    m.tipo,
    m.medida,
    l.valor                                                 as valor_limpio,
    m.valor,
    m.valor - l.valor                                       as delta,
    case when m.tipo = 'cifra'
        then round(100 * (m.valor / nullif(l.valor, 0) - 1), 4)
    end                                                     as delta_pct,
    m.usd_expuesto,
    -- Una cifra que desaparece (el mart queda sin la fila) se movió más que
    -- cualquier materialidad; un pipeline que truena también.
    case m.tipo
        when 'cifra' then coalesce(
            case
                when m.valor is null then l.valor is not null
                -- Sobre el delta redondeado que se publica: 99 contra 100 es
                -- 1% exacto, no 1.0000000000000009%.
                else abs(round(100 * (m.valor / nullif(l.valor, 0) - 1), 4))
                    > {{ var('calidad_materialidad_pct') }}
            end, false)
        when 'identidad' then m.valor > 0
        when 'error' then true
    end                                                     as supera_materialidad,
    case when m.tipo = 'cifra'
        then list_contains(r.claves, 'todas') or list_contains(r.claves, m.medida)
    end                                                     as declarada
from medidas m
left join limpio l on l.tipo = m.tipo and l.medida = m.medida
left join reglas r on r.defecto = m.defecto
where m.nivel <> 'limpio'
