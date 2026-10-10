-- Brecha de flota y su costo en USD por planta y material en el escenario
-- base (ADR-016, ADR-025, ADR-026): préstamo con flete, compra al corte y
-- desechable mientras llega la compra. El sobrante que queda después de
-- prestar es capital ocioso. El cálculo vive en int_brecha_escenario.
select * exclude (escenario)
from {{ ref('int_brecha_escenario') }}
where escenario = 'base'
