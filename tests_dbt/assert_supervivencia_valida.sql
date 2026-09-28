-- La probabilidad de seguir en cliente está en [0, 1] y nunca sube con la edad.
with curva as (
    select
        *,
        lag(prob_en_cliente) over (
            partition by tipo_material order by edad
        ) as prob_anterior
    from {{ ref('int_supervivencia_retorno') }}
)

select *
from curva
where prob_en_cliente < 0
   or prob_en_cliente > 1
   or prob_en_cliente > prob_anterior + 1e-9
