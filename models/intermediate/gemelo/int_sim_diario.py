# Serie diaria del gemelo (ADR-038) por escenario, planta y tipo de empaque.
# Un escenario con paro se corre con su peor inicio, el que elige
# int_sim_peor_inicio.
from rpi.simulador import correr


def model(dbt, session):
    dbt.config(materialized="table")
    peor = (
        dbt.ref("int_sim_peor_inicio")
        .pl()
        .select("escenario", "planta", "tipo_material", "inicio_paro")
    )
    return correr(
        dbt.ref("int_sim_calendario").pl(),
        dbt.ref("int_sim_lotes").pl(),
        dbt.ref("int_sim_vacios").pl(),
        dbt.ref("stg_maestro_materiales").pl(),
        dbt.ref("escenarios_capacidad").pl(),
        peor=peor,
    )
