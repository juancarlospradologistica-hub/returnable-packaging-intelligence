{#
  Falla si hay violaciones de reglas con la severidad dada. La severidad de
  cada regla vive en el seed reglas_calidad y se lee al correr; dbt fija la
  severidad del test al parsear, por eso hay un test por severidad
  (ADR-028, punto 7). Una fila por regla, planta y material.
#}
{% test calidad_sin_violaciones(model, severidad) %}
select regla, planta, material, count(*) as violaciones
from {{ model }}
where severidad = '{{ severidad }}'
group by regla, planta, material
{% endtest %}
