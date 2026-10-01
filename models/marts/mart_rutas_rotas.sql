-- Rutas planta × cliente con merma o ciclo fuera de umbral (ADR-012).
-- Los umbrales y el cálculo viven en mart_rutas (ADR-015); aquí solo se filtra.
select
    planta,
    cliente,
    contenedores_salida,
    salidas_conciliadas,
    faltantes,
    tasa_merma_pct,
    ciclo_promedio_dias,
    perdida_acum_usd
from {{ ref('mart_rutas') }}
where ruta_rota
order by perdida_acum_usd desc
