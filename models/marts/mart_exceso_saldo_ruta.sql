-- Exceso de saldo en cliente por ruta planta × cliente y fin de mes (ADR-012).
-- Alerta temprana, no clasificador: el criterio de ruta rota sigue siendo la
-- tasa conciliada de mart_rutas_rotas.
--
-- Un cierre aislado no sirve para comparar rutas: toda la flota sube y baja
-- con el calendario de conciliación. El indicador de la alerta es el exceso
-- de los últimos 3 cierres (un ciclo de conciliación trimestral) sobre el
-- saldo esperado de esos mismos cierres.
with cuenta as (
    select * from {{ ref('int_cuenta_mensual') }}
),

-- Antes de que pase el horizonte de la curva desde el primer movimiento del
-- dataset, el saldo esperado no está completo y el exceso sale sesgado.
horizonte as (
    select
        (select min(fecha_contab) from {{ ref('int_mov_cuenta') }})
        + (select max(edad) from {{ ref('int_supervivencia_retorno') }}) as fecha_minima
),

ruta as (
    select
        planta,
        cliente,
        mes,
        fin_mes,
        cast(sum(saldo_fin_mes) as bigint)                  as saldo_fin_mes,
        sum(saldo_esperado)                                 as saldo_esperado
    from cuenta
    group by planta, cliente, mes, fin_mes
),

ventana as (
    select
        *,
        sum(saldo_fin_mes - saldo_esperado) over w         as exceso_ventana,
        sum(saldo_esperado) over w                          as esperado_ventana,
        count(*) over w                                     as cierres_en_ventana,
        min(fin_mes) over w                                 as primer_cierre
    from ruta
    window w as (
        partition by planta, cliente
        order by mes
        rows between 2 preceding and current row
    )
)

select
    v.planta,
    v.cliente,
    v.mes,
    v.saldo_fin_mes,
    round(v.saldo_esperado, 1)                              as saldo_esperado,
    round(v.saldo_fin_mes - v.saldo_esperado, 1)            as exceso_saldo,
    round((v.saldo_fin_mes - v.saldo_esperado) * 100.0
        / nullif(v.saldo_esperado, 0), 2)                   as exceso_pct,
    round(v.exceso_ventana * 100.0
        / nullif(v.esperado_ventana, 0), 2)                 as exceso_pct_ciclo,
    v.cierres_en_ventana = 3
        and v.primer_cierre >= h.fecha_minima               as alerta_valida
from ventana v
cross join horizonte h
