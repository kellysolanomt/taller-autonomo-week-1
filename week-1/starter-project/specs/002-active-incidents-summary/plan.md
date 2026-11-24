# Implementation Plan: Resumen de incidentes activos (H002)

**Branch**: `002-active-incidents-summary` | **Date**: 2026-11-23 | **Spec**: [spec.md](./spec.md)

**Input**: Especificación de funcionalidad desde `/specs/002-active-incidents-summary/spec.md`, más la instrucción explícita del usuario de diseñar el Hito 002 respetando la Arquitectura Hexagonal de `docs/constitution.md` (Artículo 2) y el diseño objetivo ya descrito en el skill `hexagonal-architecture` y en `docs/adr/003-arquitectura-hexagonal.md`.

**Note**: This template is filled in by the `/speckit.plan` command; its definition describes the execution workflow.

## Summary

H002 expone el resumen de incidentes activos (total, incumplimientos de SLA y detalle) por HTTP y CLI, con filtro opcional por componente e instante de referencia opcional (FR-001 a FR-013). El enfoque técnico extrae la persistencia SQLite heredada de Semana 1 hacia un adaptador de salida (`src/adapters/outbound/`) detrás de un puerto `IncidentRepositoryPort` (`typing.Protocol`), mueve la evaluación de SLA — hoy incorrectamente acoplada al repositorio — a `IncidentService.get_active_incidents_summary` en `src/application/services.py`, y añade los adaptadores de entrada paritarios (`GET /api/v1/incidents/summary` en FastAPI, comando `summary` en Typer). Se incorpora además la validación estática de fronteras con Ruff (`TID251`/`TID252`) ya especificada en el skill `hexagonal-architecture`, materializándola por primera vez en `pyproject.toml` y en archivos `ruff.toml` jerárquicos por capa.

## Technical Context

**Language/Version**: Python >= 3.10, gestionado con `uv` (sin cambios respecto a H001).

**Primary Dependencies**: FastAPI + Pydantic v2 (REST), Typer (CLI), `sqlite3` de la biblioteca estándar (persistencia), `ruff` (análisis estático de fronteras, ya en `dependency-groups.dev`). Ninguna dependencia nueva fuera de las ya declaradas en `pyproject.toml`.

**Storage**: SQLite vía el adaptador de salida `SQLiteIncidentRepository`, seleccionado por `DATABASE_URL` (por defecto `sqlite:///:memory:`). Solo se soporta el esquema `sqlite:///` en este corte; cualquier otro esquema queda explícitamente fuera de alcance y diferido a H004 (motor relacional dedicado, Constitución 3.2: "cualquier cambio de motor de base de datos exige un ADR aprobado previamente"); no es una incógnita pendiente de resolver, es un límite de alcance ya decidido.

**Testing**: `pytest` + `TestClient` (FastAPI) + `CliRunner` (Typer), igual que H001, con almacenamiento aislado por prueba (`SQLiteIncidentRepository(":memory:")` nuevo por test, nunca compartido), conforme al skill `bdd-acceptance`.

**Target Platform**: Igual que H001 — ejecución local vía `uv run uvicorn ...` / `uv run python -m src.adapters.inbound.cli`, sin despliegue nuevo.

**Project Type**: Proyecto único con doble adaptador de entrada (web-service + CLI) sobre el mismo núcleo hexagonal; no aplica la opción de "frontend + backend" ni "mobile + API" del template.

**Performance Goals**: SC-006 — resumen completo (total, incumplimientos, detalle) en menos de 2 segundos con hasta ~100 incidentes activos simultáneos, sin paginación.

**Constraints**:
- Determinismo: `src/domain/` y `src/application/` nunca leen el reloj del sistema (Constitución 1.2); el único punto donde se permite `datetime.now()` es el borde (adaptadores de entrada), para resolver el valor por defecto de `reference_time` cuando el llamador no lo indica (FR-013). Ver resolución detallada en `research.md`.
- Datetimes naive únicamente; cualquier `tzinfo` sigue lanzando `ValueError` vía `evaluate_sla_status` (sin cambios).
- SQL solo con placeholders `?`; ningún valor de usuario se interpola (Constitución 3.3), incluido el nuevo filtro de componente.
- Paridad de resultado de negocio entre HTTP y CLI (FR-002, SC-002): ambos adaptadores deben invocar exactamente `IncidentService.get_active_incidents_summary(...)`.

