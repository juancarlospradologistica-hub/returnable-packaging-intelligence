-- Un escenario con paro se corre desde cada lunes posible del calendario; uno
-- sin paro, una sola vez y sin inicio (ADR-038, punto 8). El peor inicio es
-- un lunes de la ventana estable y deja al menos tanto desechable como la
-- mediana.
with lunes as (
    select count(*) as n from {{ ref('int_sim_calendario') }} where inicio_paro
),

v as (
    select inicio_estable, fin_base from {{ ref('int_calendario_necesidad') }}
)

select c.escenario, c.planta, c.tipo_material, c.paro_dias, c.inicios, c.inicio_peor
from {{ ref('mart_sim_capacidad') }} c, lunes, v
where (c.paro_dias > 0 and (c.inicios <> lunes.n or c.inicio_peor is null))
   or (c.paro_dias = 0 and (c.inicios <> 1 or c.inicio_peor is not null))
   or isodow(c.inicio_peor) <> 1
   or c.inicio_peor not between v.inicio_estable and v.fin_base
   or c.faltante < c.faltante_mediana
