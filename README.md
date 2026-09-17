# returnable-packaging-intelligence

Análisis de rotación, ciclo y pérdidas de contenedores retornables en flota multi-planta usando datos MB51 sintéticos. Modela el comportamiento real de una operación de Returnable Packaging Logistics (RPL) automotriz: 14 plantas entre México, Estados Unidos y Nicaragua, ~1,200 SKUs de empaque, 18 meses de historia, ~10M movimientos.

El objetivo es aterrizar en KPIs accionables para un equipo de gobernanza de RPL: cuánto se pierde en USD, en qué rutas cliente se pierde primero, qué SKUs pasan de "activos" a "flota fantasma", y qué tan disciplinado es el registro operativo comparado con la fecha real del movimiento.

## Disclaimer

Todos los datos de este repositorio son **sintéticos**. Se generan por código a partir de reglas de negocio publicadas en `PROYECTO.md`. No provienen de ningún sistema SAP productivo, ni de datos anonimizados de ningún empleador pasado o presente. El generador vive en `src/rpi/` y es 100% reproducible con `uv sync` + un comando.

## Problema

Los suppliers Tier-1 de industria automotriz manejan flotas de contenedores retornables (racks metálicos, KLTs plásticos) que ciclan entre planta y cliente. La tasa típica de pérdida anual está entre 2% y 5%. En una flota mediana eso son cientos de miles de dólares que se registran como activos en SAP pero que en la práctica ya no vuelven.

MB51 registra cada movimiento (clase 501, 601, 311, etc.) pero por sí solo no responde:

- ¿Cuántos días tarda en promedio un empaque en volver de cliente? (ciclo 601→602)
- ¿Qué rutas cliente concentran las pérdidas?
- ¿Qué SKUs cruzaron un umbral que sugiere pérdida no reconocida?
- ¿La disciplina de registro varía por planta? (lag Cpudt vs Budat)

Este proyecto construye el pipeline analítico que sí responde esas preguntas.

## Approach

Batch, no streaming. Pipeline reproducible corrido localmente sin infraestructura cloud.

```mermaid
flowchart LR
    A[Generador<br/>sintético] -->|Parquet| B[data/raw]
    B --> C[DuckDB<br/>ingesta]
    C --> D[dbt staging<br/>+ tests]
    D --> E[dbt marts<br/>KPIs rotación<br/>y pérdidas]
    E --> F[Notebook<br/>narrativo]
    E --> G[Dashboard<br/>Evidence.dev]
```

El generador produce los movimientos MB51 con reglas realistas: mix por tipo de empaque, ciclo log-normal 601→602 con cola larga, tasa de no-retorno del 2% distribuida entre rutas, lag Cpudt/Budat con distribución 92/6/2. Los parámetros están documentados en `PROYECTO.md` sección 4.

## Stack

Elegí este stack apuntando a un pipeline analítico reproducible sin depender de infraestructura administrada. Los ADRs con contexto y alternativas descartadas están en `PROYECTO.md` sección 3.

| Capa | Herramienta | Por qué |
|------|-------------|---------|
| DataFrames | Polars | 5-10x más rápido que Pandas a 10M filas. Sintaxis moderna. |
| Warehouse local | DuckDB | Motor OLAP embebido. Cero infraestructura. |
| Modelado analítico | dbt-duckdb | Linaje, tests y docs auto-generados. |
| Validación de schemas | Pandera | Contrato explícito sobre las 18 columnas MB51. |
| Generación sintética | NumPy + Faker | Distribuciones realistas por parámetro. |
| Persistencia | Parquet | Columnar comprimido, interoperable. |
| Package manager | uv | Setup en segundos. Reemplaza pip + venv + poetry. |
| Lint + format | Ruff | Rápido, opinado, un solo binario. |
| Tests | pytest + pytest-cov | Estándar. |
| CI | GitHub Actions | Tests y lint en cada push. |

Explícitamente descartado: Pandas, Airflow, Postgres, Snowflake. Ver ADRs para el razonamiento.

## Requisitos

- Python 3.11 o superior.
- [uv](https://github.com/astral-sh/uv) instalado.
- Git.

## Setup local

Clonar y levantar el entorno:

```bash
git clone https://github.com/juancarlospradologistica-hub/returnable-packaging-intelligence.git
cd returnable-packaging-intelligence
uv sync --all-extras
```

Verificar que Polars y DuckDB cargan:

```bash
uv run python -c "import polars, duckdb; print(polars.__version__, duckdb.__version__)"
```

## Estructura del repo

## Estado actual

Semana 1 del roadmap. Scaffold del proyecto, schema Pandera de las 18 columnas MB51, dependencias declaradas.

Roadmap completo por semanas en `PROYECTO.md` sección 5.

## Licencia

MIT. Ver `LICENSE`.