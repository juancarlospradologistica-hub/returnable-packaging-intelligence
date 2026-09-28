-- La fila de flota es única, suma los contenedores de las plantas y ningún
-- nivel tiene p50 mayor que p90.
with ciclo as (
    select * from {{ ref('mart_ciclo_cohortes') }}
),

flota as (
    select * from ciclo where nivel = 'flota'
),

plantas as (
    select sum(contenedores_recogidos) as total from ciclo where nivel = 'planta'
)

select 'flota no es única' as falla
from flota
having count(*) <> 1

union all

select 'flota no cuadra con plantas'
from flota, plantas
where flota.contenedores_recogidos <> plantas.total

union all

select 'p50 mayor que p90'
from ciclo
where ciclo_p50_dias > ciclo_p90_dias
