-- Fechas que usan la necesidad de flota y su backtest, en un solo lugar
-- (ADR-023). Todas las ventanas son semanas completas de lunes a domingo y
-- terminan antes de la semana del corte, que está incompleta.
--   base:     las semanas que dan d_base, igual que el plan.
--   sigma:    variabilidad del stock en uso para la necesidad.
--   prueba:   semanas donde se cuentan los quiebres del backtest.
--   estimacion: variabilidad para el backtest, antes de la prueba.
-- Si la foto inicial no trae stock en cliente, el saldo V arranca en cero y
-- tarda semanas en llenarse: ese tramo no entra a ninguna ventana.
with limites as (
    select min(fecha) as apertura, max(fecha) as corte
    from {{ ref('int_stock_diario') }}
),

v_inicial as (
    select count(*) > 0 as hay_stock_v
    from {{ ref('int_mov_stock') }}
    where estado = 'cliente' and evento = 'apertura'
),

base as (
    select
        apertura,
        corte,
        -- Domingo anterior al corte, o el corte si cae en domingo.
        cast(corte - cast(isodow(corte) % 7 as integer) as date)                   as fin_base,
        -- Primer lunes después de la apertura, más el arranque del saldo V.
        cast(date_trunc('week', apertura + 7) as date)
            + case when v.hay_stock_v then 0 else 7 * {{ var('semanas_arranque') }} end
                                                                    as inicio_estable
    from limites, v_inicial v
)

select
    apertura,
    corte,
    inicio_estable,
    fin_base,
    cast(fin_base - 7 * {{ var('ventana_base_semanas') }} + 1 as date)         as inicio_base,
    greatest(
        cast(fin_base - 7 * {{ var('ventana_sigma_semanas') }} + 1 as date),
        inicio_estable
    )                                                                           as inicio_sigma,
    cast(fin_base - 7 * {{ var('backtest_semanas') }} + 1 as date)             as inicio_prueba,
    cast(fin_base - 7 * {{ var('backtest_semanas') }} as date)                 as fin_estimacion,
    greatest(
        cast(fin_base - 7 * ({{ var('backtest_semanas') }} + {{ var('ventana_sigma_semanas') }}) + 1 as date),
        inicio_estable
    )                                                                           as inicio_estimacion
from base
