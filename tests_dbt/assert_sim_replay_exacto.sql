-- Con capacidad sin límite el gemelo reproduce el MB51 (ADR-038, punto 3):
-- vacíos igual a la traza todos los días, sin cola ni desechable, y la flota
-- que sobra igual a lo más bajo que llegó vacíos en int_stock_diario. Las
-- dos referencias se calculan aquí, sin pasar por el simulador.
with traza as (
    select planta, tipo_material, fecha,
        sum(sum(delta)) over (partition by planta, tipo_material order by fecha) as vacios
    from {{ ref('int_stock_diario') }}
    where estado = 'vacios'
    group by planta, tipo_material, fecha
),

diario as (
    select * from {{ ref('mart_sim_vacios_diario') }} where escenario = 'replay'
),

dia_a_dia as (
    select 'vacios distinto a la traza' as falla, d.planta, d.tipo_material, d.fecha
    from diario d
    asof left join traza t
        on t.planta = d.planta and t.tipo_material = d.tipo_material and t.fecha <= d.fecha
    where d.vacios <> coalesce(t.vacios, 0)
       or d.vacios_replay <> coalesce(t.vacios, 0)
       or d.faltante <> 0
       or d.cola_lavado <> 0
       or d.cola_reparacion <> 0
),

apertura as (
    select min(fecha) as inicio from {{ ref('int_sim_calendario') }}
),

minimo as (
    select
        s.planta,
        s.tipo_material,
        s.material,
        -- Antes de su primer movimiento un material sin foto está en cero.
        least(min(s.saldo), case when min(s.fecha) > any_value(a.inicio) then 0 end) as minimo
    from {{ ref('int_stock_diario') }} s, apertura a
    where s.estado = 'vacios'
    group by s.planta, s.tipo_material, s.material
),

sobra as (
    select planta, tipo_material, sum(greatest(minimo, 0)) as sobra
    from minimo
    group by all
)

select * from dia_a_dia
union all
select 'flota que sobra distinta', c.planta, c.tipo_material, null
from {{ ref('mart_sim_capacidad') }} c
join sobra s using (planta, tipo_material)
where c.escenario = 'replay'
  and (c.flota_sobra <> s.sobra or c.faltante <> 0 or c.flota_falta <> 0)
