-- Ciclo de retorno de cohortes completas, por planta y para la flota.
-- Percentiles ponderados por contenedor sobre la distribución completa de
-- días: un promedio de p90 mensuales no es el p90 (ADR-014).
with cohortes as (
    select planta, mes
    from {{ ref('mart_rotacion_planta') }}
    where cohorte_completa
),

tramos as (
    select
        t.planta,
        t.dias,
        t.cantidad
    from {{ ref('int_tramos_fifo') }} t
    inner join cohortes c
        on c.planta = t.planta
       and c.mes = cast(date_trunc('month', t.fecha_salida) as date)
    where t.tipo_cierre = '622'
),

dias as (
    select
        case when grouping(planta) = 1 then 'flota' else 'planta' end as nivel,
        planta,
        dias,
        sum(cantidad)                                   as cantidad
    from tramos
    group by grouping sets ((planta, dias), (dias))
),

acumulado as (
    select
        *,
        sum(cantidad) over (
            partition by nivel, planta order by dias
            rows between unbounded preceding and current row
        ) * 1.0 / sum(cantidad) over (partition by nivel, planta) as fraccion_acum
    from dias
)

select
    nivel,
    planta,
    cast(sum(cantidad) as bigint)                       as contenedores_recogidos,
    round(sum(cantidad * dias) * 1.0 / sum(cantidad), 1) as ciclo_promedio_dias,
    min(dias) filter (where fraccion_acum >= 0.5)       as ciclo_p50_dias,
    min(dias) filter (where fraccion_acum >= 0.9)       as ciclo_p90_dias
from acumulado
group by nivel, planta
order by nivel, ciclo_promedio_dias desc