**Scale/Scope**: ~100 incidentes activos simultáneos (panel de guardia tipo, ver Clarifications de `spec.md`); no se diseña para paginación ni para el volumen sintético de 10,000 registros usado en el benchmark pedagógico de `src/incident_repository.py` (ese módulo no se modifica, ver Project Structure).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Fuente normativa**: esta evaluación cita `docs/constitution.md` (Artículos 1–4) por su numeración más legible, y cada fila añade el principio equivalente en la constitución ratificada por Spec Kit, `.specify/memory/constitution.md` (v1.0.0, Principios I–V), que es la que `/speckit.plan`/`/speckit.tasks`/`/speckit.analyze` tratan como no negociable. Ambos documentos son sustantivamente consistentes para H002; `.specify/memory/constitution.md` prevalece ante cualquier conflicto textual (p. ej., el flag exacto de `pytest`: `-v`, no `-q` — ver AGENTS.md).

| Artículo de la Constitución (`docs/constitution.md`) | Principio equivalente (`.specify/memory/constitution.md`) | Evaluación para H002 |
|---|---|---|
| 1.1 Dominio único de verdad | I. Núcleo Determinista Único | Cumple. El resumen reutiliza `src/domain/sla_calculator.py` tal cual; ninguna regla de SLA se reimplementa en `src/application/` ni en los adaptadores. La agregación (total, incumplimientos, detalle) es orquestación de aplicación, no una regla de dominio nueva. |
| 1.2 Determinismo / reloj del sistema | I. Núcleo Determinista Único | Cumple, con una resolución explícita: `IncidentService.get_active_incidents_summary` exige `reference_time` como parámetro obligatorio (nunca lo calcula internamente); el valor por defecto "instante de la consulta" (FR-013) se calcula con `datetime.now()` únicamente en el adaptador de entrada (ruta FastAPI / comando Typer), que luego lo pasa como argumento concreto. Esto preserva la prohibición de leer el reloj en dominio/aplicación y mantiene las pruebas deterministas (siempre inyectan `reference_time` explícito). |
| 1.4/1.5 SLA y escalamiento | Restricciones de Dominio y Seguridad (SLA/Escalamiento) | Cumple sin cambios de regla. El ítem de detalle expone `elapsed_minutes` y `requires_escalation` (FR-005); no se añade un campo `is_breached` por ítem porque, para un incidente activo (no `RESOLVED`), `is_breached=True` implica `requires_escalation=True` (el umbral de escalamiento, 75%, es siempre menor al umbral de incumplimiento, 100%); el `breached_count` agregado ya satisface FR-004 sin duplicar el dato en cada ítem. |
| 1.8 Duplicados | Restricciones de Dominio y Seguridad (Duplicados) | No aplica a H002 (el resumen no reporta duplicados); el puerto incluye `find_open_duplicates` como preparación explícita para H003, sin conectarse a ningún caso de uso de H002 (ver `research.md`, Decisión 4). |
| 2.1–2.5 Arquitectura hexagonal | II. Arquitectura Hexagonal Estricta (ADR-003) | Cumple y es el objeto central de este plan: se crea el puerto de salida (`src/application/ports.py`), se extrae el adaptador de salida (`src/adapters/outbound/`) y se mantiene la paridad entre adaptadores de entrada. La dirección de dependencias permanece hacia adentro. El Principio II nombra explícitamente `DATABASE_URL` como el mecanismo de selección en tiempo de ejecución — exactamente lo que implementa `factory.py` (T009). |
| 3.2 Motor de BD / ADR previo | III. Gobernanza del Stack Tecnológico (ADR-001) | Cumple. No se cambia de motor (sigue siendo SQLite); `DATABASE_URL` solo selecciona *dónde* vive el archivo SQLite, no un motor distinto, por lo que no dispara la exigencia de un ADR nuevo por este concepto. |
| 3.3 Seguridad SQL | III. Gobernanza del Stack Tecnológico; Restricciones de Dominio y Seguridad (Seguridad SQL) | Cumple. El filtro de componente y el conjunto de estados activos siguen viajando como parámetros `?`, igual que en `src/incident_repository.py` (ADR-001). |
| 3.4 Calidad BDD | V. Calidad mediante Pruebas BDD Obligatorias (pytest) | Cumple. `tests/test_spec_002_summary.py` mapea 1:1 los 8 escenarios de aceptación de `spec.md` (convención `test_bdd_*` del skill `bdd-acceptance`), más una prueba de solo-lectura (FR-011/FR-012) y una de rendimiento (SC-006) añadidas tras el análisis de `/speckit.analyze`. El comando de verificación es `uv run pytest -v` (Principio V), no `-q`; `AGENTS.md`, `quickstart.md` y `tasks.md` ya quedaron alineados a ese flag. |
| 4.1 ADR para cambio estructural | Cumplimiento Operativo y Jerarquía Normativa; Governance | **Ya satisfecho por un ADR existente**: `docs/adr/003-arquitectura-hexagonal.md` ya decide y diagrama (Mermaid) exactamente esta forma — puerto de salida vía `Protocol`, repositorio SQLite como adaptador de salida, chequeo de conectividad. H002 *realiza* esa decisión ya tomada; no introduce una decisión estructural nueva que requiera un ADR adicional. La única pieza no cubierta explícitamente por el diagrama de ADR-003 es el mecanismo de selección por `DATABASE_URL`, pero el Principio II ya lo nombra directamente, y es cableado de borde (Art. 2.5), no una decisión de arquitectura nueva. |

