{#
  Tipo de empaque por prefijo de Matnr. Vive en un solo lugar porque lo usan
  stg_mb51 y stg_stock_inicial. Un extracto real lo sacaría del maestro de
  materiales (MARA), no del código: se cambia aquí y no en cada modelo.
#}
{% macro tipo_material(matnr) -%}
    case
        when {{ matnr }} like 'KLT-%' then 'KLT'
        when {{ matnr }} like 'RCK-%' then 'RACK'
        when {{ matnr }} like 'CTN-%' then 'CARTON'
    end
{%- endmacro %}
