-- Insumos del TCO por planta y tipo de material (ADR-011, punto 8).
-- Los parámetros de costo viven solo aquí (ADR-010). El cartón ya no entra:
-- es desechable y sale con 601 (ADR-011, punto 10).
with parametros as (
    select 'KLT' as tipo_material,
           25.0  as costo_unitario_usd,
           150   as vida_util_ciclos,
           0.20  as mant_por_ciclo_usd,
           4.50  as desechable_equiv_usd
    union all
    select 'RACK', 180.0, 80, 2.50, 45.0      -- desechable $34–66 (ADR-010)
),

movimientos as (
    select * from {{ ref('stg_mb51') }}
    where mov_type in ('621', '702')
),

ultima_conciliacion as (
    select max(fecha_contab) as fecha
    from movimientos
    where mov_type = '702'
),

-- Tasa por ventana conciliada (ADR-012): faltantes entre salidas con 120 días
-- antes de la última conciliación. Viajes: todas las salidas del horizonte.
flujo as (
    select
        m.planta,
        m.tipo_material,
        sum(abs(m.cantidad)) filter (where m.mov_type = '621')          as viajes,
        sum(abs(m.cantidad)) filter (
            where m.mov_type = '621' and m.fecha_contab <= u.fecha - 120
        )                                                               as salidas_conciliadas,
        coalesce(sum(abs(m.cantidad)) filter (where m.mov_type = '702'), 0) as faltantes,
        coalesce(sum(abs(m.cantidad) * m.costo_usd)
            filter (where m.mov_type = '702'), 0)                       as perdida_reconocida_usd
    from movimientos m
    cross join ultima_conciliacion u
    group by m.planta, m.tipo_material
),

tasa as (
    select
        *,
        faltantes * 1.0 / nullif(salidas_conciliadas, 0)                as p_merma
    from flujo
)

select
    t.planta,
    t.tipo_material,
    t.viajes,
    t.salidas_conciliadas,
    t.faltantes,
    round(t.p_merma * 100, 3)                                           as tasa_merma_pct,
    t.perdida_reconocida_usd,
    p.costo_unitario_usd,
    p.vida_util_ciclos,
    p.mant_por_ciclo_usd,
    p.desechable_equiv_usd,
    -- Viajes promedio antes de perderse o llegar a la vida útil:
    -- E[vida] = (1 − (1 − p)^V) / p; sin merma, E[vida] = V.
    case
        when coalesce(t.p_merma, 0) = 0 then p.vida_util_ciclos
        else (1 - power(1 - t.p_merma, p.vida_util_ciclos)) / t.p_merma
    end                                                                 as vida_esperada_ciclos
from tasa t
join parametros p on p.tipo_material = t.tipo_material