**Resultado**: PASA. No hay violaciones que requieran justificación en Complexity Tracking.

**Nota operativa (no bloquea el gate)**: `AGENTS.md` describe hoy que `src/incident_repository.py` "sigue en `src/` tal como estaba". Este plan no mueve ni borra ese archivo (ver Project Structure): es un módulo de benchmark pedagógico de Semana 1 (`uv run python -m src.incident_repository`), independiente del nuevo adaptador de salida `src/adapters/outbound/sqlite_repository.py`. `AGENTS.md` deberá actualizarse como parte de la implementación para reflejar la nueva capa `src/adapters/outbound/`, pero eso es un seguimiento documental, no una razón para detener este plan.

### Re-evaluación tras el diseño de Fase 1

Tras producir `research.md`, `data-model.md`, `contracts/incidents-summary.md` y `quickstart.md`, se repasó la tabla anterior contra el diseño concreto: el puerto quedó en `typing.Protocol` (2.2), el repositorio de salida solo devuelve `Incident` sin evaluar SLA (1.1, Decisión 2 de `research.md`), el reloj del sistema solo se lee en los adaptadores de entrada (1.2, Decisión 3), ningún valor de usuario se interpola en SQL (3.3) y los 8 escenarios de aceptación tienen una función `test_bdd_*` planeada 1:1 (3.4 / Principio V). **Resultado**: PASA sin cambios respecto a la evaluación inicial; ninguna decisión de Fase 1 introdujo una violación nueva.

### Re-evaluación tras `/speckit.analyze`

`/speckit.analyze` detectó que la cobertura de `tasks.md` dejaba sin prueba a FR-011/FR-012 (solo-lectura/idempotencia) y a SC-006 (rendimiento con ~100 incidentes), y que el comando de verificación citado en `quickstart.md`/`tasks.md` (`pytest -q`) no coincidía con el Principio V de `.specify/memory/constitution.md` (`pytest -v`). Se añadieron T031/T032 a `tasks.md` y se alinearon `AGENTS.md`, `specs/001-triage-endpoint-manual.md`, el skill `bdd-acceptance`, `quickstart.md` y `tasks.md` al flag `-v` de la constitución ratificada, en vez de amender el Principio V. **Resultado**: PASA; Constitution Check sigue sin violaciones pendientes de justificar.

