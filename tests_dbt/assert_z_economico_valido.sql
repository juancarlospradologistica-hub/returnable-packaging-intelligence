-- Cada tipo de empaque tiene una z de la rejilla que cumple su objetivo en el
-- tramo de calibración, y el objetivo es una proporción (ADR-025). Una z nula
-- quiere decir que ni 4σ alcanza: la historia es corta o los costos están mal.
select *
from {{ ref('int_z_economico') }}
where z_servicio is null
   or z_servicio >= 4.0
   or objetivo_quiebre <= 0
   or objetivo_quiebre >= 1
   or quiebre_calibracion > objetivo_quiebre
