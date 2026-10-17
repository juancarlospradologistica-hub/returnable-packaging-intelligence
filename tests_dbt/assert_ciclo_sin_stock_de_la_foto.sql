-- El ciclo se mide solo con salidas de la ventana (ADR-036). El stock V de la
-- foto no tiene fecha de salida ni documento: si un modelo lo cuenta, sus
-- contenedores pesan en el promedio con cero días o abren un mes que no existe.
-- Aquí una salida de la ventana es un tramo con documento y un ciclo medible,
-- uno cerrado por 622 con días.
with tramos as (
    select * from {{ ref('int_tramos_fifo') }}
),

rotacion as (
    select planta, sum(contenedores_salida) as contenedores
    from {{ ref('mart_rotacion_planta') }}
    group by planta
),

salidas as (
    select planta, sum(cantidad) as contenedores
    from tramos
    where doc_salida is not null
    group by planta
),

completas as (
    select planta, mes from {{ ref('mart_rotacion_planta') }} where cohorte_completa
),

cohortes as (
    select sum(t.cantidad) as contenedores
    from tramos t
    join completas c
        on c.planta = t.planta and c.mes = cast(date_trunc('month', t.fecha_salida) as date)
    where t.tipo_cierre = '622' and t.dias is not null
),

ciclo_ruta as (
    select
        planta,
        cliente,
        round(sum(cantidad * dias) * 1.0 / sum(cantidad), 1) as ciclo
    from tramos
    where tipo_cierre = '622' and dias is not null
    group by planta, cliente
)

select 'rotación cuenta salidas que no son de la ventana' as falla, r.planta as detalle
from rotacion r
left join salidas s on s.planta = r.planta
where r.contenedores <> coalesce(s.contenedores, 0)

union all

select 'cohortes cuentan ciclos sin días', null
from {{ ref('mart_ciclo_cohortes') }} f, cohortes c
where f.nivel = 'flota' and f.contenedores_recogidos <> c.contenedores

union all

select 'ciclo de ruta con ciclos sin días', r.planta || ' ' || r.cliente
from {{ ref('mart_rutas') }} r
join ciclo_ruta c on c.planta = r.planta and c.cliente = r.cliente
where r.ciclo_promedio_dias <> c.ciclo