## Project Structure

### Documentation (this feature)

```text
specs/002-active-incidents-summary/
├── spec.md                  # Ya existe (clarificado y validado)
├── plan.md                  # Este archivo (/speckit.plan)
├── research.md              # Fase 0 (/speckit.plan)
├── data-model.md            # Fase 1 (/speckit.plan)
├── quickstart.md            # Fase 1 (/speckit.plan)
├── contracts/
│   └── incidents-summary.md # Fase 1 (/speckit.plan) — contrato HTTP + CLI
├── checklists/
│   └── requirements.md      # Ya existe (16/16)
└── tasks.md                 # Fase 2 (/speckit.tasks — fuera de este comando)
```

### Source Code (repository root = `week-1/starter-project/`)

```text
src/
├── domain/
│   ├── models.py            # + campo opcional `symptom_category` en `Incident` (aditivo)
│   ├── triage_rules.py       # sin cambios
│   ├── sla_calculator.py     # sin cambios (se reutiliza tal cual desde application)
│   └── ruff.toml              # nuevo: banned-api (FastAPI/Typer/Pydantic/sqlite3/src.adapters/src.application)
├── application/
│   ├── ports.py               # nuevo: IncidentRepositoryPort (Protocol, 5 métodos)
│   ├── services.py            # + get_active_incidents_summary(component_filter, reference_time)
│   │                          #   + dataclasses ActiveIncidentSummaryItem / ActiveIncidentsSummary
│   │                          #   + IncidentService ahora recibe un IncidentRepositoryPort en el constructor
│   └── ruff.toml               # nuevo: banned-api (FastAPI/Typer/Pydantic/sqlite3/src.adapters.*)
├── adapters/
│   ├── inbound/
│   │   ├── api/
│   │   │   ├── app.py          # + GET /api/v1/incidents/summary; create_app(service: IncidentService | None)
│   │   │   └── schemas.py      # + ActiveIncidentItemSchema, ActiveIncidentsSummaryResponseSchema
│   │   ├── cli.py              # + comando `summary`; refactor a create_cli_app(service) + app = create_cli_app(...)
│   │   └── ruff.toml           # nuevo: banned-api (sqlite3, src.incident_repository, repositorio concreto outbound)
│   └── outbound/               # nuevo paquete
│       ├── __init__.py
│       ├── sqlite_repository.py  # nuevo: SQLiteIncidentRepository(IncidentRepositoryPort)
│       └── factory.py            # nuevo: get_incident_repository() a partir de DATABASE_URL
├── incident_repository.py      # SIN CAMBIOS — benchmark pedagógico de Semana 1 (N+1 vs. consulta optimizada)
└── context_audit.py             # sin cambios

tests/
├── conftest.py                  # + fixtures: incident_repository, incident_service,
│                                 #   summary_api_client, summary_cli_app (almacenamiento aislado por test)
└── test_spec_002_summary.py     # nuevo: 8 funciones test_bdd_* (una por escenario de aceptación de spec.md)
    │                             #   + test_bdd_resumen_es_solo_lectura_sin_efectos_secundarios (FR-011/FR-012)
    │                             #   + prueba de rendimiento (SC-006) y de cumplimiento de IncidentRepositoryPort

pyproject.toml                   # + [tool.ruff.lint] select = ["E4", "E7", "E9", "F", "TID"]
```

**Structure Decision**: Se conserva el proyecto único con doble adaptador de entrada ya establecido en H001; la única estructura nueva es el paquete `src/adapters/outbound/` (puerto de salida materializado) y los archivos `ruff.toml` jerárquicos por capa, ambos ya anticipados en `docs/adr/003-arquitectura-hexagonal.md` y en el skill `hexagonal-architecture`. No se introduce ninguna carpeta fuera de `src/`, `tests/` y `specs/002-active-incidents-summary/`.

## Complexity Tracking

> Fill ONLY if Constitution Check has violations that must be justified

Sin violaciones — ver tabla de Constitution Check arriba. No aplica.
