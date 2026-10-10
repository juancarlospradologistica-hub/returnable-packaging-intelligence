-- Lo que se presta es lo que se recibe, en cada escenario y etapa: dentro de
-- cada país y material, y entre países por material. Nadie presta más de su
-- sobrante ni recibe más de su déficit, y ninguna planta presta y recibe el
-- mismo material.
with p as (
    select * from {{ ref('int_prestamos') }}
),

por_pais as (
    select escenario, material, pais,
           sum(recibido_mismo_pais) as recibido, sum(prestado_mismo_pais) as prestado
    from p group by escenario, material, pais
),

por_material as (
    select escenario, material,
           sum(recibido_otro_pais) as recibido, sum(prestado_otro_pais) as prestado
    from p group by escenario, material
)

select escenario, 'pais' as etapa, material, pais as planta, recibido, prestado
from por_pais where abs(recibido - prestado) > 1e-6
union all
select escenario, 'otro_pais', material, null, recibido, prestado
from por_material where abs(recibido - prestado) > 1e-6
union all
select escenario, 'planta', material, planta, recibido_mismo_pais + recibido_otro_pais,
       prestado_mismo_pais + prestado_otro_pais
from p
where prestado_mismo_pais + prestado_otro_pais > sobrante + 1e-6
   or recibido_mismo_pais + recibido_otro_pais > deficit_pico + 1e-6
   or (recibido_mismo_pais + recibido_otro_pais > 0
       and prestado_mismo_pais + prestado_otro_pais > 0)
