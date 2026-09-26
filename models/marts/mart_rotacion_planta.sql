-- Ciclo de retorno por planta y mes de salida, con tramos FIFO cerrados por
-- 622 ponderados por cantidad. Una cohorte está completa cuando ya pasó el
-- horizonte de la curva de supervivencia; antes solo se ven los ciclos cortos
-- y el promedio sale bajo.
with tramos as (
    select * from {{ ref('int_tramos_fifo') }}
),

corte as (
    select max(fecha_contab) as fecha_corte from {{ ref('int_mov_cuenta') }}
),

horizonte as (
    select max(edad) as max_edad from {{ ref('int_supervivencia_retorno') }}
),

salidas as (
    select
        planta,
        cast(date_trunc('month', fecha_salida) as date) as mes,
        cast(sum(cantidad) as bigint)                   as contenedores_salida
    from tramos
    group by planta, date_trunc('month', fecha_salida)
),

-- Distribución de días por planta y mes, para percentiles ponderados.
dias as (
    select
        planta,
        cast(date_trunc('month', fecha_salida) as date) as mes,
        dias,
        sum(cantidad)                                   as cantidad
    from tramos
    where tipo_cierre = '622'
    group by planta, date_trunc('month', fecha_salida), dias
),

acumulado as (
    select
        *,
        sum(cantidad) over (
            partition by planta, mes order by dias
            rows between unbounded preceding and current row
        ) * 1.0 / sum(cantidad) over (partition by planta, mes) as fraccion_acum
    from dias
),

ciclo as (
    select
        planta,
        mes,
        cast(sum(cantidad) as bigint)                   as contenedores_recogidos,
        round(sum(cantidad * dias) * 1.0 / sum(cantidad), 1) as ciclo_promedio_dias,
        min(dias) filter (where fraccion_acum >= 0.5)   as ciclo_p50_dias,
        min(dias) filter (where fraccion_acum >= 0.9)   as ciclo_p90_dias
    from acumulado
    group by planta, mes
)

select
    s.planta,
    s.mes,
    s.contenedores_salida,
    coalesce(c.contenedores_recogidos, 0)               as contenedores_recogidos,
    c.ciclo_promedio_dias,
    c.ciclo_p50_dias,
    c.ciclo_p90_dias,
    cast(s.mes + interval 1 month - interval 1 day as date) + h.max_edad
        <= k.fecha_corte                                as cohorte_completa
from salidas s
left join ciclo c
    on c.planta = s.planta and c.mes = s.mes
cross join corte k
cross join horizonte h