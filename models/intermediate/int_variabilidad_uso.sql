-- Uso promedio, desviación del stock en uso, demanda diaria y ciclo total por
-- material, en dos ventanas con el mismo cálculo (ADR-023):
--   necesidad: la que usa mart_necesidad_flota.
--   backtest:  la que usa assert_backtest_necesidad, antes de su prueba.
-- El ciclo T es por planta y tipo de empaque, por ley de Little: uso promedio
-- entre salidas por día, sumado sobre los materiales. Por material sale ruidoso.
with cal as (
    select * from {{ ref('int_calendario_necesidad') }}
),

ventanas as (
    select 'necesidad' as ventana, inicio_sigma as inicio, fin_base as fin,
           inicio_base as inicio_d, fin_base as fin_d
    from cal
    union all
    select 'backtest', inicio_estimacion, fin_estimacion,
           cast(fin_estimacion - 7 * {{ var('ventana_base_semanas') }} + 1 as date), fin_estimacion
    from cal
),

por_material as (
    select
        v.ventana,
        u.planta,
        u.material,
        u.tipo_material,
        avg(u.en_uso) filter (where u.fecha between v.inicio and v.fin)            as uso_promedio,
        stddev_pop(u.en_uso) filter (where u.fecha between v.inicio and v.fin)     as sigma_uso,
        sum(u.salidas) filter (where u.fecha between v.inicio and v.fin)
            / (v.fin - v.inicio + 1)                                               as d_ventana,
        sum(u.salidas) filter (where u.fecha between v.inicio_d and v.fin_d)
            / (v.fin_d - v.inicio_d + 1)                                           as d_base
    from {{ ref('int_uso_diario') }} u
    cross join ventanas v
    group by v.ventana, u.planta, u.material, u.tipo_material, v.inicio, v.fin, v.inicio_d, v.fin_d
),

ciclo as (
    select
        ventana,
        planta,
        tipo_material,
        sum(uso_promedio) / nullif(sum(d_ventana), 0)    as ciclo_dias
    from por_material
    group by ventana, planta, tipo_material
)

select
    m.ventana,
    m.planta,
    m.material,
    m.tipo_material,
    m.uso_promedio,
    m.sigma_uso,
    m.d_ventana,
    m.d_base,
    c.ciclo_dias
from por_material m
join ciclo c
    on c.ventana = m.ventana and c.planta = m.planta and c.tipo_material = m.tipo_material
