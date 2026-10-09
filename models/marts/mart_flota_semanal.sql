-- Flota por planta y material al cierre de cada semana, repartida por estado.
-- Semana de lunes a domingo, igual que el plan de producción. La semana 0
-- cierra el día de la foto inicial; la última, en el corte. Densa: un material
-- sin movimiento en la semana repite su saldo, y un estado vacío va en cero.
-- Ancho y no largo: 3b y el dashboard leen una fila por material y semana, y
-- la conservación se valida fila por fila (ADR-020).
with diario as (
    select * from {{ ref('int_stock_diario') }}
),

limites as (
    select min(fecha) as apertura, max(fecha) as corte from diario
),

semanas as (
    select
        cast(s.semana as date)                                      as semana,
        least(cast(s.semana as date) + 6, l.corte)                  as fecha_cierre
    from limites l,
        unnest(generate_series(
            date_trunc('week', l.apertura),
            date_trunc('week', l.corte),
            interval 1 week
        )) as s(semana)
),

materiales as (
    select distinct planta, material, tipo_material from diario
),

-- Un estado nuevo en el seed almacenes necesita su columna aquí y en flota;
-- si falta, assert_conservacion_flota truena.
por_semana as (
    select
        planta,
        material,
        cast(date_trunc('week', fecha) as date)                     as semana,
        sum(delta) filter (where estado = 'recepcion')              as recepcion,
        sum(delta) filter (where estado = 'vacios')                 as vacios,
        sum(delta) filter (where estado = 'linea')                  as linea,
        sum(delta) filter (where estado = 'llenos')                 as llenos,
        sum(delta) filter (where estado = 'sucios')                 as sucios,
        sum(delta) filter (where estado = 'reparacion')             as reparacion,
        sum(delta) filter (where estado = 'scrap')                  as scrap,
        sum(delta) filter (where estado = 'cliente')                as cliente,
        sum(delta) filter (where tipo_stock = 'bloqueado')          as bloqueado
    from diario
    group by planta, material, date_trunc('week', fecha)
),

acumulado as (
    select
        m.planta,
        m.material,
        m.tipo_material,
        s.semana,
        s.fecha_cierre,
        {% for estado in ['recepcion', 'vacios', 'linea', 'llenos', 'sucios', 'reparacion', 'scrap', 'cliente', 'bloqueado'] -%}
        cast(sum(coalesce(p.{{ estado }}, 0)) over w as bigint)    as {{ estado }},
        {% endfor -%}
    from materiales m
    cross join semanas s
    left join por_semana p
        on  p.planta = m.planta
        and p.material = m.material
        and p.semana = s.semana
    window w as (
        partition by m.planta, m.material
        order by s.semana
        rows between unbounded preceding and current row
    )
)

select
    *,
    recepcion + vacios + linea + llenos + sucios + reparacion + scrap   as en_planta,
    recepcion + vacios + linea + llenos + sucios + reparacion + scrap
        + cliente                                                       as flota
from acumulado
