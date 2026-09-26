-- Saldo de stock especial V por cuenta, en orden de contabilización.
-- 621 suma; 622 y 702 restan. SAP no deja recoger ni dar de baja
-- más de lo que hay en la cuenta.
with movimientos as (
    select
        planta,
        cliente,
        material,
        fecha_contab,
        anio_contable,
        doc_material,
        posicion,
        case mov_type when '621' then abs(cantidad) else -abs(cantidad) end as delta
    from {{ ref('stg_mb51') }}
    where mov_type in ('621', '622', '702')
),

saldo as (
    select
        *,
        sum(delta) over (
            partition by planta, cliente, material
            order by fecha_contab, anio_contable, doc_material, posicion
            rows between unbounded preceding and current row
        ) as saldo
    from movimientos
)

select * from saldo where saldo < 0
