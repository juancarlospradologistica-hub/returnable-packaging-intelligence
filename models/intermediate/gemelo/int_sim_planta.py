# Gemelo de la red RPL (ADR-038): cada escenario de capacidad por planta, tipo
# de empaque e inicio de paro. La simulación vive en rpi.simulador; aquí solo
# se leen las tablas y se publica el resultado.
from rpi.simulador import correr


def model(dbt, session):
    dbt.config(materialized="table")
    return correr(
        dbt.ref("int_sim_calendario").pl(),
        dbt.ref("int_sim_lotes").pl(),
        dbt.ref("int_sim_vacios").pl(),
        dbt.ref("stg_maestro_materiales").pl(),
        dbt.ref("escenarios_capacidad").pl(),
    )
