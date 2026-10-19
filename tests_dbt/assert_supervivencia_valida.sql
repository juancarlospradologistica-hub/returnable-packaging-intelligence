-- La probabilidad de seguir en cliente está en [0, 1], nunca sube con la edad
-- y llega a cero en la última: todo lo que regresó, regresó a alguna edad. Un
-- tramo sin días, como el stock V de la foto, la deja arriba de cero (ADR-036).
with curva as (
    select
        *,
        lag(prob_en_cliente) over (
            partition by tipo_material order by edad
        ) as prob_anterior,
        edad = max(edad) over (partition by tipo_material) as es_la_ultima
    from {{ ref('int_supervivencia_retorno') }}
)

select *
from curva
where prob_en_cliente < 0
   or prob_en_cliente > 1
   or prob_en_cliente > prob_anterior + 1e-9
   or (es_la_ultima and prob_en_cliente > 1e-9)
