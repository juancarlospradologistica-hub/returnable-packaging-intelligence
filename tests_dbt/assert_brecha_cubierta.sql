-- Cada déficit queda cubierto por préstamo más compra, sin comprar de más: la
-- compra es el resto redondeado hacia arriba a contenedores enteros. El mart
-- redondea a un decimal cada columna: la suma puede moverse 0.2.
select *
from {{ ref('mart_brecha_flota') }}
where recibido_mismo_pais + recibido_otro_pais + compra < deficit_pico - 0.2
   or recibido_mismo_pais + recibido_otro_pais + compra >= deficit_pico + 1.2
   or compra < 0
   or viajes_desechable < 0
   or sobrante_final < -0.2
