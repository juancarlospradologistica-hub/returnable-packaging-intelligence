-- Un Rack es herramental dedicado: todas sus partes son del mismo cliente
-- (ADR-016, ADR-017). Dos clientes en un Rack es un error de instrucción o de
-- maestro, no una decisión de empaque.
select i.planta, i.material, count(distinct p.cliente) as clientes
from {{ ref('stg_instruccion_empaque') }} i
join {{ ref('stg_partes') }} p
    on p.planta = i.planta and p.parte = i.parte
where i.tipo_material = 'RACK'
group by i.planta, i.material
having count(distinct p.cliente) > 1
