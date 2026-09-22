# PROYECTO — Returnable Packaging Intelligence

Cerebro interno del proyecto. Todo vive aquí.
Para la vista pública ver `README.md`.

**Repositorio:** `returnable-packaging-intelligence`
**Autor:** Juan Carlos Prado Arias
**Última actualización:** 2026-09-20

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

### Audiencia

- Equipos de gobernanza de Returnable Packaging Logistics (RPL) en industria automotriz.
- Analistas de master data SAP MM que quieran ver cómo se aterriza MB51 en un pipeline analítico moderno.
- Ingenieros de datos que trabajen con datasets tipo ERP y busquen ejemplos de dbt + Polars + DuckDB.

### Alcance IN — Fase 1

Rotación y pérdidas de contenedores retornables en flota multi-planta usando dataset MB51 sintético (18 meses, 14 plantas, ~1,200 Matnr).

### Alcance OUT (roadmap futuro, NO se ejecuta ahora)

- Fase 2: TCO retornable vs desechable (metal vs cartón + tarima madera).
- Fase 3: Forecast de necesidad de packaging vs plan de producción MRP.
- Fase 4: Cuello de botella del ciclo lavado / reparación.

### Criterios de completitud

- Repo público con documentación completa y CI verde.
- Pipeline reproducible: `uv sync` + comando único para regenerar dataset y correr todo el stack analítico.
- Notebook narrativo que traduzca KPIs técnicos en cifras de negocio en USD.
- Diagramas Mermaid del dominio y del flujo de datos.

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
- **Faker + NumPy** — generación sintética
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
- **Evidence.dev** — dashboard vivo como código
- **Power BI Desktop** — vista ejecutiva descargable (.pbix)
- **MkDocs Material** — sitio de documentación

### Descartado explícitamente

- **Airflow** — overkill para este scope.
- **Postgres / MySQL** — DuckDB los reemplaza en este scope.
- **Snowflake / BigQuery / Databricks** — no necesarios; portables vía dbt profiles.
- **Pandas** — reemplazado por Polars en todo el pipeline.
- **Kafka / streaming** — este es batch, no streaming.

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

---

## 4. Diccionario de datos (MB51 sintético)

### Columnas core (16)

| Campo | Descripción | Uso analítico |
|-------|-------------|---------------|
| Werks | Centro (planta) | Filtro base por sitio |
| Lgort | Almacén | Distingue racks piso / tránsito / cuarentena |
| Matnr | Material (código empaque) | Rack, contenedor, KLT |
| Maktx | Texto breve del material | Lectura rápida sin cruzar MAKT |
| Bwart | Clase de movimiento | Separar 501/502, 561/562, 411/412, 309, 601/602 |
| Mjahr / Budat | Año contable y fecha contabilización | Cortes mensuales / semanales |
| Cpudt / Cputm | Fecha y hora de registro en sistema | Auditar registros tardíos |
| Menge + Meins | Cantidad y unidad de medida base | PC normalmente en empaques |
| Mblnr / Zeile | Documento material y posición | Ancla a MIGO / ME23N |
| Lifnr | Proveedor | Retornable con socio (461/462, 501/502) |
| Kunnr | Cliente / consignatario | Racks a cliente (601/602, 631/632) |
| Xblnr | Referencia / documento externo | Número embarque, delivery, pedido físico |

### Columnas extras opcionales (6)

| Campo | Descripción |
|-------|-------------|
| Ebeln / Ebelp | Orden de compra y posición (101/102, 501/502 con PO) |
| Sgtxt | Texto de posición (placas, folios, comentarios) |
| Umwrk / Umlgo | Centro y almacén destino en traslados (301/311) |
| Usnam | Usuario que registró (trazabilidad de errores) |

### Parámetros del generador

- **14 plantas:** 6 México, 6 Estados Unidos, 2 Nicaragua. Nombres genéricos PLNT_XX##.
- **250 Matnr por planta**, ~1,200 únicos globales con solape entre plantas.
- **Mix por tipo:** 60% KLT plástico, 30% racks metálicos, 10% cartón + tarima madera.
- **Horizonte:** 18 meses de historia (para capturar estacionalidad).
- **Volumen objetivo:** ~40-80k movimientos por planta/mes → ~10M filas totales.
- **Bwart mix realista:** 501/502, 601/602, 311/411, 101/102, 261, 309 esporádico.
- **Ciclo 601→602:** log-normal, media 25 días, con cola larga (60-90 días para algunos).
- **Tasa de no-retorno:** 2% global, uniforme entre clientes y rutas.
- **Lag Cpudt vs Budat:** 92% mismo día, 6% 1-2 días tarde, 2% >48h (ángulo de disciplina operativa).

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

---

## 6. Worklog

Bitácora cronológica. Entrada más reciente al principio. **Nunca cerrar VS Code sin agregar entrada del día.**

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

### Términos de dominio (RPL)

- **RPL** — Returnable Packaging Logistics. Logística de empaques retornables.
- **KLT** — Kleinladungsträger. Contenedor plástico apilable pequeño, estándar automotriz.
- **Rack** — Estructura metálica reutilizable para transportar piezas voluminosas.
- **Tarima** — Pallet de madera. Aquí en categoría desechable/consumible.
- **Ciclo 601→602** — Tiempo entre salida a cliente (601) y retorno del empaque (602).
- **Merma** — Empaque que sale y no vuelve. Se convierte en pérdida contable.
- **Flota fantasma** — Empaques registrados como activos pero perdidos en la práctica.

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

---



*Fin del documento. Actualizar el Worklog en cada sesión.*