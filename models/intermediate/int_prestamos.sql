-- Primer nivel de escalamiento (ADR-016, ADR-025): préstamo de flota entre
-- plantas que tienen el mismo material, por escenario. Primero dentro del
-- país, después entre países, porque cruzar frontera cuesta más flete y
-- trámite. En cada etapa el déficit y el sobrante se reparten en proporción:
-- si el sobrante no alcanza, cada planta recibe la misma fracción de su
-- déficit, y si sobra, cada donante presta la misma fracción de su sobrante.
-- Un material que solo existe en una planta no tiene de quién recibir.
with balance as (
    select * from {{ ref('int_balance_material') }}
),

pais_material as (
    select escenario, material, pais, sum(deficit_pico) as deficit, sum(sobrante) as sobrante
    from balance
    group by escenario, material, pais
),

etapa_pais as (
    select
        b.*,
        b.deficit_pico * least(1, pm.sobrante / nullif(pm.deficit, 0))    as recibido_mismo_pais,
        b.sobrante * least(1, pm.deficit / nullif(pm.sobrante, 0))        as prestado_mismo_pais
    from balance b
    join pais_material pm
        on pm.escenario = b.escenario and pm.material = b.material and pm.pais = b.pais
),

resto as (
    select
        *,
        deficit_pico - coalesce(recibido_mismo_pais, 0)                    as deficit_resto,
        sobrante - coalesce(prestado_mismo_pais, 0)                        as sobrante_resto
    from etapa_pais
),

-- Después de la etapa de país, un país tiene déficit o sobrante, no los dos:
-- lo que se mueve aquí cruza frontera.
material as (
    select escenario, material, sum(deficit_resto) as deficit, sum(sobrante_resto) as sobrante
    from resto
    group by escenario, material
)

select
    r.escenario,
    r.planta,
    r.pais,
    r.material,
    r.tipo_material,
    r.ciclo_dias,
    r.deficit_pico,
    r.sobrante,
    coalesce(r.recibido_mismo_pais, 0)                                      as recibido_mismo_pais,
    coalesce(r.deficit_resto * least(1, m.sobrante / nullif(m.deficit, 0)), 0)
                                                                            as recibido_otro_pais,
    coalesce(r.prestado_mismo_pais, 0)                                      as prestado_mismo_pais,
    coalesce(r.sobrante_resto * least(1, m.deficit / nullif(m.sobrante, 0)), 0)
                                                                            as prestado_otro_pais
from resto r
join material m on m.escenario = r.escenario and m.material = r.material
