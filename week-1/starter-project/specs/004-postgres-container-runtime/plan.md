# Implementation Plan: Persistencia relacional dedicada y runtime en contenedores

**Branch**: `004-postgres-container-runtime` | **Date**: 2026-11-24 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/004-postgres-container-runtime/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command; its definition describes the execution workflow.

## Summary

Exponer un chequeo de salud real (`GET /health` + comando CLI `health`) que delega en
`IncidentRepositoryPort.check_health()`, construir un segundo adaptador de salida
(`PostgresIncidentRepository`, vía `psycopg[binary]`, SQL nativo sin ORM) que cumple
exactamente el mismo puerto que `SQLiteIncidentRepository`, y seleccionarlo de forma
transparente a través de `DATABASE_URL` en una `factory.create_repository(database_url)`
reutilizable. El runtime se empaqueta en dos contenedores (`api` + `db`, Docker Compose)
para una ejecución reproducible, sin alterar ninguna regla de dominio ni el resultado de
negocio ya vigente en H001-H002. Implementa ADR-004 y la Constitución v1.1.0 (Principio
III), y materializa `specs/004-postgres-container-runtime/spec.md`.

## Technical Context

**Language/Version**: Python >= 3.10 (igual que el resto del proyecto); la imagen de
contenedor del servicio `api` estandariza en `python:3.12-slim` (satisface el mínimo del
proyecto; no cambia `requires-python` de `pyproject.toml`, que sigue siendo `>=3.10` para
no restringir el desarrollo local fuera de contenedores).

**Primary Dependencies**: FastAPI + Pydantic v2 (REST, sin cambios), Typer (CLI, sin
cambios), `psycopg[binary]>=3.3.9` (ya añadido a `pyproject.toml`/`uv.lock`), `sqlite3` de
la biblioteca estándar, `uv` como gestor de entorno dentro y fuera de los contenedores.

**Storage**: Persistencia dual sin ORM (ADR-004): `sqlite3` para desarrollo/pruebas
(incluye `sqlite:///:memory:` por defecto) y PostgreSQL 16 (`postgres:16-alpine` en el
servicio `db` de Docker Compose) para producción, vía `psycopg[binary]`. Timestamps
almacenados como texto ISO 8601 (`TEXT`) en ambos motores, para paridad exacta.

**Testing**: `pytest` (`uv run pytest -v`), reutilizando el patrón ya establecido en
`tests/conftest.py` (`TestClient` de FastAPI + `CliRunner` de Typer, cada prueba con su
propio repositorio aislado). El motor PostgreSQL se verifica de forma estructural
(conformidad con `IncidentRepositoryPort`) sin requerir un servidor PostgreSQL en
ejecución durante `pytest` (ver `research.md`, Decisión 4).

**Target Platform**: Linux en contenedores (Docker/Docker Compose) para el runtime
reproducible de H004; desarrollo local multiplataforma (Windows/macOS/Linux) sin
contenedores sigue soportado contra SQLite, sin cambios.

**Project Type**: Proyecto único existente (servicio web + CLI sobre arquitectura
hexagonal); esta funcionalidad no introduce un proyecto nuevo, solo un segundo adaptador
de salida y los artefactos de contenedores.

**Performance Goals**: No se definieron metas cuantitativas de rendimiento en `spec.md`
(fuera de alcance de H004; ver Criterios de Éxito, que son cualitativos). El chequeo de
salud es una operación síncrona de bajo costo (una sola consulta `SELECT 1` o
equivalente); no se introduce procesamiento asíncrono ni paralelo.

**Constraints**: Fronteras hexagonales intactas (Constitución, Principio II):
`src/domain/` y `src/application/` no importan `psycopg`, `sqlite3`, FastAPI, Typer ni
Pydantic. Todo valor SQL viaja parametrizado (`?` en SQLite, `%s` en PostgreSQL); sin
interpolación de entrada de usuario. Los dos adaptadores de salida deben producir
resultados de negocio idénticos para la misma entrada (FR-006). `uv run ruff check src/`
y `uv run pytest -v` deben pasar en verde (Constitución, Principios IV y V).

