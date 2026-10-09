-- Parte en el plan sin instrucción de empaque o sin maestro de partes
-- (ADR-017, reglas de calidad). Sin instrucción no hay empaque al que cargarle
-- la necesidad y la parte desaparece del cálculo sin aviso.
select p.planta, p.parte, i.parte is null as sin_instruccion, m.parte is null as sin_parte
from (select distinct planta, parte from {{ ref('stg_plan_produccion') }}) p
left join {{ ref('stg_instruccion_empaque') }} i
    on i.planta = p.planta and i.parte = p.parte
left join {{ ref('stg_partes') }} m
    on m.planta = p.planta and m.parte = p.parte
where i.parte is null or m.parte is null
