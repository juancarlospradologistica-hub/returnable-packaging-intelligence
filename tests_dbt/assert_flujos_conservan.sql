-- Lo que cambia cada estado en una semana es lo que entró menos lo que salió
-- por los tramos de mart_flujos_semanales (ADR-039). El stock sale de
-- mart_flota_semanal, que se arma de int_stock_diario sin pasar por los
-- flujos. Si un tramo se empareja mal, el anillo dibuja flujos que no
-- existieron y aquí no cuadra.
with flota as (
    select planta, tipo_material, semana,
        sum(vacios) as vacios, sum(linea) as linea, sum(llenos) as llenos,
        sum(sucios) as sucios, sum(reparacion) as reparacion, sum(scrap) as scrap,
        sum(cliente) as cliente, sum(recepcion) as recepcion
    from {{ ref('mart_flota_semanal') }}
    group by planta, tipo_material, semana
),

cambio as (
    select planta, tipo_material, semana, estado,
        stock - lag(stock) over (partition by planta, tipo_material, estado order by semana) as cambio
    from flota
    unpivot (stock for estado in (vacios, linea, llenos, sucios, reparacion, scrap, cliente, recepcion))
),

neto as (
    select planta, tipo_material, semana, estado, sum(contenedores) as neto
    from (
        select planta, tipo_material, semana, destino as estado, contenedores
        from {{ ref('mart_flujos_semanales') }}
        union all
        select planta, tipo_material, semana, origen, -contenedores
        from {{ ref('mart_flujos_semanales') }}
    )
    group by planta, tipo_material, semana, estado
)

select c.planta, c.tipo_material, c.semana, c.estado, c.cambio, n.neto
from cambio c
left join neto n using (planta, tipo_material, semana, estado)
where c.cambio is not null
  and c.cambio <> coalesce(n.neto, 0)
