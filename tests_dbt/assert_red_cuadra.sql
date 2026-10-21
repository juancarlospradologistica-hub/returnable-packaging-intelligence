-- La red por cliente suma los tramos con el cliente del anillo (ADR-039): las
-- dos vistas del dashboard dicen lo mismo de la misma semana.
with red as (
    select planta, tipo_material, semana,
        sum(salidas) as salidas, sum(recogidas) as recogidas, sum(faltante) as faltante
    from {{ ref('mart_red_semanal') }}
    group by planta, tipo_material, semana
),

anillo as (
    select planta, tipo_material, semana,
        sum(contenedores) filter (where destino = 'cliente')                     as salidas,
        sum(contenedores) filter (where origen = 'cliente' and destino = 'sucios')  as recogidas,
        sum(contenedores) filter (where destino = 'faltante')                    as faltante
    from {{ ref('mart_flujos_semanales') }}
    group by planta, tipo_material, semana
)

select planta, tipo_material, semana
from red r
full join anillo a using (planta, tipo_material, semana)
where coalesce(r.salidas, 0) <> coalesce(a.salidas, 0)
   or coalesce(r.recogidas, 0) <> coalesce(a.recogidas, 0)
   or coalesce(r.faltante, 0) <> coalesce(a.faltante, 0)
