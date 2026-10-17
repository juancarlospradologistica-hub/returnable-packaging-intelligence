-- Fecha de extracción del MB51 (ADR-034). Es dato de entrada, no se calcula:
-- con max(Budat), una sola línea contabilizada después del corte corre todo el
-- calendario de necesidad, flota y saldos.
{% macro fecha_extraccion() -%}
    cast('{{ var("fecha_extraccion") }}' as date)
{%- endmacro %}
