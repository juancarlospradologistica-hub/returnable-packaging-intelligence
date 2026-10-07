# PROYECTO — Returnable Packaging Intelligence

Cerebro interno del proyecto. Todo vive aquí.
Para la vista pública ver `README.md`.

**Repositorio:** `returnable-packaging-intelligence`
**Autor:** Juan Carlos Prado Arias
**Última actualización:** 2026-09-30

---

## Índice

1. [Charter](#1-charter)
2. [Stack](#2-stack)
3. [Decisiones (ADR)](#3-decisiones-adr)
4. [Diccionario de datos](#4-diccionario-de-datos-mb51-sintético)
5. [Roadmap por semanas](#5-roadmap-por-semanas)
6. [Worklog](#6-worklog)
7. [Glosario](#7-glosario)

---

## 1. Charter

### Propósito

Análisis de rotación, ciclo y pérdidas de contenedores retornables en flota multi-planta usando datos MB51 sintéticos. El objetivo es aterrizar en KPIs accionables para un equipo de gobernanza de Returnable Packaging Logistics (RPL): cuánto se pierde en USD, dónde, qué rutas cliente están rotas, qué SKUs se descontrolan primero.

El pipeline se diseña para recibir algún día un extracto MB51 real sin reescribir modelos. Lo que cambia entre empresas (códigos de almacén, clases de movimiento, parámetros de política) vive en seeds, no en el SQL. Ver ADR-017.

### Audiencia

- Equipos de gobernanza de Returnable Packaging Logistics (RPL) en industria automotriz.
- Analistas de master data SAP MM que quieran ver cómo se aterriza MB51 en un pipeline analítico moderno.
- Ingenieros de datos que trabajen con datasets tipo ERP y busquen ejemplos de dbt + Polars + DuckDB.

### Alcance IN — Fase 1

Rotación y pérdidas de contenedores retornables en flota multi-planta usando dataset MB51 sintético (18 meses, 14 plantas, ~1,200 Matnr). Cerrado en semana 8.

### Alcance IN — Fase 2

TCO retornable vs desechable (metal vs cartón + tarima madera). Cuantifica el costo por ciclo, la amortización por tipo de contenedor y el punto de equilibrio frente al desechable equivalente. Cerrado en semana 11.

### Alcance IN — Fase 3 (diseño cerrado, ADR-017)

Necesidad de flota retornable por planta, empaque y semana contra el plan de producción de las 12 semanas posteriores al corte, y costo en USD de la brecha contra la flota real. Incluye el ciclo del empaque dentro de la planta: recepción, vacíos, línea, llenos, sucios, reparación y scrap. Alcance en ADR-016; diseño en ADR-017. 3a en Semanas 16–17, 3b en Semanas 18–19.

### Alcance OUT (roadmap futuro, NO se ejecuta ahora)

- Fase 4: Simulador visual de la red de Returnable Packaging Logistics (RPL) y cuello de botella de lavado y reparación, con replay de movimientos MB51. Arranca solo cuando se cumplan los criterios de ADR-016.
- EDI del cliente (DELFOR/DELJIT), S&OP mensual, HU/EWM y empaque alterno.

### Criterios de completitud

- Repo público con documentación completa y CI verde.
- Pipeline reproducible: `uv sync` + comando único para regenerar dataset y correr todo el stack analítico.
- Notebook narrativo que traduzca KPIs técnicos en cifras de negocio en USD.
- Diagramas Mermaid del dominio y del flujo de datos.
- Contrato de entrada documentado: MB51, foto de stock inicial (MB5B), plan de producción (MD61) e instrucción de empaque. Un extracto real se carga cambiando seeds, no modelos.

### Restricciones

- 100% data sintética. Cero información de empleador (pasada o presente).
- Trabajo en tiempo parcial, sin fecha límite dura.
- Todo en Windows + VS Code + PowerShell.

---

## 2. Stack

### Capa 1 — Esencial (semana 1-2)

- **Python 3.11+**
- **uv** — gestor de entornos y paquetes
- **Polars** — data manipulation
- **DuckDB** — warehouse local
- **Parquet** — persistencia de datos
- **NumPy** — generación sintética
- **Jupyter en VS Code** — notebooks
- **Git + GitHub**
- **Mermaid** — diagramas en Markdown

### Capa 2 — Diferenciador (semana 3-5)

- **dbt-duckdb** — modelado analítico declarativo
- **Pandera** — validación de schemas
- **Ruff** — linter y formatter
- **Pytest** — testing
- **GitHub Actions** — CI/CD

### Capa 3 — Opcional (semana 6+)

- **Prefect 3** — orquestación de pipelines
- **Marimo** — dashboard como notebook reactivo en `.py` (ADR-008)
- **Power BI Desktop** — vista ejecutiva descargable (.pbix)
- **MkDocs Material** — sitio de documentación

### Descartado explícitamente

- **Airflow** — overkill para este scope.
- **Postgres / MySQL** — DuckDB los reemplaza en este scope.
- **Snowflake / BigQuery / Databricks** — no necesarios; portables vía dbt profiles.
- **Pandas** — reemplazado por Polars en todo el pipeline.
- **Kafka / streaming** — este es batch, no streaming.
- **Evidence.dev** — migró a modelo cloud (ADR-008).

---

## 3. Decisiones (ADR)

Cada decisión importante queda registrada con fecha, contexto, alternativas descartadas y consecuencias. Números secuenciales, nunca reutilizar.

### ADR-001 · Polars en lugar de Pandas

- **Fecha:** 2026-09-16
- **Estado:** Accepted
- **Contexto:** El dataset objetivo son ~10M filas de movimientos MB51 sintéticos. Pandas empieza a sufrir a partir de 5M en joins y groupbys.
- **Alternativas evaluadas:**
  - Pandas: familiar y ampliamente usado, pero lento a este volumen en joins y groupbys.
  - Polars: sintaxis moderna, 5-10x más rápido.
  - Dask: distribuido, overkill para un laptop.
- **Decisión:** Polars como default para todo el pipeline.
- **Consecuencias:**
  - Curva de aprendizaje inicial de la sintaxis de Polars.
  - El README documenta la decisión con contexto y alternativas descartadas.

### ADR-002 · DuckDB como warehouse local

- **Fecha:** 2026-09-16
- **Estado:** Accepted
- **Contexto:** Necesitamos ejecutar SQL analítico contra los datos generados sin infraestructura.
- **Alternativas evaluadas:**
  - Postgres local: requiere setup, servicio corriendo.
  - SQLite: no está pensado para analítica.
  - DuckDB: embebido, columnar, un solo archivo.
- **Decisión:** DuckDB como motor SQL local.
- **Consecuencias:** Cero fricción de arranque. Portable a Snowflake/BigQuery vía dbt en el futuro.

### ADR-003 · dbt-duckdb para modelado analítico

- **Fecha:** 2026-09-16
- **Estado:** Accepted
- **Contexto:** dbt es estándar en pipelines analíticos modernos de forma recurrente.
- **Alternativas evaluadas:**
  - SQL puro en scripts: no escala, no hay linaje.
  - dbt-core con adaptador Postgres: implica servicio Postgres.
  - dbt-duckdb: mismo dbt, sin servicio.
- **Decisión:** dbt-duckdb como capa de modelado.
- **Consecuencias:** Documentación y linaje auto-generados.

### ADR-004 · Data 100% sintética, sin data de empleador

- **Fecha:** 2026-09-16
- **Estado:** Accepted
- **Contexto:** El autor tiene acceso a MB51 real por su trabajo pero no puede extraer datos.
- **Alternativas evaluadas:**
  - Anonimizar datos reales: riesgo legal y reputacional inaceptable.
  - Datasets públicos genéricos: no reflejan la estructura MB51.
  - Generar sintéticos con reglas de negocio reales: control total, cero riesgo.
- **Decisión:** Generador sintético parametrizado, disclaimer explícito en README.
- **Consecuencias:** Blindaje profesional. Se puede publicar el generador como package reutilizable.

### ADR-005 · Fase 1 primero (rotación y pérdidas)

- **Fecha:** 2026-09-16
- **Estado:** Accepted
- **Contexto:** El proyecto completo (todo el ciclo end-to-end de packaging) es demasiado grande. Riesgo de nunca terminar.
- **Alternativas evaluadas:**
  - Ejecutar todo el ciclo: muy grande, se estanca.
  - TCO retornable vs desechable: bueno pero requiere datos financieros.
  - Rotación y pérdidas: universal, output en USD, datos SAP puros.
  - Forecast vs MRP: potente pero exige más integración.
- **Decisión:** Fase 1 primero. Otras Fases quedan documentadas como roadmap.
- **Consecuencias:** Un entregable terminado > cinco a medias.

### ADR-006 · PROYECTO.md único como cerebro interno

- **Fecha:** 2026-09-16
- **Estado:** Accepted
- **Contexto:** El autor pierde el hilo entre sesiones cuando hay múltiples documentos.
- **Alternativas evaluadas:**
  - CHARTER + WORKLOG + DECISIONS separados: estándar de industria, más overhead.
  - Todo en README: contamina la cara pública.
  - PROYECTO.md único con 7 secciones: baja fricción, alta consolidación.
- **Decisión:** Un solo PROYECTO.md con índice navegable. README.md separado para la vista pública.
- **Consecuencias:** Menor probabilidad de perder contexto. Un solo archivo que abrir.

### ADR-007 · Matnr por planta: pool global 40% sin límite estricto de 250

- **Fecha:** 2026-09-17
- **Estado:** Accepted
- **Contexto:** El parámetro inicial era 250 Matnr por planta. Al implementar el solape con 40% de pool global (480 de 1,200), cada planta accede a 480 Matnr compartidos, superando el límite de 250.
- **Alternativas evaluadas:**
  - Opción B: reducir global a 10% (~120) y completar con 130 locales para respetar 250 estrictos.
  - Opción A: dejar 480 por planta, más realista para flota global donde contenedores circulan libremente entre sitios.
- **Decisión:** Opción A. Confirmada por conocimiento de dominio RPL del autor.
- **Consecuencias:** matnr_count en PlantConfig actualizado a 480. La descripción del pool en GeneratorConfig refleja el 40% compartido.

### ADR-008 · Marimo en lugar de Evidence.dev para dashboard

- **Fecha:** 2026-09-18
- **Estado:** Accepted
- **Contexto:** Evidence.dev migró a Evidence Studio, modelo cloud con CLI propietario. El flujo asume cuenta en su plataforma y conexión GitHub desde su UI. Incompatible con el requisito de pipeline 100% local reproducible.
- **Alternativas evaluadas:**
  - Evidence.dev: descartado por migración a modelo cloud.
  - Streamlit: ampliamente conocido, pero requiere proceso corriendo; no genera artefacto estático.
  - Marimo: notebooks reactivos en Python, sin Node, sin cloud, exporta a HTML estático o corre como app local.
- **Decisión:** Marimo como capa de dashboard.
- **Consecuencias:** Sin dependencias Node. El dashboard corre con `uv run marimo run` dentro del mismo entorno uv del proyecto.

### ADR-009 · Fase 2: TCO retornable vs desechable (extiende ADR-005)

- **Fecha:** 2026-09-21
- **Estado:** Accepted. Parámetro de Rack y ubicación de parámetros reemplazados por ADR-010.
- **Contexto:** Fase 1 cerrada. El pipeline cubre rotación, pérdidas en USD y ciclo 601→602. La pregunta que queda sin respuesta es cuánto cuesta realmente operar con retornables frente a reemplazarlos con desechables: amortización, mantenimiento y pérdidas por merma consolidados en un solo número por ciclo.
- **Alternativas evaluadas:**
  - Fase 3 (Forecast vs MRP): requiere simular un plan de producción creíble. La complejidad del sintético sube sin que el análisis de packaging gane claridad.
  - Fase 4 (ciclo lavado/reparación): el output es tiempo de inmovilización, no dinero. Extensión válida de Fase 1 pero no cierra el argumento financiero.
  - TCO: usa Costo_usd y mart_perdidas_usd que ya existen. Agrega vida útil y mantenimiento. El output es USD/ciclo y punto de equilibrio, que es lo que justifica o cuestiona la inversión en flota retornable.
- **Decisión:** Fase 2 = TCO retornable vs desechable. Se agrega TcoConfig a config.py y dos modelos dbt nuevos: int_tco_por_material y mart_tco_comparativo.
- **Parámetros iniciales:**
  - KLT: vida útil 150 ciclos, mantenimiento $0.20/ciclo, desechable equivalente $4.50/unidad.
  - Rack: vida útil 80 ciclos, mantenimiento $2.50/ciclo, sin equivalente desechable directo.
  - Cartón: 1 ciclo, $8.00/unidad.
- **Consecuencias:**
  - TcoConfig se agrega a config.py sin modificar GeneratorConfig existente.
  - Los marts de Fase 1 no se tocan; los nuevos se construyen sobre int_ciclo_retorno.
  - El notebook 03_tco_analysis.ipynb cierra el argumento: en cuántos ciclos el retornable recupera su costo y cuánto vale cada punto de merma recuperado.

### ADR-010 · Desechable equivalente del Rack y fuente única de parámetros TCO

- **Fecha:** 2026-09-24
- **Estado:** Accepted. Cifras de Consecuencias actualizadas con la base corregida de ADR-011.
- **Contexto:** ADR-009 dejó el Rack sin equivalente desechable y su ahorro salía null. Además los parámetros TCO quedaron duplicados: TcoConfig en config.py y un CTE hardcodeado en int_tco_por_material.sql. dbt solo lee el SQL; TcoConfig nunca se usó y ya divergía (Rack en None contra $45 en SQL).
- **Alternativas evaluadas:**
  - Dejar Rack sin equivalente: el TCO excluye el tipo con mayor valor por unidad. Se pierde el argumento.
  - Rack a $45 por embarque, armado como kit de un solo uso: caja corrugada triple pared $22 (rango 18–30), tarima de madera $12 (10–20), dunnage interior $8 (5–12), consumibles $3 (1–4). Rango total $34–66. Supuesto: una carga de rack = un embarque desechable.
  - Parámetros en TcoConfig inyectados como dbt vars: una sola fuente en Python, pero acopla generador y dbt.
  - Parámetros solo en el SQL: una sola fuente, visible en el linaje de dbt.
- **Decisión:** Rack desechable equivalente = $45.00. Parámetros TCO solo en el CTE `parametros` de int_tco_por_material.sql. Se elimina TcoConfig.
- **Consecuencias:**
  - Reemplaza el parámetro de Rack de ADR-009.
  - Con la base de Sesión 28: ahorro neto total $41.0M; con el rango $34–66 va de $30.9M a $60.4M. Cada $1 mueve el ahorro del Rack ~$0.9M. El Rack deja de convenir abajo de ~$8.70.
  - Con la base corregida de ADR-011: ahorro neto total $137.5M; con el rango $34–66 el del Rack va de $63.1M a $133.1M y el total de $113.5M a $183.4M. Cada $1 mueve el ahorro del Rack $2.2M, porque ahora se cuentan contenedores y no líneas.
  - El equilibrio del Rack pasa de ~$8.70 a $5.14 por embarque en la flota y $5.55 en la planta con más merma. Baja porque la merma ya no se resta aparte con el conteo inflado por el fan-out 601→602: entra al costo por viaje vía vida esperada con la tasa conciliada, 0.415% por viaje en Rack (ADR-011, punto 8). El piso del rango ($34) queda arriba de los dos.
  - Cambiar un supuesto TCO = editar el CTE y correr dbt.
  - Si una fase futura necesita correr escenarios, migrar a dbt seed o vars con ADR nuevo.

### ADR-011 · Corrección de base: ciclo 621→622, saldo por cuenta y generador reproducible

- **Fecha:** 2026-09-25
- **Estado:** Accepted. Reemplaza el emparejamiento de int_ciclo_retorno, la asignación de Matnr descrita en ADR-007 y el tratamiento de merma en el TCO de ADR-009.
- **Contexto:** Antes de Fase 3 medí generador y modelos con una corrida reducida (2 plantas, 18 meses). Encontré:
  - Solo existen 480 Matnr: los 720 locales nunca se asignan.
  - El join 601→602 por planta + material + cliente hace fan-out y sobrecuenta la merma ~8%.
  - Las pérdidas cuentan líneas y no Menge.
  - Hay 602 con fecha posterior al corte y Mjahr heredado del 601.
  - Mblnr aleatorio con llaves duplicadas.
  - ~9,000 clientes aleatorios por planta.
  - Signos de Menge que no permiten reconstruir stock.
  - date.today() rompe la reproducibilidad.
  
  Además, en SAP estándar 602 es el storno del 601; el retornable con cliente se lleva como stock especial V con 621/622.
- **Alternativas evaluadas:**
  - Construir Fase 3 sobre la base actual y documentar limitaciones: descartado, porque Fase 3 necesita stock y saldo en cliente que hoy no se pueden derivar.
  - Corregir solo el join, emparejando por documento: descartado, porque los contenedores son fungibles y ningún MB51 real permite emparejar salida con retorno por documento.
  - Saldo por cuenta con antigüedad FIFO: elegido, porque es como se concilia en operación y es la base de la flota en cliente de Fase 3.
- **Decisión:**
  1. Ciclo de empaque con 621 (salida a stock especial V), 622 (recogida) y 702 con stock especial V (faltante en conciliación). 601/602 salen del ciclo.
  2. Ciclo, vencido y merma se calculan por saldo planta × cliente × Matnr con antigüedad FIFO. Vencido = saldo con más de 120 días. Merma = faltante reconocido en conciliación.
  3. Métricas en contenedores (Menge), no en líneas.
  4. Signo SAP en Menge: salidas negativas, entradas positivas.
  5. reference_date fija en GeneratorConfig (2026-06-30). Nada se emite después del corte; Mjahr se calcula desde Budat.
  6. Mblnr secuencial por planta y año. Llave Werks + Mjahr + Mblnr + Zeile única, validada con test singular de dbt.
  7. Matnr: 480 globales en todas las plantas + 720 locales repartidos sin repetir entre plantas (51 o 52 por planta). global_matnr_share = 0.40 pasa a GeneratorConfig; matnr_count se elimina de PlantConfig.
  8. TCO: costo por ciclo = costo / E[vida] + mantenimiento, con E[vida] = (1 − (1 − p)^V) / p. La merma no se resta aparte; la pérdida USD de Fase 1 se reporta como KPI propio.
  9. Faker fuera de dependencias. test-paths de dbt a tests_dbt. Sin continue-on-error en la ingesta de CI.
  10. El cartón es desechable: sale con 601 y no genera 622 ni 702. Deja de participar en ciclo, merma y TCO como retornable.
  11. Censura sobre Budat y Cpudt: un documento registrado después del corte no existe a la fecha de extracción.
  12. Traslados 311/411/309 en dos posiciones del mismo documento (sale TR01, entra TR02) con el mismo registro. La suma por Matnr es cero. El volumen pasa de ~15.5M a ~22M filas; ADR-001 no cambia.
  13. El generador escribe un Parquet por planta (data/raw/mb51_<Werks>.parquet) y libera memoria entre plantas. El dataset completo junto no cabe en un laptop de desarrollo. Mblnr sigue siendo único por año en todo el dataset.
- **Supuestos (práctica de industria, sin datos de empleador):**
  - Merma: 0.5% por viaje (rango 0.2–1.0%), ~6% anual de la flota. Tasa heterogénea por cuenta: ~20% de las cuentas concentran ~70% de la merma.
  - Clientes: 40 cuentas globales, de 3 a 8 por planta. Rack dedicado a un cliente; KLT compartido entre los clientes de la planta.
  - Menge por línea: KLT 1–12, Rack 1–4, Cartón 1–6, sesgada a valores bajos. Temporal hasta que un ADR de Fase 3 la derive del plan.
  - Conciliación trimestral (rango mensual a semestral).
- **Consecuencias:**
  - Todas las cifras de Fase 1 y 2 cambian. README, notebooks 01/03 y dashboard se recalculan desde los marts.
  - int_ciclo_retorno se reemplaza por un modelo de saldo por cuenta. mart_rotacion_planta y mart_rutas_rotas se reconstruyen sobre él.
  - El diagrama de estados del README cambia a 621/622.
  - ADR-001 sigue vigente; el volumen se mantiene en el mismo orden.
- **Cifras antes y después:** Sesión 28 (cierre de Fase 2 sobre la base anterior) contra el cierre de Semana 13. 14 plantas, seed 42.

| Métrica | Sesión 28 | Semana 13 | Qué lo mueve |
|---|---:|---:|---|
| Filas MB51 | ~15.5M | 22,970,200 | Traslados en dos posiciones (punto 12) |
| Matnr en uso | 480 | 1,200 | Locales asignados (punto 7) |
| Clientes por planta | ~9,000 | 3 a 8 | Cuentas globales (Supuestos) |
| Pérdida reconocida | $4,822,074 | $2,238,765 | Sin fan-out 601→602, Menge en lugar de líneas, merma por conciliación (puntos 1 a 3, ADR-012) |
| Contenedores perdidos | 72,512 líneas | 45,853 | Menge en lugar de líneas (punto 3) |
| Costo promedio por pérdida | $66.50 | $48.82 | Mezcla Rack/KLT contada en contenedores |
| Tasa de merma de flota | n/d | 0.405% por viaje | Ventana conciliada (ADR-012) |
| Tasa máxima por ruta | 35.29% | 1.77% | Tasa por viaje sobre salidas conciliadas (ADR-012) |
| Ruta con más pérdida | PLNT_MX01 → CUST-5144 | PLNT_US04 → CUST-0014 | Clientes y merma por cuenta |
| Ciclo de flota | ~25 días | 25.6 promedio, p50 25, p90 35 | 621→622 con antigüedad FIFO (ADR-012, ADR-014) |
| Viajes TCO, Rack / KLT | 923,918 / 2,085,975 líneas | 2,186,377 / 12,355,872 contenedores | Menge en lugar de líneas (punto 3) |
| Ahorro por viaje, Rack / KLT | $36.32 / $3.59 | $39.86 / $4.08 | Merma dentro de la vida esperada (punto 8) |
| Ahorro neto | $41.0M | $137.5M | Volumen en contenedores |
| Ahorro neto, Rack / KLT | $33.6M / $7.5M | $87.1M / $50.4M | Volumen en contenedores |
| Payback, Rack / KLT | 5 / 6 | 5 / 6 | Sin cambio |
| Merma en el TCO | $4.77M restados aparte | Dentro de E[vida] | Punto 8 |
| Cartón en el TCO | Línea base (−$57,064) | Fuera | Punto 10 |
| Ahorro total con desechable Rack $34–66 | $30.9M a $60.4M | $113.5M a $183.4M | Volumen en contenedores |
| Equilibrio del Rack | ~$8.70 | $5.14 flota, $5.55 peor planta | Punto 8 (ADR-010, Consecuencias) |
| Tests dbt en CI | 0 (dbt run) | 87 (dbt build) | Punto 9 |

La economía por viaje casi no cambia (Rack +10%, KLT +14%). Lo que se mueve es el volumen, que antes contaba líneas, y dónde se reconoce la merma: la pérdida baja a menos de la mitad porque ya no hay fan-out y solo cuenta el faltante conciliado.

### ADR-012 · Merma por ventana conciliada, exceso de saldo por supervivencia y FIFO solo para ciclo

- **Fecha:** 2026-09-25
- **Estado:** Accepted. Reemplaza la definición de vencido y el cálculo de merma del punto 2 de ADR-011.
- **Contexto:** Antes de escribir los modelos de Semana 13 prototipé el FIFO en DuckDB sobre una corrida reducida (2 plantas, 18 meses, seed 42).
  - El FIFO conserva cantidad: salidas 621 = suma de tramos. El ciclo FIFO de 622 da 25.6 días.
  - Los 702 cierran cantidad con edad FIFO promedio de ~31 días. La cuenta es fungible y con flujo continuo: los 622 posteriores a una pérdida consumen primero el saldo viejo y el faltante se corre hacia salidas recientes.
  - Consecuencia: el saldo vencido >120 días al corte da 0, y la tasa de merma por cohorte FIFO subestima (0.30% contra 0.45% real).
  - Con umbral 5% / 45 días, mart_rutas_rotas queda vacío: la tasa alta por cuenta es 1.75% y todas las rutas ciclan en ~26 días.
  - Una cuenta con saldo −1: un 621 censurado por Cpudt con su 622 vivo.
  - Saldo esperado por Little con ventana de 90 días: con ciclo por cuenta, una ruta sana llega a 9.1% de exceso y una problema a 3.1%. Con ciclo constante por tipo, separa peor que supervivencia en 5 de 8 meses.
- **Alternativas evaluadas:**
  - Vencido FIFO >120 días: no detecta nada en cuentas con flujo continuo, que son casi todas.
  - Emparejar salida y cierre por documento: descartado en ADR-011, los contenedores son fungibles.
  - Saldo esperado por Little (salidas de 90 días × ciclo): supone flujo estable; la variación de salidas cerca del cierre de mes mete ruido del mismo tamaño que la señal.
  - Saldo esperado por curva de supervivencia: cada salida aporta su cantidad por la probabilidad de seguir en cliente a su edad. Es Little día por día, no supone flujo estable y es aditivo entre cuenta, ruta y planta.
- **Decisión:**
  1. FIFO solo para ciclo (tramos cerrados por 622, ponderados por cantidad).
  2. Tasa de merma = Σ702 / Σ621 con Budat ≤ última conciliación − 120 días.
  3. Saldo esperado por cuenta a fin de mes = Σ salidas del día × S(edad). S(edad) es la fracción de contenedores recogidos con 622 cuyo ciclo supera esa edad, por tipo de material. Exceso de saldo = saldo a fin de mes − saldo esperado.
  4. Ruta rota: tasa de merma > 1.0% por viaje o ciclo promedio > 45 días.
  5. mart_perdidas_usd se agrupa por mes de reconocimiento del 702.
  6. El generador no emite 622 ni 702 si su 621 se registra después del corte.
  7. Alerta de exceso en mart_exceso_saldo_ruta: exceso de los últimos 3 cierres entre el esperado de esos cierres, por ruta planta × cliente. El exceso de una ruta rota crece entre conciliaciones y el 702 lo borra en el cierre del mes de conciliación; en ese cierre la ruta rota se ve igual que una sana. Una ventana de 3 cierres, igual al periodo de conciliación, siempre contiene un solo cierre de conciliación y dos con exceso acumulado. Solo cuentan ventanas posteriores al horizonte de la curva (alerta_valida). Sin umbral: ordena rutas, no las clasifica.
  8. Cierre mensual en el último día hábil del mes (lunes a viernes, sin calendario de feriados), no en el último día natural. Los 621 y 622 solo caen en día hábil y S(edad) está en días naturales: un fin de mes en domingo inflaba el exceso de toda la flota +7% y uno en sábado +2.5%, y ese vaivén se confundía con la señal. El test singular assert_cierre_dia_habil valida que el cierre cae de lunes a viernes y dentro de su mes.
- **Supuestos:**
  - Umbral de ruta rota: 1.0% por viaje (rango 0.8–1.5%). Es el tope del rango de industria de ADR-011; la cuenta sana del sintético queda en ~0.19% y la problema en ~1.75%.
  - S(edad) se estima con los 18 meses completos. Un fin de mes antiguo ve recogidas posteriores; aceptable para análisis histórico. En monitoreo en línea se estimaría solo con recogidas anteriores a cada corte.
  - Ventana de la alerta: 3 cierres, igual al periodo de conciliación (rango: el periodo de conciliación vigente). Con 14 plantas y cierre hábil separa rutas rotas del resto en los 12 cierres válidos: rotas con exceso mediano de +4.7% a +6.8%, resto de −1.6% a −0.9%. Con un solo cierre se traslapan en 3 de 12 meses, dos de ellos de conciliación.
- **Consecuencias:**
  - El saldo vencido >120 días deja de ser KPI; el exceso de saldo toma su lugar como alerta de flota fantasma.
  - El exceso es alerta temprana, no clasificador. El criterio de ruta rota sigue siendo la tasa conciliada.
  - Sesgo residual: con cierre hábil las rutas sanas quedan entre −1.6% y −0.9% de exceso (−1.2% en promedio), no en cero. No cambia el orden de la alerta porque pega parejo en la flota, pero el exceso no se lee como merma absoluta. Se revisa en Fase 3.
  - El criterio de ciclo en rutas rotas hoy no dispara: el generador no tiene ciclo heterogéneo por ruta.
  - El dataset cambia completo con el mismo seed: 22,970,200 filas reemplazan la cifra de la Sesión 29.

### ADR-013 · Los marts entregan conteos en BIGINT

- **Fecha:** 2026-09-25
- **Estado:** Accepted
- **Contexto:** En DuckDB, sum() sobre enteros devuelve HUGEINT. Polars no lo maneja, así que dashboard, notebooks y pytest tenían que castear cada columna por su cuenta. Nueve columnas de cuatro marts salían HUGEINT; saldo_fin_mes en mart_exceso_saldo_ruta ya salía BIGINT.
- **Alternativas evaluadas:**
  - Castear en cada consumidor: la regla depende de que nadie la olvide, y un consumidor nuevo la rompe sin avisar.
  - Castear en el mart: una sola vez, en la capa que ya es contrato con los consumidores.
- **Decisión:** Todo conteo en un mart sale como BIGINT. El test singular assert_marts_sin_hugeint falla si alguna columna de un mart sale HUGEINT.
- **Consecuencias:**
  - Los consumidores leen las columnas de los marts sin cast. Si vuelven a sumarlas, sum() sobre BIGINT devuelve HUGEINT otra vez y hay que castear el resultado.
  - BIGINT alcanza de sobra: el conteo más grande del proyecto es del orden de 10^7.
  - Un mart nuevo tiene que agregarse a los depends_on del test para quedar cubierto.

### ADR-014 · Percentiles de ciclo sobre la distribución completa

- **Fecha:** 2026-09-26
- **Estado:** Accepted
- **Contexto:** El dashboard mostraba p50 y p90 de flota y de planta como promedio de los percentiles mensuales de mart_rotacion_planta. Un promedio de percentiles no es un percentil. Con 14 plantas el promedio de p90 mensuales daba 36.4 días; el p90 de la distribución completa es 35. Esa cifra iba a README y notebook.
- **Alternativas evaluadas:**
  - Calcular el percentil en Polars dentro del dashboard y del notebook: la misma lógica escrita dos veces.
  - Columnas nuevas en mart_rotacion_planta: cambia su grano planta × mes.
  - Mart nuevo con grouping sets planta y flota: una sola regla para las dos vistas.
- **Decisión:** mart_ciclo_cohortes con percentiles ponderados por contenedor sobre todos los tramos 622 de cohortes completas, una fila por planta y una de flota. La cohorte completa se toma de mart_rotacion_planta. Lo valida el test singular assert_ciclo_cohortes_cuadra.
- **Consecuencias:**
  - Ciclo de flota: promedio 25.6 días, p50 25, p90 35. Reemplaza el p90 de 36.4.
  - Por planta, p90 de 33 a 39 días.
  - Los percentiles salen en días enteros.
  - Dashboard y notebook leen el ciclo de este mart; mart_rotacion_planta queda para la serie mensual.  

### ADR-015 · mart_rutas como universo de rutas

- **Fecha:** 2026-09-29
- **Estado:** Accepted
- **Contexto:** El KPI "12 de 71" rutas rotas tomaba el numerador de mart_rutas_rotas y el denominador de mart_exceso_saldo_ruta, un mart de grano ruta × mes hecho para la alerta. Si un cambio en la ventana de la alerta dejaba fuera una ruta, el denominador cambiaba sin que nadie tocara la definición de ruta. Además, las rutas sanas no existían en ningún mart con su tasa y su ciclo.
- **Alternativas evaluadas:**
  - Dejar el conteo sobre mart_exceso_saldo_ruta y documentarlo: el denominador sigue dependiendo de la alerta.
  - Contar rutas en el dashboard y el notebook desde stg_mb51: la definición de ruta queda escrita dos veces fuera de dbt.
  - Mart de grano planta × cliente con todas las rutas y la marca de rota: una sola definición de ruta y de umbral.
- **Decisión:** mart_rutas con todas las rutas planta × cliente con salidas 621, su tasa de merma conciliada, ciclo promedio y las marcas rota_por_merma, rota_por_ciclo y ruta_rota. Los umbrales de ADR-012 (punto 4) viven solo ahí. mart_rutas_rotas pasa a ser un filtro de mart_rutas y conserva sus columnas. El test singular assert_rutas_universo falla si mart_rutas tiene rutas duplicadas o si no coincide con las rutas de mart_exceso_saldo_ruta.
- **Consecuencias:**
  - 71 rutas, 12 rotas, 0 por ciclo. Las cifras no cambian.
  - Dashboard y notebook 01 toman el total y las rotas de mart_rutas.
  - count_if() en DuckDB devuelve HUGEINT, igual que sum() sobre enteros: al contar rutas en un consumidor hay que castear.
  - Las rutas sanas quedan disponibles para comparar contra las rotas sin reconstruir la tasa.

### ADR-016 · Alcance de Fase 3 y simulador en Fase 4

- **Fecha:** 2026-09-30
- **Estado:** Accepted. Fija alcance y los insumos de dominio; los valores puntuales y el modelo de datos se deciden en el ADR de diseño de Semana 15.
- **Contexto:** El Charter dejó Fase 3 como "forecast de necesidad de packaging vs plan MRP" sin alcance. Al revisarlo encontré que el generador solo modela el tramo planta ↔ cliente (621/622/702). Dentro de la planta el empaque no tiene estado: los traslados 311 van de TR01 a TR02, almacenes sin significado. Sin almacén de vacíos no hay flota disponible contra la cual comparar la demanda. En paralelo surgió la idea de un simulador visual de la red, con cada paso registrado como movimiento MB51.
- **Alternativas evaluadas:**
  - Cambiar Fase 3 a Data Quality sobre MB51: menor costo, pero el Charter ya comprometía el forecast y es la pregunta que conecta con Fase 1. Queda como candidata para una fase futura.
  - Forecast sin ciclo interno, contra un número de flota fijo: compara demanda contra una cifra sin origen en los datos.
  - Simulador dentro de Fase 3: duplica el alcance y se construiría sobre una base que todavía cambia (ADR-011 a ADR-015 en dos semanas).
- **Decisión:**
  1. Fase 3 contesta: ¿cuántos contenedores necesita cada empaque, por planta y semana, para cubrir el plan de producción, y cuánto cuesta en USD la brecha contra la flota real? La merma de Fase 1 reduce la flota real; ahí se conectan las fases.
  2. Dos bloques. 3a: ciclo interno en el generador (almacenes, 311 entre ellos, lavado, reparación, scrap). 3b: plan de producción, instrucción de empaque, necesidad contra flota y brecha en USD.
  3. Insumos de dominio para el diseño, todos de práctica estándar de la industria:
     - Stock de seguridad: cantidad mínima dentro del almacén de vacíos, sin Lgort propio. Se calcula en días de cobertura.
     - Almacenes del ciclo: recepción de flota nueva, vacíos limpios, línea (PSA), llenos o embarque, sucios por lavar, reparación (stock bloqueado) y scrap pendiente. En cliente sigue el stock especial V.
     - Surtido a línea con 311: el retornable no se consume. El 261 queda solo para el cartón.
     - Contenedor lleno con stock propio, sin HU: el proyecto es MM/IM.
     - Baja con 555 desde stock bloqueado, viniendo de reparación.
     - Plan interno nivelado, semanal, 12 semanas.
     - Una parte, un empaque, cantidad fija por contenedor (instrucción de empaque).
     - Rack dedicado a pocas partes de un cliente; KLT compartido (confirma ADR-011).
     - Escalamiento modelado en tres niveles: préstamo entre plantas, desechable de emergencia y compra de flota.
  4. Fuera de Fase 3: EDI del cliente, S&OP mensual, HU/EWM, empaque alterno, plan diario.
  5. Fase 4: simulador de la red RPL (plantas, clientes y almacenes internos) en modo simulado y en replay de MB51, más el cuello de botella de lavado y reparación. Arranca cuando se cumplan los tres: Fase 3 cerrada; dos semanas seguidas sin ADR que cambie cifras de Fase 1 o 2; test de cuadre del README verde sin tocar cifras. HTML/JS entra al stack con ADR propio en ese momento.
- **Supuestos (práctica de industria, sin datos de empleador):**
  - Lavado: KLT siempre, 1–3 días contando cola y secado. Rack solo inspección y limpieza si está sucio.
  - Reparación por retorno: KLT 1–3%, 1–2 días; Rack 3–8%, 5–15 días.
  - Scrap anual: KLT 0.5–2%; Rack 1–3%.
  - Días de cobertura del stock de seguridad: KLT 3, Rack 5 (rango 2–7).
  - Compra de Rack: 8–16 semanas de lead time.
  - El diseño usa el punto medio de cada rango y el notebook muestra sensibilidad al rango completo.
- **Consecuencias:**
  - 622 sigue como recogida (pedido LA, categoría LAN). El 632 es de consignación (stock especial W), no de empaque retornable. El 623 (el cliente se queda el empaque y se factura) queda fuera de alcance.
  - El generador cambia: almacenes con significado, 311 entre ellos, cambio a stock bloqueado al entrar a reparación y 555 en la baja. El conteo de filas cambia y test_readme.py lo detecta.
  - Si el ciclo interno consume la misma secuencia aleatoria, las cifras de Fase 1 y 2 se mueven. El ADR de diseño decide si usa un generador aleatorio propio para no tocarlas.
  - Fase 3 pasa de un bloque a dos: ~1.5–2 semanas para 3a y ~2 para 3b.

  ### ADR-017 · Diseño de Fase 3: almacenes, plan de producción y flota inicial

- **Fecha:** 2026-09-30
- **Estado:** Accepted. Fija los valores y el modelo de datos que ADR-016 dejó abiertos. Vuelve permanente la Menge por línea de ADR-011: el plan se deriva de los embarques, no al revés.
- **Contexto:** Antes de diseñar corrí el generador con una planta (PLNT_MX01, seed 42; en una corrida de una planta los 720 Matnr locales caen en ella). Encontré:
  - El ruido operativo no conserva stock. Solo el 501 de KLT mete 835,087 contenedores en 18 meses, el 82% de los 1,024,381 que salen con 621 de KLT en la planta. Con almacenes con significado, vacíos quedaría negativo o la flota crecería sola.
  - 47,257 líneas 261 sobre retornables. ADR-016 deja el 261 solo para el cartón.
  - El 702 V lleva Lgort RECP. El stock especial V se lleva por planta, cliente y material (MSKU), sin almacén.
  - Un solo generador aleatorio para las 14 plantas. Hora, minuto y referencia se sortean por fila al final de cada planta: una fila de más en una planta cambia los 621 de todas las siguientes.
  - MB51 no trae el stock con el que arranca la ventana. Sin una foto inicial no hay flota real.
  - El proyecto apunta a recibir algún día un MB51 real, y cada empresa configura sus almacenes y clases de movimiento a su manera.
- **Alternativas evaluadas:**
  - Que el plan genere los 621: cambia todas las cifras de Fase 1 y 2.
  - Mismo generador aleatorio, aceptando cifras nuevas: obliga a recalcular y documentar todo otra vez y rompe el criterio de ADR-016 para arrancar Fase 4.
  - Movimientos internos en un Parquet aparte: en SAP es un solo MB51; parte la numeración de Mblnr y obliga a unir dos fuentes en staging.
  - Un 311 por cada 621: más filas sin más información. Un 311 semanal: borra lavado y reparación de 1 a 3 días. Elegí registro diario por material y tramo, que además es como lo registra un coordinador: conteo al cierre de turno.
  - Daño con 311 a reparación y 344 ahí: el contenedor dañado queda como libre un rato. Elegí 344 donde se detecta y 325 a reparación.
  - Códigos de almacén y de clase de movimiento fijos en el SQL: un MB51 real obligaría a reescribir modelos. Elegí mapeo en seeds.
- **Decisión:**
  1. Siete almacenes: RECF recepción de flota nueva, VACI vacíos limpios (ahí vive el stock de seguridad, sin Lgort propio), LINE línea/PSA, LLEN llenos/embarque, SUCI sucios por lavar e inspección de retorno, todos en libre utilización; REPA reparación y SCRP scrap pendiente, en bloqueado.
  2. Movimientos: 101 con OC entra a RECF. 311 de RECF a VACI, de VACI a LINE, de LINE a LLEN, de SUCI a VACI y de REPA a VACI. 621 sale de LLEN. 622 entra a SUCI. 702 V sin Lgort. Daño: 344 en SUCI y 325 a REPA. Reparado: 343 en REPA y 311 a VACI. Irreparable: 325 a SCRP. Baja: 555 desde SCRP, en lote el último día hábil del mes. 325, 343, 344 y 555 entran a BWART_VALIDOS. Lgort acepta nulo en el schema.
  3. El tipo de stock se deriva de Bwart y signo, sin columna nueva: en 344 la posición positiva es bloqueada, en 343 la negativa; 325 y 555 siempre son bloqueado. Posición 1 sale, posición 2 entra, igual que el 311 de hoy.
  4. Los 311 internos se registran un documento por día, material y tramo. Los modelos no asumen granularidad: calculan stock sumando lo que llegue.
  5. Seeds almacenes.csv (Lgort → estado del ciclo) y clases_movimiento.csv (Bwart → evento). Los modelos de Fase 3 leen estado y evento, no códigos SAP.
  6. Ruido: salen 501, 502 y los 311, 411 y 309 de relleno en todos los materiales, y 101, 102 y 261 en retornables. El cartón conserva 101, 102, 261 y 601. Se filtra después de los sorteos actuales.
  7. Sin 101 históricos para retornables. Tabla stock_inicial con la foto de la fecha de arranque, equivalente a MB5B. Flota inicial por empaque = mínimo que deja vacíos en cero o más durante los 18 meses, más una holgura sorteada por empaque. La merma (702) y el scrap (555) la consumen.
  8. Plan derivado de los 621: embarques semanales por planta, empaque y cliente, repartidos entre partes con pesos fijos; base = promedio de las 13 semanas previas al corte, en piezas; escenario por parte (estable, arranque o fin de serie). Horizonte de 12 semanas, del lunes 2026-07-06 al domingo 2026-09-27, sin feriados. Tres tablas en data/raw: partes, instruccion_empaque y plan_produccion.
  9. emit_plant_movements conserva sus sorteos y su orden. El ciclo interno corre después, con un generador aleatorio propio por planta: default_rng([random_seed, indice_planta, 1]); el plan usa [random_seed, indice_planta, 2]. Las reglas de Lgort (621 desde LLEN, 622 a SUCI, 702 V sin Lgort) no usan azar. Mblnr se asigna al final con un solo rango.
  10. Antes de tocar el generador se guarda la huella (hash) de las filas 621, 622 y 702 ordenadas, con Werks, Matnr, Budat, Cpudt, Menge y Kunnr. test_ciclo_cliente_intacto la compara en cada corrida.
  11. Parámetros que solo existen porque los datos son sintéticos van en config.py. Parámetros de política (días de cobertura, lead time) van en el seed parametros_flota.csv por tipo de empaque.
  12. Necesidad por empaque y semana = d × (ciclo en cliente + ciclo interno) + d × días de cobertura, con d = contenedores por día que pide el plan. El ciclo en cliente usa el promedio, no la mediana: la fórmula es la ley de Little.
- **Supuestos (práctica de industria, sin datos de empleador):** las tasas usan el punto medio del rango; los tiempos se sortean en días enteros dentro del rango.
  - Tiempo en RECF: 3 días (1–5), inspección de entrada.
  - Tiempo en LINE: 1 día (0–2), el surtido cubre uno o dos turnos.
  - Tiempo en LLEN: KLT 1 día, Rack 2 días (0–3), entrega justo a tiempo.
  - Tiempo en SUCI: KLT 2 días de lavado (1–3, ADR-016); Rack 1 día de inspección (0–2).
  - Tiempo en REPA: KLT 1–2 días; Rack 5–15 días (ADR-016).
  - Baja con 555: mensual (rango mensual a trimestral), por aprobación y cierre contable.
  - Reparación por retorno: KLT 2% (1–3%), Rack 5.5% (3–8%) (ADR-016).
  - Scrap anual: KLT 1.25% (0.5–2%), Rack 2% (1–3%) (ADR-016). Con ~12 viajes al año (~31 días de ciclo total) sale ~5% de lo que entra a reparación en KLT y ~3% en Rack.
  - Holgura de flota inicial: 0–30% por empaque, 15% en promedio. Las plantas sobredimensionan la flota en el lanzamiento, y no todas igual.
  - Días de cobertura: KLT 3, Rack 5 (2–7) (ADR-016).
  - Lead time de compra: KLT 4 semanas (2–6), es de catálogo y sin herramental dedicado; Rack 12 semanas (8–16) (ADR-016).
  - Partes por empaque: Rack 2 (1–3), dedicado a un cliente; KLT 5 (3–8), puede cruzar clientes de la planta.
  - Piezas por contenedor: Rack 12 (4–24), KLT 40 (12–120). Se cancelan al pasar de piezas a contenedores: no mueven la necesidad y no llevan sensibilidad.
  - Ventana base del plan: 13 semanas (8–26), un trimestre, igual que la conciliación.
  - Escenario por parte: 80% estable (70–90%); 10% arranque, +30% (+20–50%) desde la semana 4–8; 10% fin de serie, −50% (−30–100%) desde la semana 4–8.
- **Consecuencias:**
  - Las cifras de Fase 1 y 2 no cambian. Si cambian, es un bug y lo detectan la huella, test_readme.py y dbt build.
  - Los Mblnr de las filas existentes cambian; ninguna métrica depende de ellos. Dos 621 del mismo día y la misma cuenta tienen la misma edad: el FIFO da los mismos días en cualquier orden.
  - El conteo de filas cambia. Medido en PLNT_MX01: de 2,048,341 se quedan ~676k, salen ~1.37M de ruido y entran ~1.37M de 311 internos. Estimado para 14 plantas: 20M a 23M filas, el mismo orden de hoy.
  - Sin compras históricas de flota. En una planta real sí las hay; aquí la merma y el scrap quedan a la vista contra la holgura. La reposición entra en 3b como acción de escalamiento.
  - El notebook de Fase 3 muestra sensibilidad a holgura, mezcla de arranque y fin de serie, días de cobertura, lavado de KLT y reparación de Rack.
  - Reglas de calidad de datos para datos reales: parte en el plan sin instrucción de empaque; instrucción que apunta a cartón o a un Matnr fuera de la planta; Rack con partes de más de un cliente; parte con plan sin embarques en las 13 semanas previas; Bwart o Lgort fuera de los seeds.
  - Al cierre de Fase 3 se decide si la fase de calidad de datos sobre MB51 y master data va antes que el simulador de Fase 4.

---

## 4. Diccionario de datos (MB51 sintético)

### Columnas core (16)

| Campo | Descripción | Uso analítico |
|-------|-------------|---------------|
| Werks | Centro (planta) | Filtro base por sitio |
| Lgort | Almacén | Distingue racks piso / tránsito / cuarentena |
| Matnr | Material (código empaque) | Rack, contenedor, KLT |
| Maktx | Texto breve del material | Lectura rápida sin cruzar MAKT |
| Bwart | Clase de movimiento | Separar 621/622 (ciclo con cliente), 702 con stock especial V (faltante), 501/502, 311/411, 101/102, 261, 309 |
| Mjahr / Budat | Año contable y fecha contabilización | Cortes mensuales / semanales |
| Cpudt / Cputm | Fecha y hora de registro en sistema | Auditar registros tardíos |
| Menge + Meins | Cantidad y unidad de medida base | PC normalmente en empaques |
| Mblnr / Zeile | Documento material y posición | Ancla a MIGO / ME23N |
| Lifnr | Proveedor | Retornable con socio (461/462, 501/502) |
| Kunnr | Cliente / consignatario | Cuenta de stock especial V (621/622) |
| Xblnr | Referencia / documento externo | Número embarque, delivery, pedido físico |
| Costo_usd | Costo unitario del empaque en USD | Pérdida y TCO en dinero |

### Columnas extras opcionales (6)

| Campo | Descripción |
|-------|-------------|
| Ebeln / Ebelp | Orden de compra y posición (101/102, 501/502 con PO) |
| Sgtxt | Texto de posición (placas, folios, comentarios) |
| Umwrk / Umlgo | Centro y almacén destino en traslados (301/311) |
| Usnam | Usuario que registró (trazabilidad de errores) |

### Parámetros del generador

- **14 plantas:** 6 México, 6 Estados Unidos, 2 Nicaragua. Nombres genéricos PLNT_XX##.
- **Matnr:** 1,200 únicos. 480 globales en todas las plantas + 720 locales repartidos sin repetir (51 o 52 por planta): 531 o 532 Matnr por planta.
- **Mix por tipo:** 60% KLT plástico, 30% racks metálicos, 10% cartón + tarima madera.
- **Horizonte:** 18 meses con fecha de corte fija 2026-06-30. Nada se emite después del corte.
- **Volumen:** ~40-80k movimientos base por planta/mes; con traslados en pareja y recogidas, ~22M filas totales.
- **Clientes:** 40 cuentas globales, de 3 a 8 por planta. Rack dedicado a un cliente; KLT compartido.
- **Menge por línea:** KLT 1–12, Rack 1–4, Cartón 1–6. Signo SAP: salidas negativas.
- **Ciclo 621→622:** log-normal, media 25 días, cola larga.
- **Merma:** 0.5% por viaje, heterogénea por cuenta (~20% de las cuentas concentran ~70%). Faltante registrado con 702 en conciliación trimestral.
- **Documento:** Mblnr secuencial por planta y año.
- **Lag Cpudt vs Budat:** 92% mismo día, 6% 1-2 días tarde, 2% >48h.
- **Cartón:** desechable, sale con 601 y no regresa.
- **Traslados:** 311/411/309 en dos posiciones del mismo documento, suma cero por Matnr.
- **Salida:** un Parquet por planta en data/raw/ (mb51_<Werks>.parquet). Cada corrida borra los mb51_*.parquet previos del directorio. Pico de memoria ~1.1 GB.

---

## 5. Roadmap por semanas

Marcar con `[x]` al cerrar.

- [x] **Semana 1** · Scaffold del repo, `pyproject.toml`, README v0, PROYECTO.md, schema Pandera de las 22 columnas.
- [x] **Semana 2** · Generador sintético completo, primer dataset Parquet de 18 meses, notebook de sanity check con validación visual.
- [x] **Semana 3** · Ingesta a DuckDB, capa dbt staging con tests.
- [x] **Semana 4** · Modelos dbt intermediate + marts para KPIs de rotación y pérdidas.
- [x] **Semana 5** · Notebook analítico narrativo con storytelling de negocio y cifras en USD.
- [x] **Semana 6** · Dashboard Marimo con KPIs, rutas rotas y ciclo de retorno. (Evidence.dev descartado por ADR-008; Power  BI movido a roadmap futuro.)
- [x] **Semana 7** · CI con GitHub Actions, tests automáticos, badges en README.
- [x] **Semana 8** · Pulido README, generación de diagramas finales.
- [x] **Semana 9** . TcoConfig en config.py, int_tco_por_material.sql, mart_tco_comparativo.sql, YMLs dbt, tres tests nuevos en test_marts.py. CI verde.
- [x] **Semana 10**. Notebook 03_tco_analysis.ipynb: punto de equilibrio por tipo, ahorro neto vs desechable, sensibilidad a tasa de merma.
- [x] **Semana 11** · Dashboard Marimo con pestaña TCO. README con resultados Fase 2. Fase 2 cerrada.
- [x] **Semana 12** · Generador corregido (ADR-011): 621/622/702, reference_date, Mblnr secuencial, clientes, Menge por tipo, merma heterogénea por cuenta, pool de 1,200 Matnr.
- [x] **Semana 13** · Modelos dbt por saldo FIFO, TCO con vida esperada, recálculo de Fase 1 y 2, tabla antes/después en ADR-011, README y notebooks alineados.
- [x] **Semana 14** · Hardening: ruff format y check en CI, mart_rutas como universo de rutas (ADR-015), unit tests de int_tramos_fifo, test de cuadre del README, desempate en el top 15. Alcance de Fase 3 y simulador en Fase 4 (ADR-016).
- [x] **Semana 15** · Diseño de Fase 3: almacenes y movimientos dentro de la planta, plan de producción, instrucción de empaque, flota inicial, parámetros con rango y generadores aleatorios propios (ADR-017).
- [ ] **Semanas 16–17** · Fase 3a: ciclo interno del empaque en el generador.
- [ ] **Semanas 18–19** · Fase 3b: necesidad de flota contra plan, brecha en USD, notebook y dashboard.

---

## 6. Worklog

### 2026-10-05 · Sesión 35 — Semana 16

- **Duración:** ~4 h (4 y 5 de octubre)
- **Hecho:**
  - Branch semana-16-fase-3a y PR #4 en borrador contra main.
  - src/rpi/huella.py: sha256 sobre las filas 621, 622 y 702 ordenadas, por planta, con filas y Menge por Bwart. sha256 sobre el CSV y no hash_rows de Polars, que no es estable entre versiones.
  - Baselines en tests/huella/: completo.json (14 plantas, 18 meses, seed 42) y ci.json (2 plantas, 6 meses, seed 42). Seis meses para que haya 702 en las dos plantas.
  - Generador reproducible en el ciclo con cliente: dos corridas completas dan la misma huella con 22,970,200 filas.
  - tests/test_ciclo_cliente_intacto.py: la corrida reducida llama al CLI con flags fijos, sin depender de cfg_ci. El completo se salta si data/raw no tiene las 14 plantas o si el primer Budat es posterior a enero de 2025. Probado rompiendo la baseline: el mensaje dice planta, Bwart, filas y Menge.
  - Fase 3a.1: schema con 325, 343, 344 y 555 y Lgort nulo en 702 V; accepted_values del source alineado; seeds almacenes y clases_movimiento con column_types varchar y 8 tests.
  - README: 13 modelos, 2 seeds, 104 tests de datos y 6 unit tests.
  - dbt build 125/125, pytest 33.
- **Decisiones tomadas:** ninguna nueva. Punto 10 de ADR-017 precisado: Costo_usd entra a la huella; Lgort, Cputm y Mblnr quedan fuera.
- **Bloqueos:**
  - Carpeta seeds creada dentro de src/rpi y archivos en 0 bytes. Movida a la raíz y archivos llenados desde VS Code, verificando Length.
  - Un tab viejo de clases_movimientos.csv se guardó y devolvió el nombre en plural; dbt lo cargó sin column_types. Renombrado y DROP de la tabla vieja en DuckDB.
  - schema.py sin formato llegó al push. Corregido en commit aparte.
- **Notas de la sesión:**
  - Hora, minuto y referencia se sortean con n = filas de la planta, y generate reusa el mismo rng entre plantas. En 3a.2 el ruido se filtra después de ese sorteo y nada nuevo usa el rng compartido.
  - dbt infiere el tipo de columna de un seed: sin column_types, 621 entra como entero.
  - El seed toma su nombre del archivo. Si no coincide con seeds.yml, la config y los tests no se aplican; solo avisa dbt ls con un warning.
  - StopIteration al compilar un seed = CSV vacío.
  - Set-Content -Encoding utf8 en PowerShell 5.1 escribe BOM; un CSV con BOM rompe el nombre de la primera columna.
  - En python -c desde PowerShell 5.1 un SQL con comillas se rompe; usar describe o show tables.
  - Un push a un branch sin PR no dispara CI: el workflow corre en pull_request y en push a main.
  - Un test vale si falla con la baseline rota. Aquí reveló que el diagnóstico salía vacío cuando solo cambiaban los conteos.
- **Próximo paso:** Fase 3a.2: quitar el ruido al final de emit_plant_movements y reglas nuevas de Lgort (621 desde LLEN, 622 a SUCI, 702 V sin Lgort). Huella en verde; test_readme.py falla por conteo de filas hasta 3a.3. Test de Lgort y Bwart contra los seeds.

### 2026-09-30 · Sesión 34 — Semana 15

- **Duración:** ~3 h
- **Hecho:**
  - Corrida de una planta (PLNT_MX01, seed 42) para medir el generador antes de diseñar: volumen de 621, ruido por clase de movimiento y Lgort actuales.
  - Diagrama de estados dentro de la planta: siete almacenes y sus movimientos (311, 344, 325, 343, 555, 621, 622, 702 V).
  - Plan de producción derivado de los embarques: partes, instrucción de empaque y plan de 12 semanas posteriores al corte.
  - Parámetros del ciclo interno con valor y rango; flota inicial con holgura y foto de stock inicial.
  - Estrategia para no mover cifras de Fase 1 y 2: generadores aleatorios propios por planta y huella de 621, 622 y 702.
  - Charter: el pipeline se diseña para recibir un MB51 real cambiando seeds.
- **Decisiones tomadas:** ADR-017.
- **Bloqueos:** ninguno.
- **Notas de la sesión:**
  - 344 cambia el tipo de stock, no el almacén. Mover stock bloqueado entre almacenes es 325.
  - El stock especial V no tiene almacén (MSKU): el 702 V va con Lgort vacío.
  - Con un solo generador aleatorio compartido, cualquier fila de más en una planta cambia los datos de todas las siguientes.
  - Las piezas por contenedor se cancelan si el plan sale de contenedores embarcados; sirven para la forma del pipeline y para calidad de datos, no para la necesidad.
  - El estimado de ~35M filas del registro diario no restaba el ruido que sale; medido, el dataset queda en el mismo orden de hoy.
  - Disco y RAM revisados: ~245 GB libres y 16 GB de RAM. El dataset de Fase 3 cabe sin cambiar hardware.
- **Próximo paso:** Semana 16, Fase 3a: huella de 621, 622 y 702 sobre el generador actual, después ciclo interno en el generador.

### 2026-09-30 · Sesión 33 — Semana 14

- **Duración:** ~5 h (28 al 30 de septiembre)
- **Hecho:**
  - ruff format sobre src, tests y notebooks: 12 archivos, sin cambio de lógica. El generador produce el mismo dataset fila por fila.
  - CI con ruff format --check. .git-blame-ignore-revs en la raíz con el commit de formato.
  - mart_rutas como universo de rutas: 71 rutas con tasa, ciclo y marcas de rota. mart_rutas_rotas pasa a ser un filtro. Test singular assert_rutas_universo (ADR-015).
  - Dashboard y notebook 01 toman el "12 de 71" y la marca de ruta rota de mart_rutas.
  - Top 15 de materiales con desempate por material: la gráfica cambiaba entre ejecuciones.
  - Seis unit tests de dbt para int_tramos_fifo con casos calculados a mano. Verificados rompiendo el modelo: LIFO y partición sin material los hacen fallar.
  - tests/test_readme.py: cuadre de cifras del README contra los marts. Se salta con dataset reducido.
  - README: 13 modelos, 96 tests de datos y 6 unit tests; mart_rutas en linaje y estructura; siguiente fase en Estado.
  - Sesión de dominio para Fase 3: ciclo del empaque dentro de la planta. Alcance de Fase 3 y simulador en Fase 4 (ADR-016).
  - dbt build 115/115, pytest 31 en local (26 y 5 saltados en CI).
- **Decisiones tomadas:** ADR-015, ADR-016.
- **Bloqueos:**
  - El commit de formato quedó en main local. Movido a semana-14-hardening con git branch -f antes del push.
  - .git-blame-ignore-revs se creó dentro de .github/workflows; movido a la raíz.
  - Descargas que no llegaban a Descargas. Revisar con Ctrl+J y Test-Path antes de expandir.
- **Notas de la sesión:**
  - COUNT_IF() en DuckDB devuelve HUGEINT, igual que sum(); castear al contar en un consumidor.
  - ORDER BY sin desempate seguido de LIMIT no es reproducible en DuckDB: el orden de los empates depende del paralelismo.
  - Un unit test de dbt necesita que el modelo de arriba exista en la base; dbt build lo resuelve por orden del DAG.
  - Un test vale si falla con el modelo roto: probar rompiéndolo a propósito.
  - En VS Code, New File con una carpeta seleccionada crea el archivo dentro de ella.
  - 632 es consignación, no empaque retornable; la recogida RTP es 622.
- **Próximo paso:** Semana 15, diseño de Fase 3.

### 2026-09-26 · Sesión 32 — Semana 13

- **Duración:** ~1 h
- **Hecho:**
  - Dashboard: ciclo desde mart_ciclo_cohortes, plantas ordenadas por p90. Fuera los casts ::BIGINT sobre columnas leídas directo del mart; queda solo el de SUM(unidades_perdidas).
  - README con cifras de la base corregida: gráficas de rutas rotas, exceso de saldo, costo por viaje y sensibilidad; diagrama de estados 621/622/702; linaje dbt como Mermaid tomado del manifest.
  - Retirados scatter_rutas_rotas.png y dbt_lineage.png (linaje anterior a ADR-011).
  - ADR-011: tabla de cifras antes y después, Sesión 28 contra Semana 13.
  - ADR-010: Consecuencias con la base corregida; equilibrio del Rack de ~$8.70 a $5.14 de flota y $5.55 en la peor planta.
  - faker fuera de pyproject.toml y uv.lock (ADR-011, punto 9).
  - Formato: encabezado de ADR-013 e item 7 de ADR-012 sin indentación de más.
  - Semana 13 cerrada. PR #1 a Ready for review y merge a main.
- **Decisiones tomadas:** ninguna nueva.
- **Bloqueos:** un Copy-Item tomó un PROYECTO.md viejo de Descargas (Length 37823 contra 62728). Detectado antes del commit; restaurado con git checkout.
- **Notas de la sesión:**
  - El README decía que 311 era traslado entre plantas. En el generador 311/411/309 van de TR01 a TR02 dentro de la misma planta.
  - Limpiar Descargas antes de bajar un reemplazo: el navegador renombra a "archivo (1)" y el Copy-Item agarra el viejo.
  - uv.lock se regenera con el uv del repo (0.12.15). Otra versión reescribe markers de paquetes que no cambiaron.
  - ruff format --check no pasa en 02_dashboard.py desde antes de esta sesión; CI solo corre ruff check.
- **Próximo paso:** decidir alcance de Fase 3. Pendientes abiertos:
  - Unit tests de dbt para int_tramos_fifo.
  - int_tramos_fifo con ASOF JOIN (costo lineal), ~1 día.
  - Denominador "de 71" rutas: hoy sale de mart_exceso_saldo_ruta; evaluar mart propio.
  - ruff format del dashboard como commit aparte.

Bitácora cronológica. Entrada más reciente al principio. **Nunca cerrar VS Code sin agregar entrada del día.**

### 2026-09-26 · Sesión 31 — Semana 13

- **Duración:** ~6 h (viernes noche y sábado)
- **Hecho:**
  - El OOM en int_tramos_fifo no era del modelo: el equipo tenía 3.2 GB libres de 15.6. Arranque depurado; con ~7 GB libres el build completo pasa en ~30 s. profiles.yml con memory_limit 4GB y threads 4.
  - Cierre mensual en el último día hábil y test assert_cierre_dia_habil. El vaivén del exceso era calendario: fin de mes en domingo inflaba +7%.
  - mart_exceso_saldo_ruta con la razón real de la ventana de 3 cierres: el 702 borra el exceso en el mes de conciliación.
  - ADR-012: puntos 7 y 8, supuesto de la ventana y sesgo residual en Consecuencias.
  - Marts con conteos en BIGINT y test assert_marts_sin_hugeint (ADR-013).
  - mart_ciclo_cohortes con percentiles sobre la distribución completa (ADR-014). p90 de flota 35 días; el 36.4 anterior era promedio de percentiles mensuales.
  - Notebook 01 reescrito sobre los marts de saldo: texto con cifras generado desde código, sección nueva de exceso de saldo, gráficas rutas_rotas.png y exceso_saldo_rutas.png.
  - Notebook 03 reescrito: TCO con vida esperada, assert de cuadre contra Fase 1, sensibilidad a merma y al desechable del Rack, gráfica tco_costo_por_viaje.png.
  - dbt build 99/99, pytest 26, CI verde.
  - Cifras con 14 plantas:
    - Ciclo de flota: promedio 25.6 días, p50 25, p90 35. Por planta, p90 de 33 a 39.
    - Rutas rotas: 12 de 71, tasa de 1.60% a 1.77%, concentran $1,385,315 (62% de la pérdida).
    - Exceso de saldo: rotas de +4.7% a +6.8%; resto de −1.6% a −0.9%.
    - Vida esperada: KLT 113.9 ciclos, Rack 68.5.
    - Rack: equilibrio de flota $5.14 por embarque, peor planta $5.55.
- **Decisiones tomadas:** ADR-013, ADR-014. ADR-012 ajustado (puntos 7 y 8).
- **Bloqueos:** archivos creados en VS Code que quedaron en 0 bytes o en carpetas duplicadas (tests_dbt\tests_dbt, models\ en vez de models\marts\). Resuelto copiando con Copy-Item desde Descargas y verificando Length.
- **Notas de la sesión:**
  - Medir memoria con Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory; Get-Counter falla en Windows en español.
  - dbt partial parse no detecta archivos creados vacíos y llenados después. Si el TOTAL no cambia, correr con --no-partial-parse y revisar Length.
  - sum() sobre BIGINT en DuckDB devuelve HUGEINT: al volver a sumar columnas de un mart hay que castear el resultado.
  - Un promedio de percentiles mensuales no es un percentil; aquí inflaba el p90 1.4 días.
  - El ruff del repo incluye B905: zip() necesita strict=. Correr ruff local antes de cada commit con notebooks.
  - PowerShell 5.1 no acepta \" dentro de un python -c entre comillas dobles; usar comillas simples en el código Python.
  - PROYECTO.md usa el signo menos tipográfico (−); Select-String con guion normal no lo encuentra.
- **Próximo paso:** Semana 13, paso 8d:
  - README con cifras nuevas y gráficas; retirar scatter_rutas_rotas.png.
  - Tabla antes/después en ADR-011.
  - Consecuencias de ADR-010: el equilibrio del Rack pasa de ~$8.70 a $5.14 de flota y $5.55 en la peor planta.
  - faker fuera de pyproject.toml y uv.lock (ADR-011, punto 9).
  - Dashboard: ciclo desde mart_ciclo_cohortes; quitar los ::BIGINT sobre columnas leídas directo.
  - Ready for review y merge del PR #1.

### 2026-09-25 · Sesión 30 — Semana 13

- **Duración:** 3 h
- **Hecho:**
  - Prototipo FIFO en DuckDB antes de escribir modelos: sirve para ciclo pero no para merma ni vencido, porque los 702 cierran saldo reciente. Todo eso quedó en ADR-012.
  - generator.py: 622 y 702 ya no se emiten si su 621 se registra después del corte. Dataset nuevo: 22,970,200 filas.
  - Staging sin filtro de Bwart, con tipo_material. test-paths a tests_dbt.
  - Tests singulares dbt:
    - Llave única, signo SAP, saldo en cliente no negativo, cartón fuera del ciclo.
    - Conservación FIFO y tramos válidos.
    - Curva de supervivencia válida y saldo mensual que cuadra con tramos abiertos.
    - Pérdidas del mart que cuadran con los 702 de staging.
  - Modelos nuevos:
    - int_mov_cuenta e int_tramos_fifo.
    - int_supervivencia_retorno por tipo de material.
    - int_cuenta_mensual con saldo esperado por curva de supervivencia y exceso de saldo.
  - mart_perdidas_usd, mart_rotacion_planta y mart_rutas_rotas reescritos. mart_rotacion_planta.yml no existía en el branch; creado.
  - TCO con vida esperada por merma, solo KLT y Rack. int_ciclo_retorno retirado.
  - CI con dbt build, dataset de 12 meses por CLI y sin continue-on-error. .gitattributes con LF.
  - PR #1 en borrador contra main. CI verde en 48 s: 79 tests dbt, 26 en pytest.
  - Cifras con 14 plantas:
    - Pérdida reconocida $2,238,765 en 45,853 contenedores (KLT $970,125, Rack $1,268,640). Tasa de flota 0.405%.
    - Rutas rotas: 12 de 71, todas por merma (1.61–1.77%). Concentran $1.39M.
    - Ciclo de cohortes completas: promedio 25.6 días, p50 25, p90 36.4.
    - TCO: ahorro neto $137.5M (KLT $50.4M, Rack $87.1M). Payback de 6 y 5 ciclos.
    - Rack: deja de convenir abajo de ~$5.55. Con el rango $34–66, ahorro de $63.1M a $133.1M.
- **Decisiones tomadas:** ADR-012.
- **Bloqueos:** OOM en int_cuenta_mensual al armar cuenta × mes × edad. Resuelto partiendo de las salidas: cada salida aporta solo a los fines de mes dentro del horizonte de la curva.
- **Notas de la sesión:**
  - dbt run no corre tests; en CI los tests de dbt nunca habían corrido. Usar dbt build.
  - dbt 1.12 pide accepted_values con `arguments:`.
  - dbt no borra la tabla de un modelo eliminado; DROP a mano en la DuckDB local.
  - En DuckDB, date_trunc sobre una fecha devuelve timestamp; castear a date.
  - git rm y git add --renormalize dejan en stage más de lo esperado. Hacer commit de lo pendiente antes de usarlos.
  - Verificar con Test-Path que la descarga terminó antes de Expand-Archive.
  - El ahorro TCO pasa de $41.0M a $137.5M casi todo por volumen: antes se contaban líneas, ahora contenedores. La economía por viaje es estable (KLT ~$4.08, Rack ~$39.86).
- **Próximo paso:** Semana 13, paso 8a — dashboard alineado a los marts nuevos.

### 2026-09-25 · Sesión 29 — Semana 12

- **Duración:** 4 h
- **Hecho:**
  - Medí generador y modelos con una corrida reducida antes de arrancar Fase 3: 480 Matnr en uso en lugar de 1,200, fan-out en el join 601→602, pérdidas contadas en líneas, 602 posteriores al corte, Mblnr con colisiones y ~9,000 clientes aleatorios por planta. Todo eso quedó en ADR-011.
  - config.py: reference_date fija, CustomerConfig, LossConfig con merma por ruta en dos segmentos, MengeConfig por tipo, conciliación trimestral, global_matnr_share.
  - generator.py reescrito y vectorizado:
    - Ciclo 621/622/702; el cartón sale con 601.
    - Censura sobre Budat y Cpudt.
    - Mblnr secuencial por año.
    - Traslados en dos posiciones.
    - Rack dedicado a un cliente.
    - Un Parquet por planta.
  - Dataset completo: 21,218,569 filas, ~65 s, pico de ~1.1 GB.
  - schema.py con Bwart 621/622/702 y signo SAP. CLI arma la config con model_validate.
  - Tests del generador: reproducibilidad fila por fila, corte, llave única, traslados en cero, cartón fuera del ciclo, rack dedicado, merma en rango. 23/23 en pytest.
  - Branch adr-011-correccion-base; main no se toca hasta alinear dbt.
- **Decisiones tomadas:** ADR-011.
- **Bloqueos:** OOM con 14 plantas al concatenar todo en memoria. Resuelto escribiendo un Parquet por planta.
- **Notas de la sesión:**
  - group_by de Polars no garantiza orden; sin maintain_order=True el dataset cambiaba entre corridas con el mismo seed. El test de reproducibilidad anterior solo comparaba conteo de filas y no lo detectaba.
  - conftest generaba en data/raw y cada pytest local pisaba el dataset completo. Ahora usa tmp_path_factory.
  - model_copy de Pydantic no corre validadores; para overrides usar model_validate.
  - Reemplazar archivos con Copy-Item desde Descargas y verificar con Select-String o git grep; el pegado en VS Code no siempre se guarda.
  - El warning LF → CRLF es ruido; pendiente .gitattributes.
- **Próximo paso:** Semana 13 — diseño de modelos dbt por saldo FIFO, TCO con vida esperada, recálculo de Fase 1 y 2.

### 2026-09-24 · Sesión 28 — Semana 11

- **Duración:** ~3 h
- **Hecho:**
  - 02_dashboard.py reestructurado en dos pestañas: "Rotación y pérdidas" y "TCO".
  - Pestaña TCO: ahorro neto retornable $41.0M (Rack $33.6M, KLT $7.5M), payback 5/6 ciclos, costo de merma $4.77M, merma sobre bruto 9.8%/13.1%, detalle por tipo y por planta.
  - Cartón mostrado como línea base (n/a en ahorro y payback); su -$57,064 en el mart es su costo de merma.
  - 03_tco_analysis.ipynb estaba guardado en UTF-16 con acentos corrompidos (GitHub no lo renderizaba). Convertido a UTF-8 y texto reparado.
  - Lint pendiente en los tres notebooks corregido. CI ahora corre ruff también sobre notebooks/.
  - README: resultados Fase 2, tabla de supuestos, desglose del desechable equivalente del Rack con rango $34–66 y sensibilidad, Marimo en tabla de stack, estructura del repo actualizada.
  - Validación cruzada: merma TCO (KLT + Rack + Cartón) = pérdida total Fase 1 ($4.82M).
  - TcoConfig eliminado de config.py (ADR-010).
  - Historial local reescrito antes del push: un commit del dashboard tenía el mensaje de semana 6.
  - 03_tco_analysis.ipynb: la sensibilidad usaba ciclos × tasa × costo y el escenario de 2% daba $41.44M contra $41.04M del headline. Ahora escala la merma real observada; el 2% cuadra exacto.
  - Resumen ejecutivo del 03 corregido: cada punto de merma = ~$2.4M en 18 meses (~$1.6M por año). Antes decía $2.4M anuales en un bullet y $1.2M en otro.
  - Signos $ escapados en markdown del 03: GitHub los renderizaba como fórmula.
- **Decisiones tomadas:** ADR-010.
- **Bloqueos:** ninguno.
- **Notas de la sesión:**
  - Las sumas de dbt sobre count(*) salen como HUGEINT; castear a BIGINT antes de pasar a Polars.
  - mart_tco_comparativo es por planta × tipo; el resumen por tipo se agrega en el dashboard.
  - En Marimo, variables auxiliares con prefijo _ para no chocar entre celdas.
  - Windows PowerShell 5.1 escribe UTF-16 con `>` y Out-File. Notebooks y archivos de texto se guardan desde VS Code.
  - `marimo edit` no ejecuta celdas al abrir; para ver el dashboard usar `marimo run`.
  - ConnectionResetError WinError 10054 al cerrar Marimo es ruido de asyncio en Windows.
  - En markdown de notebooks, dos $ en el mismo párrafo se renderizan como LaTeX en GitHub. Escapar con \$.
  - Re-ejecutar notebooks con `jupyter nbconvert --execute --inplace` en vez de VS Code: no depende del kernel de la UI y conserva UTF-8.
- **Próximo paso:** decidir si hay Fase 3 o cierre del proyecto con post de lanzamiento.


### 2026-09-24 · Sesión 27 — Semana 10

- **Duración:** ~2 h
- **Hecho:**
  - Parámetro desechable equivalente Rack corregido a $45.00 en int_tco_por_material.sql (estaba null por hardcode en SQL, no leía TcoConfig).
  - mart_tco_comparativo regenerado con números completos para los tres tipos.
  - Notebook 03_tco_analysis.ipynb completo: headline $41M, ahorro por tipo, payback, costo de merma, sensibilidad a tasa de merma, resumen ejecutivo.
  - Dos gráficos guardados en docs/img/: tco_ahorro_neto.png, tco_sensibilidad.png.
- **Decisiones tomadas:** ninguna nueva.
- **Bloqueos:** ninguno.
- **Próximo paso:** semana 11 — dashboard Marimo con pestaña TCO, README con resultados Fase 2.

### 2026-09-24 · Sesión 26 — Semana 9

- **Duración:** ~2 h
- **Hecho:**
  - TcoConfig agregado a config.py con parámetros KLT/Rack/Cartón (vida útil, mantenimiento, desechable equivalente).
  - int_tco_por_material.sql: amortización por ciclo, costo retornable, ahorro vs desechable, ciclos de payback.
  - mart_tco_comparativo.sql: TCO agregado por tipo de material y planta, ahorro neto vs desechable considerando merma.
  - YMLs de documentación dbt para ambos modelos.
  - Tres tests de dominio en test_marts.py: costo retornable positivo, payback positivo, tipos válidos.
  - dbt run: PASS=7 WARN=0 ERROR=0. pytest: 17/17 passed.
  - 4 commits pusheados a main.
- **Decisiones tomadas:** ninguna nueva.
- **Bloqueos:** archivos SQL/YML creados con wrapper de PowerShell dentro — resuelto escribiendo directo con Set-Content.
- **Próximo paso:** confirmar CI verde, luego notebook 03_tco_analysis.ipynb con storytelling TCO en USD.

### 2026-09-23 · Sesión 25 — Arranque Fase 2

- **Duración:** en curso
- **Hecho:**
  - Revisión completa del repo (ZIP): código fuente, modelos dbt, tests, CI, README. Estado confirmado con Fase 1 funcionando de punta a punta.
  - Decisión de Fase 2: TCO retornable vs desechable. Descartadas Fase 3 (Forecast vs MRP) y Fase 4 (ciclo lavado/reparación) — razonamiento en ADR-009.
  - ADR-009 redactado y pegado en PROYECTO.md.
  - Código diseñado: TcoConfig en config.py, int_tco_por_material.sql, mart_tco_comparativo.sql, YMLs de documentación, tres  tests nuevos en test_marts.py.
- **Decisiones tomadas:** ADR-009.
- **Bloqueos:** ninguno.
- **Próximo paso:** aplicar cambios en repo local, correr dbt + pytest, confirmar CI verde. Luego notebook 03_tco_analysis.ipynb.

### 2026-09-22 · Sesión 24

- **Duración:** ~3 h
- **Hecho:**
  - README: sección Resultados con KPIs del dataset ($4,822,074 USD, 72,512 unidades, costo promedio $66.50 USD/unidad).
  - tests/test_marts.py: 5 tests de dominio sobre marts dbt (perdida_usd positiva, tasa_merma en [0,100], ciclo positivo y dentro de rango, criterios de rutas rotas). 14/14 pytest passing.
  - README: diagrama Mermaid stateDiagram-v2 del ciclo de vida de un contenedor retornable (EnPlanta → EnCliente → Retorno / Merma con códigos Bwart).
  - 02_dashboard.py: sección KPIs globales con mo.hstack, gráfico de barras mensual de pérdidas USD con matplotlib inline.
  - CI verde en todos los runs.
- **Decisiones tomadas:** ninguna nueva.
- **Bloqueos:** ninguno.
- **Próximo paso:** evaluar inicio de Fase 2 del proyecto.

### 2026-09-21 · Sesión 23

- **Duración:** ~3 h
- **Hecho:**
  - Auditoría completa del repo: revisión de todos los archivos contra criterios del Charter.
  - `Costo_usd` declarado en `schema.py` como campo del contrato MB51. 9/9 pytest passing.
  - Sección 2 de PROYECTO.md actualizada: Marimo en Capa 3, Evidence.dev movido a descartados.
  - Semana 6 del roadmap corregida: refleja entrega real con Marimo.
  - README: nota sobre período del dataset y cola del ciclo 601→602.
  - `mart_rotacion_planta.yml` creado con tests not_null en 4 columnas.
  - README: nota sobre uso de `raw_dir` en `ingest()` con `--output` personalizado.
  - `02_dashboard.py`: eliminado `mo.stat()` duplicado en primera celda.
  - `01_analisis_perdidas.ipynb` ejecutado y commiteado con outputs.
  - Gráficos regenerados commiteados: `scatter_rutas_rotas.png`, `top15_materiales.png`.
  - CI verde en run #25. 54 commits totales.
- **Decisiones tomadas:** ninguna nueva.
- **Bloqueos:** ninguno.
- **Próximo paso:** evaluar inicio de Fase 2 del proyecto.

### 2026-09-20 · Sesión 22

- **Duración:** ~5 h
- **Hecho:**
  - Tests dbt agregados en toda la cadena: sources.yml, stg_mb51.yml, mart_perdidas_usd.yml, int_ciclo_retorno.yml, mart_rutas_rotas.yml. 20/20 PASS.
  - dbt docs generate + grafo de linaje capturado en docs/img/dbt_lineage.png y agregado al README.
  - Cobertura pytest subió de 89% a 94%. db.py pasó de 0% a 92% con test_ingest_crea_tabla_con_filas. 9/9 PASS.
  - CLI del generador implementado en src/rpi/__main__.py con flags --months, --plants, --country, --loss-rate, --seed, --output.
  - Dashboard Marimo con manejo de estado vacío: mo.stop con callout si falta DuckDB o marts.
  - Fix diagrama Mermaid en README: eliminados br en nodos, bloque cerrado correctamente.
  - Fix CI: imports fuera de lugar en test_schema.py y PlantConfig no usado en __main__.py. Ruff --fix aplicado. CI verde.
  - Fix código: comentario "Fase 1" en schema.py, xblnr duplicado en stg_mb51.sql, sintaxis accepted_values en stg_mb51.yml.
  - Todos los commits pusheados a main.
- **Decisiones tomadas:** ninguna nueva.
- **Bloqueos:** ninguno.
- **Próximo paso:** evaluar inicio de siguiente fase del proyecto.

### 2026-09-19 · Sesión 21

- **Duración:** ~2 h
- **Hecho:**
  - 3 iteraciones para limpiar errores de lint (imports no usados, orden de imports, anotaciones Optional → X | None, línea larga en schema.py).
  - CI verde en run final. Badges ci/passing, python 3.11 y license MIT renderizando en README.
- **Decisiones tomadas:** ninguna nueva.
- **Bloqueos:** ninguno.
- **Próximo paso:** semana 8 — tests dbt completos, dbt docs, cobertura pytest.

### 2026-09-17 · Sesión 20

- **Duración:** ~2 h
- **Hecho:**
  - test_schema.py completo: schema Pandera, columnas core, Bwart enum, Menge no cero.
  - ci.yml creado: lint Ruff, generador CI (2 plantas, 3 meses), ingesta DuckDB, dbt run, pytest con cobertura.
  - profiles.yml en raíz del repo con rutas relativas para que dbt funcione en CI.
- **Decisiones tomadas:** ninguna nueva.
- **Bloqueos:** ninguno.
- **Próximo paso:** limpiar errores de lint, CI verde.

### 2026-09-15 · Sesión 19

- **Duración:** ~2 h
- **Hecho:**
  - conftest.py con fixtures cfg_ci y df_ci (2 plantas MX, 3 meses, seed 42).
  - test_generator.py: filas en rango, plantas correctas, reproducibilidad, tasa no-retorno ±5pp.
- **Decisiones tomadas:** ninguna nueva.
- **Bloqueos:** ninguno.
- **Próximo paso:** test_schema.py, ci.yml.

### 2026-09-13 · Sesión 18

- **Duración:** ~6 h
- **Hecho:**
  - notebooks/02_dashboard.py completo: imports + conexión DuckDB read-only, KPIs globales con mo.stat, tabla rutas rotas, tabla rotación mensual, tabla ciclo promedio por planta.
  - Headers narrativos Markdown entre secciones.
  - Dashboard corriendo con datos reales de los marts.
  - Commit y push: semana 6 dashboard Marimo con KPIs, rutas rotas y ciclo de retorno.
- **Decisiones tomadas:** ninguna nueva.
- **Bloqueos:** ninguno.
- **Próximo paso:** semana 7 — CI con GitHub Actions, tests automáticos, badges en README.

### 2026-09-10 · Sesión 17

- **Duración:** ~2 h
- **Hecho:**
  - uv add marimo agregado al entorno del proyecto.
  - Estructura inicial del dashboard: conexión DuckDB, primera celda con KPIs.
- **Decisiones tomadas:** ninguna nueva.
- **Bloqueos:** ninguno.
- **Próximo paso:** completar dashboard con todas las secciones.

### 2026-09-08 · Sesión 16

- **Duración:** ~2 h
- **Hecho:**
  - Intento fallido con Evidence.dev: paquete create-evidence-app eliminado de npm; nuevo CLI migró a modelo cloud (Evidence Studio).
  - Investigación de alternativas: Streamlit, Marimo.
  - Decisión de reemplazar Evidence.dev por Marimo (ADR-008).
- **Decisiones tomadas:** ADR-008 (Marimo sobre Evidence.dev).
- **Bloqueos:** Evidence.dev incompatible con pipeline local.
- **Próximo paso:** instalar Marimo, arrancar dashboard.

### 2026-09-06 · Sesión 15

- **Duración:** ~6 h
- **Hecho:**
  - notebooks/01_analisis_perdidas.ipynb completo: headline USD, tendencia mensual, pareto plantas, top materiales, rutas rotas, resumen ejecutivo.
  - 4 gráficos guardados en docs/img/: perdidas_mensual.png, pareto_plantas.png, top15_materiales.png, scatter_rutas_rotas.png.
  - Detectado y corregido: tasa_merma_pct en mart_rutas_rotas almacenado como % entero, no decimal.
  - Detectado: distribución de pérdidas entre plantas uniforme — refleja generador sintético sin varianza por planta.
- **Decisiones tomadas:** ninguna nueva.
- **Bloqueos:** ninguno.
- **Próximo paso:** semana 6 — dashboard con Evidence.dev.

### 2026-09-03 · Sesión 14

- **Duración:** ~2 h
- **Hecho:**
  - Gráficos matplotlib: tendencia mensual de pérdidas, pareto de plantas, top 15 materiales.
  - uv add matplotlib agregado al entorno.
  - Directorio docs/img/ creado para guardar gráficos.
- **Decisiones tomadas:** ninguna nueva.
- **Bloqueos:** ninguno.
- **Próximo paso:** completar notebook con scatter rutas rotas y resumen ejecutivo.

### 2026-09-01 · Sesión 13

- **Duración:** ~2 h
- **Hecho:**
  - Arranque notebooks/01_analisis_perdidas.ipynb: estructura de secciones, conexión a DuckDB, primera query de headline USD.
- **Decisiones tomadas:** ninguna nueva.
- **Bloqueos:** ninguno.
- **Próximo paso:** gráficos matplotlib, pareto plantas, top materiales.

### 2026-08-30 · Sesión 12

- **Duración:** ~5 h
- **Hecho:**
  - mart_rutas_rotas.sql: rutas con tasa_merma > 5% o ciclo > 45 días, ordenadas por pérdida acumulada.
  - dbt run: PASS=5 WARN=0 ERROR=0. Pipeline completo funcionando de punta a punta.
  - Commit y push: semana 4 marts completos.
- **Decisiones tomadas:** ninguna nueva.
- **Bloqueos:** ninguno.
- **Próximo paso:** semana 5 — notebook analítico narrativo.

### 2026-08-29 · Sesión 11

- **Duración:** ~2 h
- **Hecho:**
  - mart_rotacion_planta.sql: rotación mensual por planta con ciclo p50/p90.
  - mart_perdidas_usd.sql: pérdidas en USD por material/planta/mes.
- **Decisiones tomadas:** ninguna nueva.
- **Bloqueos:** ninguno.
- **Próximo paso:** mart_rutas_rotas.sql, dbt run completo.

### 2026-08-27 · Sesión 10

- **Duración:** ~2 h
- **Hecho:**
  - int_ciclo_retorno.sql: left join 601→602 con ventana 120 días, flag es_merma.
- **Decisiones tomadas:** ninguna nueva.
- **Bloqueos:** ninguno.
- **Próximo paso:** marts de pérdidas y rotación.

### 2026-08-25 · Sesión 09

- **Duración:** ~2 h
- **Hecho:**
  - MaterialCost en config.py: clase Pydantic con KLT $25, Rack $180, Cartón $8.
  - StrEnum aplicado a Country y MaterialType.
  - costo_usd propagado en build_matnr_pool y emit_plant_movements.
  - generate() refactorizado a list[pl.DataFrame] por planta — resuelve OOM.
  - Dataset regenerado: 15,550,868 filas × 17 columnas. DuckDB reingestado.
  - stg_mb51.sql actualizado con costo_usd.
- **Decisiones tomadas:** ninguna nueva.
- **Bloqueos:** ninguno.
- **Próximo paso:** int_ciclo_retorno.sql.

### 2026-08-17 · Sesión 08

- **Duración:** ~4 h
- **Hecho:**
  - stg_mb51.sql: limpieza y tipado de las 22 columnas MB51, filtro por Bwart válidos, cálculo lag_dias y flag_tardio.
  - sources.yml: fuente raw_mb51 declarada con descripción.
  - dbt run staging: PASS=1 WARN=0 ERROR=0.
- **Decisiones tomadas:** ninguna nueva.
- **Bloqueos:** ninguno.
- **Próximo paso:** semana 4 — modelos intermediate y marts.

### 2026-08-16 · Sesión 07

- **Duración:** ~6 h
- **Hecho:**
  - db.py: ingesta Parquet → DuckDB con CREATE OR REPLACE TABLE raw_mb51.
  - DuckDB cargado: 15,550,868 filas confirmadas.
  - dbt_project.yml y profiles.yml configurados.
  - Estructura models/staging/, models/intermediate/, models/marts/ creada.
- **Decisiones tomadas:** ninguna nueva.
- **Bloqueos:** ninguno.
- **Próximo paso:** stg_mb51.sql y sources.yml.

### 2026-08-13 · Sesión 06

- **Duración:** ~2 h
- **Hecho:**
  - notebooks/00_sanity_check.ipynb: shape, Bwart mix, ciclo 601→602 (media 24.9 días, P99 85.8), merma 2.0% uniforme en 14 plantas, lag Cpudt/Budat ~92% mismo día.
  - Validación Pandera OK contra MB51Schema (strict=False para 16 de 22 columnas).
  - Ajustes en schema.py: Optional en 6 columnas opcionales, tipos corregidos.
- **Decisiones tomadas:** ninguna nueva.
- **Bloqueos:** ninguno.
- **Próximo paso:** semana 3 — ingesta DuckDB, dbt staging.

### 2026-08-10 · Sesión 05

- **Duración:** ~6 h
- **Hecho:**
  - generator.py completo: apply_return_cycle con ciclo log-normal 601→602, merma 2.01%.
  - Dataset completo generado: 15,550,868 filas × 16 columnas en data/raw/mb51_synthetic.parquet.
  - Tasa de merma real: 2.01% (objetivo 2.0%).
- **Decisiones tomadas:** ninguna nueva.
- **Bloqueos:** ninguno.
- **Próximo paso:** validación Pandera, notebook sanity check.

### 2026-08-09 · Sesión 04

- **Duración:** ~6 h
- **Hecho:**
  - config.py: modelo Pydantic completo con PlantConfig, MaterialMix, CycleConfig, CpudtLagConfig, GeneratorConfig. Validadores de suma=1.0 y rangos de negocio.
  - generator.py: build_matnr_pool, assign_matnr_to_plants (40% global con solape, 480 por planta), build_date_range, emit_plant_movements (Bwart mix realista, lag Cpudt/Budat 92/6/2, Lgort coherente con Bwart).
  - Límite ge=1_000 en monthly_movements_min/max ajustado a ge=100 para pruebas con volumen reducido.
- **Decisiones tomadas:** ADR-007 (Matnr por planta: pool global 40% sin límite estricto de 250).
- **Bloqueos:** ninguno.
- **Próximo paso:** apply_return_cycle, dataset completo.

### 2026-08-08 · Sesión 03

- **Duración:** ~2 h
- **Hecho:**
  - README v0 público con problema, approach, stack con trade-offs, diagrama Mermaid del flujo, disclaimer de datos sintéticos.
  - src/rpi/schema.py con las 22 columnas MB51 en Pandera (16 core + 6 opcionales), tipos, longitudes SAP, enum de Bwart y Meins, nullable explícito por columna.
  - Corrección: el conteo inicial decía 18 columnas cuando el core real son 16 (22 en total). Corregido en PROYECTO.md, README.md y schema.py.
- **Decisiones tomadas:** ninguna nueva.
- **Bloqueos:** ninguno.
- **Próximo paso:** semana 2 — generador sintético completo.

### 2026-08-06 · Sesión 02

- **Duración:** ~2 h
- **Hecho:**
  - Setup local completado: Git 2.55, uv 0.12.15, Python 3.11.16 en Windows.
  - Repo returnable-packaging-intelligence creado público en GitHub y clonado en C:\proyectos.
  - Estructura src/ layout con carpetas para tests, notebooks, docs, data.
  - pyproject.toml con dependencias Capa 1 y Capa 2. uv.lock versionado.
  - .gitignore ampliado con data generada, DuckDB, dbt target, Power BI, IDE.
- **Decisiones tomadas:** ninguna nueva.
- **Bloqueos:** ninguno.
- **Notas:**
  - Windows es case-insensitive pero Git es case-sensitive: PROYECTO.MD vs PROYECTO.md causó un git add que no capturaba nada. Fix: rename explícito.
- **Próximo paso:** README v0, schema Pandera.

### 2026-08-04 · Sesión 01

- **Duración:** ~2 h
- **Hecho:**
  - Definido proyecto: rotación y pérdidas de RPL como primera entrega.
  - Definido stack completo por capas (esencial, diferenciador, opcional).
  - Definidos parámetros del generador sintético (14 plantas, 1,200 Matnr, mix por tipo, merma 2%, ciclo 25 días).
  - Definido diccionario de datos con 16 columnas core + 6 opcionales MB51 (22 en total).
  - Definido sistema de docs: PROYECTO.md único con 7 secciones + README.md público separado.
  - Confirmado entorno: Windows + Git + VS Code + PowerShell.
- **Decisiones tomadas:** ADR-001 a ADR-006.
- **Bloqueos:** Ninguno.
- **Próximo paso:**
  - Crear repo en GitHub (público).
  - Clonar localmente en C:\proyectos\returnable-packaging-intelligence.
  - Preparar scaffold de semana 1.

---

## 7. Glosario

### Términos SAP

- **MB51** — Transacción SAP: reporte de movimientos de materiales. Fuente principal del proyecto.
- **MIGO** — Transacción SAP: registro de movimientos de material.
- **MMBE** — Transacción SAP: stock overview por material.
- **ME21N / ME23N** — Transacciones SAP: crear / visualizar orden de compra.
- **ME31L / ME38** — Transacciones SAP: contratos y planes de entrega.
- **ME29N** — Transacción SAP: liberación de órdenes de compra.
- **Bwart** — Clase de movimiento SAP. Códigos numéricos que definen el tipo de transacción (recepción, consumo, traslado, salida a cliente, retorno).
- **Werks** — Centro / planta.
- **Lgort** — Almacén.
- **Matnr** — Código de material.
- **Lifnr** — Proveedor.
- **Kunnr** — Cliente.
- **PO / OC** — Purchase Order / Orden de Compra.
- **Stock especial V** — Empaque retornable en ubicación del cliente que sigue siendo propiedad de la empresa. Se ve en MMBE.
- **LEIH** — Grupo de tipos de posición estándar SAP para empaque retornable.
- **Pedido LA** — Pedido de recogida de empaque retornable; su entrada contabiliza 622.
- **OMJJ** — Transacción SAP: configuración de clases de movimiento.
- **RTP** — Returnable Transport Packaging. Proceso estándar SD para empaque retornable con cliente: 621 salida, 622 recogida, 623 el cliente se queda el empaque.
- **344** — Traspaso de libre utilización a stock bloqueado.
- **555** — Baja (desecho) desde stock bloqueado.
- **343** — Traspaso de stock bloqueado a libre utilización, dentro del mismo almacén.
- **325** — Traslado de stock bloqueado a stock bloqueado entre almacenes de la misma planta.
- **Tipo de stock** — Libre utilización, control de calidad o bloqueado. 344 y 343 cambian el tipo sin cambiar de almacén.
- **MSKU** — Tabla SAP del stock especial en cliente (V). Se lleva por planta, cliente y material, sin almacén: el 702 V no lleva Lgort.
- **PSA** — Production Supply Area. Punto de surtido de material junto a la línea.
- **STO** — Stock Transport Order. Pedido de traslado entre plantas.
- **MB5B** — Transacción SAP: stock a una fecha. Da el stock inicial que MB51 no trae; movimientos más foto inicial reconstruyen el stock.
- **MD61 / PBED** — Transacción y tabla SAP de necesidades independientes: el plan de producción por material y periodo.
- **POP1** — Transacción SAP de instrucción de empaque. Alternativa en SD: registro info cliente-material (VD51).

### Términos de dominio (RPL)

- **RPL** — Returnable Packaging Logistics. Logística de empaques retornables.
- **KLT** — Kleinladungsträger. Contenedor plástico apilable pequeño, estándar automotriz.
- **Rack** — Estructura metálica reutilizable para transportar piezas voluminosas.
- **Tarima** — Pallet de madera. Aquí en categoría desechable/consumible.
- **Ciclo 621→622** — Tiempo entre salida del empaque a stock especial del cliente (621) y su recogida (622).
- **Merma** — Empaque que sale y no vuelve. Se convierte en pérdida contable.
- **Flota fantasma** — Empaques registrados como activos pero perdidos en la práctica.
- **TCO** — Total Cost of Ownership. Costo total de operar un contenedor en su vida útil: compra amortizada, mantenimiento y merma.
- **Payback** — Ciclos que tarda un retornable en recuperar su costo de compra contra el desechable equivalente.
- **Desechable equivalente** — Empaque de un solo uso que haría el mismo trabajo que un retornable en un embarque.
- **Dunnage** — Material interior que protege y separa las piezas dentro del empaque (separadores, espuma, charolas).
- **Bulk bin** — Caja corrugada grande de triple pared para carga a granel sobre tarima.
- **Conciliación de saldo** — Comparación periódica del saldo en cliente contra conteo físico; el faltante es merma confirmada.
- **Antigüedad FIFO** — Edad del saldo en cliente asumiendo que lo primero que salió es lo primero que regresa.
- **Saldo vencido** — Contenedores en cliente con más de 120 días de antigüedad. Riesgo de merma, todavía no pérdida.
- **Vida esperada** — Ciclos promedio que dura un contenedor considerando la merma: (1 − (1 − p)^V) / p.
- **Ventana conciliada** — Salidas con antigüedad suficiente para haber pasado por una conciliación: Budat ≤ última conciliación − 120 días. Denominador de la tasa de merma.
- **Instrucción de empaque** — Define para cada parte y cliente qué empaque se usa y cuántas piezas lleva (Packvorschrift / PI).
- **Días de cobertura** — Stock expresado en días de demanda que alcanza a cubrir.
- **Exceso de saldo** — Saldo en cliente por arriba del esperado por la curva de supervivencia. Merma todavía no reconocida en conciliación.
- **Holgura de flota** — Porcentaje de contenedores por arriba del mínimo que necesita la operación. La merma y el scrap la consumen con el tiempo.
- **Arranque / fin de serie (EOP)** — Inicio y fin de producción de un programa del cliente. Mueven la necesidad de empaque antes de que la flota pueda reaccionar.

### Términos técnicos

- **ADR** — Architecture Decision Record. Formato para documentar decisiones técnicas con contexto y alternativas descartadas.
- **dbt** — data build tool. Framework de modelado analítico en SQL con testing, docs y linaje.
- **Parquet** — formato columnar comprimido de facto en data engineering moderno.
- **Polars** — dataframe library en Rust, alternativa moderna a Pandas.
- **DuckDB** — motor analítico OLAP embebido, "SQLite para analytics".
- **Pandera** — librería para validación de schemas de dataframes en Python.
- **uv** — gestor de entornos y paquetes de Python, escrito en Rust, muy rápido.
- **Ruff** — linter y formatter de Python, escrito en Rust, muy rápido.
- **CI/CD** — Continuous Integration / Continuous Delivery.
- **Marimo** — notebooks reactivos de Python guardados como `.py`; corren como app con `marimo run`.
- **UTF-8 / UTF-16** — codificaciones de texto. El repo usa UTF-8; Windows PowerShell 5.1 escribe UTF-16 por default con `>`.
- **HUGEINT** — entero de 128 bits de DuckDB; es lo que devuelve sum() sobre enteros. Polars no lo maneja bien. Los marts castean a BIGINT (ADR-013).
- **Unit test (dbt)** — Test con datos de entrada y salida definidos a mano que valida la lógica de un modelo sin depender del dataset.
- **.git-blame-ignore-revs** — Lista de commits que git blame y GitHub ignoran; se usa para commits de solo formato.
- **Censura al corte** — No emitir movimientos posteriores a la fecha de corte del dataset.
- **Curva de supervivencia** — Probabilidad de que un contenedor siga en cliente a cierta edad, estimada con los ciclos observados. Aplicada a las salidas diarias da el saldo esperado.

---



*Fin del documento. Actualizar el Worklog en cada sesión.*