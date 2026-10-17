-- Medición de los ciegos antes de escribir sus reglas (ADR-033), con los
-- mismos tipos que la de impacto. No se vuelve a correr: es el antes.
{{ medicion_arnes(source('calidad', 'ciegos_antes')) }}