**Scale/Scope**: Alcance acotado a H004 (ver `docs/ROADMAP.md`): un adaptador de salida
nuevo, una fábrica con selección dual, un método de servicio, dos interfaces de entrada
(HTTP + CLI) para el chequeo de salud, y los artefactos de contenedores. No incluye alta
disponibilidad, replicación, migración de datos entre motores ni monitoreo avanzado.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principio / Regla | Evaluación | Cumplimiento planeado |
|---|---|---|
| I. Núcleo Determinista Único | PASA | El chequeo de salud no evalúa ninguna regla de triaje/SLA/duplicados; no lee `reference_time` ni el reloj del sistema; `check_health()` no tiene parámetros. |
| II. Arquitectura Hexagonal Estricta (ADR-003) | PASA, con ajuste de frontera requerido | `PostgresIncidentRepository` vive en `src/adapters/outbound/` (permitido usar `psycopg`); `src/application/services.py` solo agrega `IncidentService.check_health()` delegando en el puerto, sin reimplementar nada; los adaptadores de entrada (`api/app.py`, `cli.py`) solo traducen HTTP/CLI al mismo servicio. **Ajuste requerido**: `src/adapters/inbound/ruff.toml` y `src/application/ruff.toml` deben extender su `banned-api` para prohibir `psycopg` y el import directo de `src.adapters.outbound.postgres_repository`, igual que ya hacen con `sqlite3`/`sqlite_repository` (paridad de frontera para el nuevo adaptador). |
| III. Gobernanza del Stack Tecnológico (ADR-001, ADR-004) | PASA | `psycopg[binary]` ya es la única dependencia nueva, ya aprobada por ADR-004 y ya declarada en `pyproject.toml`; sin ORM; SQL nativo parametrizado en ambos motores; selección exclusiva por `DATABASE_URL`. |
| IV. Verificación Estática de Fronteras Hexagonales (Ruff) | PASA tras el ajuste de la fila II | `uv run ruff check src/` debe pasar sin TID251/TID252 incluyendo las nuevas reglas banned-api. |
| V. Calidad mediante Pruebas BDD Obligatorias (pytest) | PASA | `tests/test_spec_004_runtime_health.py` cubre las 3 Historias de Usuario de `spec.md` con escenarios Given/When/Then, reutilizando fixtures aisladas por prueba; deterministas (sin reloj de pared, el chequeo de salud no depende de tiempo). |
| Cumplimiento Operativo — ADR obligatorio para cambios estructurales | PASA | ADR-004 ya existe y ya está ratificado en la Constitución v1.1.0; esta funcionalidad lo implementa, no abre una decisión arquitectónica nueva. |
| Cumplimiento Operativo — Idioma | PASA | Código, comentarios y documentación generados en español, consistente con el resto del proyecto. |

No hay violaciones sin justificar; el único punto que exige trabajo adicional (fila II) es
una tarea de paridad de configuración, no una excepción a los principios. **Complexity
Tracking queda vacía** (ver abajo).

## Project Structure

### Documentation (this feature)

```text
specs/004-postgres-container-runtime/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md         # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
│   └── health-check.md
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
week-1/starter-project/
├── src/
│   ├── domain/                              # sin cambios (sin acceso a psycopg/sqlite3)
│   ├── application/
│   │   ├── ports.py                         # sin cambios (check_health ya declarado, H003)
│   │   ├── services.py                      # + IncidentService.check_health()
│   │   └── ruff.toml                        # + banned-api: psycopg, postgres_repository
│   └── adapters/
│       ├── inbound/
│       │   ├── api/
│       │   │   ├── app.py                   # + GET /health (200/503)
│       │   │   └── schemas.py               # + HealthResponseSchema
│       │   ├── cli.py                       # + comando `health`
│       │   └── ruff.toml                    # + banned-api: postgres_repository
│       └── outbound/
│           ├── sqlite_repository.py         # sin cambios
│           ├── postgres_repository.py       # NUEVO: PostgresIncidentRepository
│           └── factory.py                   # + create_repository(database_url); conserva
│                                             #   get_incident_repository() como wrapper
│                                             #   fino sobre DATABASE_URL del entorno
├── tests/
│   ├── conftest.py                          # + fixtures del chequeo de salud (doble de prueba)
│   └── test_spec_004_runtime_health.py      # NUEVO
├── Dockerfile                               # NUEVO (python:3.12-slim + uv)
├── .dockerignore                            # NUEVO
└── docker-compose.yml                       # NUEVO (servicios api + db)
```

**Structure Decision**: Se reutiliza la estructura hexagonal ya vigente (Constitución,
Principio II); no se crea ningún proyecto, carpeta de nivel superior ni capa nueva. El
único archivo de código nuevo en `src/` es `postgres_repository.py`, como segundo
adaptador de salida detrás del mismo `IncidentRepositoryPort`; todo lo demás son
modificaciones acotadas a archivos existentes más los tres artefactos de contenedores en
la raíz de `week-1/starter-project/` (mismo nivel que `pyproject.toml`, consistente con
"Run every command from there" de `AGENTS.md`).

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

*(Vacía: ninguna violación de la Constitución requiere justificación en este plan.)*

## Re-evaluación de la Constitución (post-diseño, Fase 1)

`research.md` y `data-model.md` no introducen ningún elemento nuevo que la tabla de
"Constitution Check" no haya anticipado: el esquema de PostgreSQL reutiliza exactamente
las columnas e índices de SQLite (Principio III/ADR-001/ADR-004), `check_health()` sigue
sin reglas de negocio (Principio I), y la estrategia de prueba de la Decisión 4 de
`research.md` mantiene `uv run pytest -v` determinista y sin dependencia de Docker
(Principio V). La única acción pendiente sigue siendo la paridad de `banned-api` en
`src/application/ruff.toml` y `src/adapters/inbound/ruff.toml` (fila II de la tabla
anterior), que `tasks.md` debe incluir como tarea explícita antes de cerrar la
funcionalidad. **Gate: PASA.**
