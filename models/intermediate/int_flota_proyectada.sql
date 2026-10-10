-- Flota disponible al cierre de cada semana del plan (ADR-025). No depende
-- del escenario: la necesidad cambia con la z, la flota no. Parte de la flota
-- al corte y le quita:
--   merma pendiente: contenedores ya perdidos en cliente que la conciliación
--     todavía no registra (salidas posteriores a la última ventana conciliada
--     por la tasa de su ruta). Hoy cuentan como stock V y no existen.
--   pérdida por viaje del plan: merma conciliada más scrap, por planta y tipo.
-- Es valor esperado: la flota proyectada lleva decimales.
with cal as (
    select * from {{ ref('int_calendario_necesidad') }}
),

clases as (
    select * from {{ ref('clases_movimiento') }}
),

ultima_conciliacion as (
    select max(m.fecha_contab) as fecha
    from {{ ref('stg_mb51') }} m
    join clases c on c.bwart = m.mov_type
    where c.evento = 'faltante_cliente'
),

-- Merma conciliada por planta y tipo: respaldo de las rutas sin tasa propia
-- y tasa por viaje del plan.
merma_tipo as (
    select planta, tipo_material, tasa_merma_pct / 100 as tasa
    from {{ ref('mart_tco_comparativo') }}
),

pendiente as (
    select
        m.planta,
        m.material,
        sum(abs(m.cantidad) * coalesce(r.tasa_merma_pct / 100, t.tasa))    as merma_pendiente
    from {{ ref('stg_mb51') }} m
    join clases c on c.bwart = m.mov_type
    cross join ultima_conciliacion u
    left join {{ ref('mart_rutas') }} r
        on r.planta = m.planta and r.cliente = m.cliente
    left join merma_tipo t
        on t.planta = m.planta and t.tipo_material = m.tipo_material
    where c.evento = 'salida_cliente'
      and m.fecha_contab > u.fecha - {{ var('antiguedad_conciliacion_dias') }}
    group by m.planta, m.material
),

-- Scrap por viaje en la misma ventana que la variabilidad: entradas a scrap
-- entre salidas a cliente.
scrap_tipo as (
    select
        s.planta,
        s.tipo_material,
        coalesce(sum(s.delta) filter (where s.estado = 'scrap'), 0)
            / nullif(sum(s.delta) filter (where s.estado = 'cliente'), 0)   as tasa
    from {{ ref('int_mov_stock') }} s
    cross join cal
    where s.fecha between cal.inicio_sigma and cal.fin_base
      and (
          (s.estado = 'scrap' and s.evento = 'traslado_bloqueado' and s.delta > 0)
          or (s.estado = 'cliente' and s.evento = 'salida_cliente')
      )
    group by s.planta, s.tipo_material
),

flota as (
    select planta, material, tipo_material, flota
    from {{ ref('mart_flota_semanal') }}, cal
    where fecha_cierre = cal.corte
),

demanda as (
    select * from {{ ref('int_demanda_plan') }}
),

semanas as (
    select distinct semana from demanda
),

-- Un material con flota y sin plan necesita cero: todo lo que tiene sobra.
base as (
    select f.planta, f.material, f.tipo_material, f.flota, s.semana
    from flota f
    cross join semanas s
)

select
    b.planta,
    b.material,
    b.tipo_material,
    b.semana,
    coalesce(n.d_plan, 0)                                               as d_plan,
    n.ciclo_dias,
    b.flota                                                             as flota_corte,
    round(coalesce(p.merma_pendiente, 0), 2)                            as merma_pendiente,
    round(sum(coalesce(n.d_plan, 0) * 7 * (t.tasa + coalesce(k.tasa, 0))) over (
        partition by b.planta, b.material
        order by b.semana
        rows between unbounded preceding and current row
    ), 2)                                                               as perdida_acumulada,
    round(
        b.flota - coalesce(p.merma_pendiente, 0)
        - sum(coalesce(n.d_plan, 0) * 7 * (t.tasa + coalesce(k.tasa, 0))) over (
            partition by b.planta, b.material
            order by b.semana
            rows between unbounded preceding and current row
        ), 2)                                                           as flota_proyectada
from base b
left join demanda n
    on n.planta = b.planta and n.material = b.material and n.semana = b.semana
left join pendiente p
    on p.planta = b.planta and p.material = b.material
join merma_tipo t
    on t.planta = b.planta and t.tipo_material = b.tipo_material
left join scrap_tipo k
    on k.planta = b.planta and k.tipo_material = b.tipo_material
