{#
  Contenedores que necesita un material (ADR-021): uso por ley de Little más
  stock de seguridad. El stock de seguridad es el mayor entre el piso de días de
  cobertura y z por la variabilidad del stock en uso, escalada con la raíz del
  volumen: lo medido entre materiales crece como Poisson, no en proporción.
  Sin base histórica (d_base en cero o nulo) queda solo el piso.
  Lo usan mart_necesidad_flota y el backtest: misma fórmula en los dos.
#}
{% macro stock_seguridad(d_plan, sigma, d_base, z, dias_cobertura) -%}
    greatest(
        {{ dias_cobertura }} * {{ d_plan }},
        coalesce({{ z }} * {{ sigma }} * sqrt({{ d_plan }} / nullif({{ d_base }}, 0)), 0)
    )
{%- endmacro %}

{% macro necesidad_flota(d_plan, ciclo, sigma, d_base, z, dias_cobertura) -%}
    ({{ d_plan }} * {{ ciclo }} + {{ stock_seguridad(d_plan, sigma, d_base, z, dias_cobertura) }})
{%- endmacro %}
