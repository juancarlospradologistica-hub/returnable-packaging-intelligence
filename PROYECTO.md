# PROYECTO — Returnable Packaging Intelligence

Cerebro interno del proyecto. Todo vive aquí.
Para la vista pública ver `README.md`.

**Repositorio:** `returnable-packaging-intelligence`
**Autor:** Juan Carlos Prado Arias
**Última actualización:** 2026-09-16

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

### Alcance IN — Rebanada 1

Rotación y pérdidas de contenedores retornables en flota multi-planta usando dataset MB51 sintético (18 meses, 14 plantas, ~1,200 Matnr).

### Alcance OUT (roadmap futuro, NO se ejecuta ahora)

- Rebanada 2: TCO retornable vs desechable (metal vs cartón + tarima madera).
- Rebanada 3: Forecast de necesidad de packaging vs plan de producción MRP.
- Rebanada 4: Cuello de botella del ciclo lavado / reparación.

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

- **Airflow** — overkill para portafolio.
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
  - Pandas: familiar, estándar en cursos IBM, pero lento a este volumen.
  - Polars: sintaxis moderna, 5-10x más rápido, señal de nivel senior.
  - Dask: distribuido, overkill para un laptop.
- **Decisión:** Polars como default para todo el pipeline.
- **Consecuencias:**
  - Curva de aprendizaje inicial de la sintaxis de Polars.
  - README destaca "we use Polars" como diferenciador frente a proyectos IBM/Coursera.

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
- **Contexto:** Las vacantes de SAP AMS / Data Quality piden dbt de forma recurrente.
- **Alternativas evaluadas:**
  - SQL puro en scripts: no escala, no hay linaje.
  - dbt-core con adaptador Postgres: implica servicio Postgres.
  - dbt-duckdb: mismo dbt, sin servicio.
- **Decisión:** dbt-duckdb como capa de modelado.
- **Consecuencias:** Señal fuerte para reclutadores. Documentación y linaje auto-generados.

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

### ADR-005 · Rebanada 1 primero (rotación y pérdidas)

- **Fecha:** 2026-09-16
- **Estado:** Accepted
- **Contexto:** El proyecto completo (todo el ciclo end-to-end de packaging) es demasiado grande. Riesgo de nunca terminar.
- **Alternativas evaluadas:**
  - Ejecutar todo el ciclo: muy grande, se estanca.
  - TCO retornable vs desechable: bueno pero requiere datos financieros.
  - Rotación y pérdidas: universal, output en USD, datos SAP puros.
  - Forecast vs MRP: potente pero exige más integración.
- **Decisión:** Rebanada 1 primero. Otras rebanadas quedan documentadas como roadmap.
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
  - Streamlit: conocido por reclutadores, pero requiere proceso corriendo; no genera artefacto estático.
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
- [x] **Semana 6** · Dashboard con Evidence.dev + versión Power BI descargable.
- [ ] **Semana 7** · CI con GitHub Actions, tests automáticos, badges en README.
- [ ] **Semana 8** · Pulido README, generación de diagramas finales, LinkedIn post de lanzamiento.

---

## 6. Worklog

Bitácora cronológica. Entrada más reciente al principio.

### 2026-09-18 · Sesión 07

- **Duración:** ~2 h
- **Hecho:**
  - Intento fallido con Evidence.dev: paquete `create-evidence-app` eliminado de npm; nuevo CLI migró a modelo cloud (Evidence Studio).
  - Decisión de reemplazar Evidence.dev por Marimo (ADR-007).
  - `uv add marimo` agregado al entorno del proyecto.
  - `notebooks/02_dashboard.py` creado con 5 secciones: imports + conexión DuckDB read-only, KPIs globales con `mo.stat`, tabla rutas rotas, tabla rotación mensual, tabla ciclo promedio por planta.
  - Headers narrativos Markdown entre secciones.
  - Dashboard corriendo en `localhost:2718` con datos reales de los marts.
  - Commit y push: `semana 6: dashboard Marimo con KPIs, rutas rotas y ciclo de retorno`.
- **Decisiones tomadas:** ADR-007 (Marimo sobre Evidence.dev).
- **Bloqueos:** ninguno.
- **Próximo paso:** Semana 7 — CI con GitHub Actions, tests automáticos, badges en README.

### 2026-09-18 · Sesión 06

- **Duración:** ~2 h
- **Hecho:**
  - Creado `notebooks/01_analisis_perdidas.ipynb` completo.
  - Instalado matplotlib via `uv add matplotlib`.
  - Creado directorio `docs/img/` para guardar gráficos.
  - 6 secciones: headline USD, tendencia mensual, pareto plantas, top materiales, rutas rotas, resumen ejecutivo.
  - 3 gráficos guardados: `perdidas_mensual.png`, `pareto_plantas.png`, `top15_materiales.png`, `scatter_rutas_rotas.png`.
  - Detectado y corregido: `tasa_merma_pct` en `mart_rutas_rotas` almacenado como % entero, no decimal.
  - Detectado: distribución de pérdidas entre plantas muy uniforme (refleja generador sintético con merma sin varianza por planta).
- **Decisiones tomadas:** ninguna nueva.
- **Bloqueos:** ninguno.
- **Próximo paso:** Semana 6 — dashboard con Evidence.dev + versión Power BI descargable.

### 2026-09-18 · Sesión 05

- **Duración:** ~3 h
- **Hecho:**
  - MaterialCost en config.py: clase Pydantic con KLT $25, Rack $180, Cartón $8.
  - StrEnum aplicado a Country y MaterialType (Ruff UP042).
  - costo_usd propagado en build_matnr_pool y emit_plant_movements.
  - generate() refactorizado a list[pl.DataFrame] por planta — resuelve OOM.
  - generate() movida al final del archivo (orden de definición correcto).
  - Dataset regenerado: 15,550,868 filas × 17 columnas.
  - DuckDB reingestado. stg_mb51.sql actualizado con costo_usd.
  - models/intermediate/int_ciclo_retorno.sql: left join 601→602 con ventana 120 días, flag es_merma.
  - models/marts/mart_rotacion_planta.sql: rotación mensual por planta con ciclo p50/p90.
  - models/marts/mart_perdidas_usd.sql: pérdidas en USD por material/planta/mes.
  - models/marts/mart_rutas_rotas.sql: rutas con tasa_merma > 5% o ciclo > 45 días.
  - dbt run: PASS=5 WARN=0 ERROR=0.
- **Decisiones tomadas:** ninguna nueva.
- **Bloqueos:** ninguno.
- **Próximo paso:**
  - Semana 5: notebook analítico narrativo con storytelling de negocio y cifras en USD.

### 2026-09-17 · Sesión 03

- **Duración:** ~3 h
- **Hecho:**
  - config.py: modelo Pydantic completo con PlantConfig, MaterialMix, CycleConfig, CpudtLagConfig y GeneratorConfig. Validadores de suma=1.0 y rangos de negocio.
  - generator.py: build_matnr_pool (1,200 Matnr, mix 60/30/10), assign_matnr_to_plants (40% global con solape, 480 por planta), build_date_range (fechas hábiles 18 meses), emit_plant_movements (Bwart mix realista, lag Cpudt/Budat 92/6/2, Lgort coherente con Bwart), apply_return_cycle (ciclo log-normal 601→602, merma 2.01%).
  - Dataset completo generado: 15,550,868 filas × 16 columnas en data/raw/mb51_synthetic.parquet.
  - Tasa de merma real: 2.01% (objetivo 2.0%).
- **Decisiones tomadas:** ADR-007 (Matnr por planta: pool global 40% sin límite estricto de 250, Opción A confirmada por dominio RPL).
- **Bloqueos:** ninguno.
- **Notas de la sesión:**
  - Límite ge=1_000 en monthly_movements_min/max ajustado a ge=100 para permitir pruebas con volumen reducido.
  - El volumen final (15.5M) supera el objetivo de 10M porque la semilla cayó hacia el extremo alto del rango 40k-80k en varias plantas. Rango correcto, resultado válido.
- **Próximo paso:**
  - Validación Pandera del dataset contra MB51Schema.
  - Notebook notebooks/00_sanity_check.ipynb: conteo por Bwart/planta/mes, histograma ciclo 601→602, distribución lag Cpudt/Budat, tasa de merma global y por planta.
  - **Actualización al cierre:**
  - Validación Pandera OK contra MB51Schema (strict=False para 16 de 22 columnas).
  - Notebook 00_sanity_check.ipynb: shape, Bwart mix, ciclo 601→602 (media 24.9 días, P99 85.8), merma 2.0% uniforme en 14 plantas, lag Cpudt/Budat ~92% mismo día.
  - Ajustes en schema.py: Optional en 6 columnas opcionales, tipos corregidos (Budat/Cpudt → date, Menge → int sin gt=0, Zeile → str, Lifnr/Kunnr → str_length 1-12, Cputm → str_length 6-8).
  - 5 commits en esta sesión. Total acumulado: ~16 commits en main.


### 2026-09-16 · Sesión 01

- **Duración:** ~2 h
- **Hecho:**
  - Definido proyecto: rebanada 1 (rotación y pérdidas de RPL).
  - Definido stack completo por capas (esencial, diferenciador, opcional).
  - Definidos parámetros del generador sintético (14 plantas, 1,200 Matnr, mix por tipo, merma 2%, ciclo 25 días).
  - Definido diccionario de datos con 16 columnas core + 6 opcionales MB51 (22 en total).
  - Definido sistema de docs: PROYECTO.md único con 7 secciones + README.md público separado.
  - Confirmado entorno: Windows + Git + VS Code + PowerShell.
- **Decisiones tomadas:** ADR-001 a ADR-006.
- **Bloqueos:** Ninguno.
- **Próximo paso:**
  - Crear repo `returnable-packaging-intelligence` en GitHub (público).
  - Clonar localmente en `C:\proyectos\returnable-packaging-intelligence`.
  - Pegar este PROYECTO.md.
  - Preparar scaffold de semana 1 (estructura de carpetas, `pyproject.toml`, README v0, primer módulo del generador).

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