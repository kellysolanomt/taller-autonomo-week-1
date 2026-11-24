# Implementation Plan: Ciclo de vida de incidentes, duplicados y SLA (H003)

**Branch**: `003-incident-lifecycle-duplicates-sla` | **Date**: 2026-11-24 | **Spec**: [spec.md](./spec.md)

**Input**: Especificación de funcionalidad desde
`/specs/003-incident-lifecycle-duplicates-sla/spec.md`, más la instrucción explícita del usuario
de planear H003 respetando estrictamente `.specify/memory/constitution.md` y el skill
`hexagonal-architecture`, cubriendo las cinco capas: Dominio (`src/domain/`), Aplicación
(`src/application/services.py`), Adaptador Secundario (`src/adapters/outbound/sqlite_repository.py`),
Adaptadores Primarios (`src/adapters/inbound/`) y Pruebas (`tests/test_spec_003_lifecycle_sla.py`).

**Note**: This template is filled in by the `/speckit.plan` command; its definition describes the execution workflow.

## Summary

H003 cierra el ciclo de vida de un incidente: registrarlo (con la misma clasificación automática
de H001), alertar si ya hay un equivalente abierto (sin bloquear el registro), y auditar su SLA
para cualquier instante de referencia — todo por HTTP y por CLI, con el mismo resultado de negocio
(FR-001 a FR-020). El enfoque técnico extiende `Incident` (dominio) con `recommended_team` y
`duplicate_group_key` para que el adaptador de salida pueda indexar duplicados por una sola
columna (`idx_incidents_dup_key` sobre `(duplicate_group_key, status)`); promueve el chequeo de
`tzinfo` de `sla_calculator.py` a una función pública reutilizada por una única función de
parseo ISO 8601 en `src/application/services.py`, que ambos adaptadores primarios comparten;
añade `IncidentService.create_incident`/`evaluate_incident_sla` (con dos excepciones nuevas,
`IncidentConflictError`/`IncidentNotFoundError`) orquestando `classify_incident_report`,
`find_open_duplicates` y `evaluate_sla_status` sin reimplementar ninguna regla; y añade las rutas
`POST /api/v1/incidents`/`GET /api/v1/incidents/{incident_id}/sla` (FastAPI) y los subcomandos
`create`/`sla` (Typer), ambos delegando exclusivamente en `IncidentService`.

## Technical Context

**Language/Version**: Python >= 3.10, gestionado con `uv` (sin cambios respecto a H001/H002).

**Primary Dependencies**: FastAPI + Pydantic v2 (REST), Typer (CLI), `sqlite3` de la biblioteca
estándar (persistencia), `secrets` de la biblioteca estándar (autogeneración de `incident_id`,
`research.md` Decisión 5), `ruff` (análisis estático de fronteras, ya en `dependency-groups.dev`).
Ninguna dependencia nueva fuera de las ya declaradas en `pyproject.toml`.

**Storage**: SQLite vía `SQLiteIncidentRepository`, seleccionado por `DATABASE_URL` (sin cambios
respecto a H002); dos columnas nuevas nullable (`recommended_team`, `duplicate_group_key`) y un
índice nuevo (`idx_incidents_dup_key`) sobre la misma tabla `incidents`. No es un cambio de motor
(sigue siendo SQLite vía `sqlite3`), por lo que no dispara la exigencia de un ADR nuevo
(Constitución, Artículo 3.2).

**Testing**: `pytest` + `TestClient` (FastAPI) + `CliRunner` (Typer), igual que H001/H002, con
almacenamiento aislado por prueba; H003 reutiliza las fixtures ya existentes de
`tests/conftest.py` sin añadir ninguna nueva (`research.md`, Decisión 8).

**Target Platform**: Igual que H001/H002 — ejecución local vía `uv run uvicorn ...` /
`uv run python -m src.adapters.inbound.cli`, sin despliegue nuevo.

**Project Type**: Proyecto único con doble adaptador de entrada (web-service + CLI) sobre el
mismo núcleo hexagonal; no aplica ninguna de las opciones de "frontend + backend" / "mobile + API"
del template.

**Performance Goals**: Sin un criterio de rendimiento propio en `spec.md` (a diferencia de SC-006
de H002); el registro y la auditoría de SLA son operaciones de un solo incidente, no de un
conjunto que crezca con el número total de incidentes activos.

**Constraints**:
- Determinismo: `src/domain/` y `src/application/` nunca leen el reloj del sistema (Constitución,
  Principio I); el único punto donde se permite `datetime.now()` es el borde (adaptadores de
  entrada), para resolver el valor por defecto de `created_at` (al registrar) y `reference_time`
  (al auditar SLA) cuando el llamador no los indica (FR-002, FR-008). Ver `research.md`, Decisión 4.
- Datetimes naive únicamente; cualquier `tzinfo` en `created_at` o `reference_time` se rechaza
  como error de validación (`422`/código `1`), nunca como `ValueError` no controlado ni como
  `500` (FR-020). El chequeo en sí sigue viviendo una sola vez en `src/domain/sla_calculator.py`
  (`require_naive_datetime`, promovida de `_require_naive` — `research.md`, Decisión 1).
- Un valor de fecha-hora malformado (no ISO 8601) o un `status` fuera del enum nunca produce el
  cuerpo/código de error propio del framework subyacente (FastAPI `RequestValidationError`;
  Typer/Click código `2`): siempre `{"error": ...}` con `422`/código `1` (FR-018/FR-019). Por eso
  `created_at`/`reference_time`/`status` viajan como `str` en los esquemas/opciones, nunca como
  `datetime`/enum nativos (`research.md`, Decisión 6).
- SQL solo con placeholders `?`; ningún valor de usuario se interpola (Constitución, Seguridad
  SQL), incluida la nueva columna `duplicate_group_key`.
- Paridad de resultado de negocio entre HTTP y CLI (FR-001, FR-007): ambos adaptadores invocan
  exclusivamente `IncidentService.create_incident(...)`/`IncidentService.evaluate_incident_sla(...)`.

**Scale/Scope**: Igual escala que H001/H002 (decenas de incidentes por prueba/demo); no se
diseña para el volumen sintético de 10,000 registros del benchmark pedagógico
(`src/incident_repository.py`, no modificado).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Fuente normativa**: esta evaluación cita `.specify/memory/constitution.md` (v1.0.0, Principios
I–V) por ser la constitución ratificada que `/speckit.plan`/`/speckit.tasks`/`/speckit.analyze`
tratan como no negociable; donde es útil, se referencia también el artículo equivalente de
`docs/constitution.md` por su numeración más legible. Ambos documentos son sustantivamente
consistentes para H003; `.specify/memory/constitution.md` prevalece ante cualquier conflicto
textual.

| Principio (`.specify/memory/constitution.md`) | Evaluación para H003 |
|---|---|
| I. Núcleo Determinista Único | Cumple. Ninguna regla de triaje, SLA, duplicados o estado se reimplementa fuera de `src/domain/`: `create_incident` delega la clasificación en `classify_incident_report` (sin cambios) y la comparación de duplicados en una consulta de infraestructura sobre un campo (`duplicate_group_key`) que el propio dominio ya calcula en `TriageResult`; `evaluate_incident_sla` delega el cálculo en `evaluate_sla_status` (sin cambios). El único código nuevo en `src/domain/` es la promoción de `_require_naive` a `require_naive_datetime` (mismo cuerpo, mismo `ValueError`) — una reutilización explícita, no una reimplementación. `src/domain/`/`src/application/` nunca leen el reloj del sistema: `created_at`/`reference_time` llegan siempre resueltos desde el adaptador de entrada (ver Constraints arriba y `research.md`, Decisión 4). Los datetimes siguen siendo naive; cualquier `tzinfo` sigue lanzando `ValueError` desde el mismo punto único de `src/domain/sla_calculator.py`. |
| II. Arquitectura Hexagonal Estricta (ADR-003) | Cumple. `src/domain/` sigue sin importar FastAPI/Typer/`sqlite3`/Pydantic ni ningún adaptador (sin cambios de import en `models.py`/`sla_calculator.py` más allá de tipos ya presentes). `src/application/services.py` sigue exponiéndose vía `ports.py` (`IncidentRepositoryPort`, con un método re-firmado — `research.md`, Decisión 2) y `services.py` (`IncidentService`, ahora con dos casos de uso más); sigue sin importar ningún adaptador concreto. `src/adapters/inbound/` resuelve el repositorio exclusivamente vía `src.adapters.outbound.factory.get_incident_repository()` (sin importar `sqlite3` ni `SQLiteIncidentRepository` directamente), igual que H001/H002. `src/adapters/outbound/sqlite_repository.py` sigue siendo la única pieza que conoce el motor SQLite concreto. La dirección de dependencias permanece hacia adentro. |
| III. Gobernanza del Stack Tecnológico (ADR-001) | Cumple. Sigue siendo FastAPI + Pydantic v2 + Typer + `sqlite3` de la biblioteca estándar, sin ORM ni dependencia de persistencia nueva; se añade `secrets` (biblioteca estándar) para `incident_id` autogenerado — no es una dependencia externa ni un motor de BD, no requiere ADR. Todo valor de consulta SQL nuevo (`duplicate_group_key`, `recommended_team`) viaja con placeholders `?`. |
| IV. Verificación Estática de Fronteras Hexagonales (Ruff) | Cumple sin cambios de configuración: H003 no introduce ningún import nuevo prohibido por capa; los `ruff.toml` jerárquicos ya existentes (`src/domain/`, `src/application/`, `src/adapters/inbound/`) siguen cubriendo exactamente las mismas fronteras. `uv run ruff check src/` debe seguir pasando en verde. |
| V. Calidad mediante Pruebas BDD Obligatorias (pytest) | Cumple por diseño: `tests/test_spec_003_lifecycle_sla.py` cubrirá 1:1 los 19 Escenarios de Aceptación de `spec.md` (7+6+6) con funciones `test_bdd_*`, ejecutadas vía `TestClient`/`CliRunner` sobre `SQLiteIncidentRepository(":memory:")` aislado por prueba (fixtures ya existentes, `research.md` Decisión 8); el comando de verificación sigue siendo `uv run pytest -v`. Antes de tocar `sla_calculator.py` (renombrar `_require_naive`), la cobertura existente de `uv run python -m src.domain.sla_calculator` (casos borde de ADR-002) actúa como prueba de caracterización: debe seguir pasando sin cambios de comportamiento. |
| Restricciones de Dominio y Seguridad — Duplicados | Cumple. La clave sigue siendo `<component>:<symptom_category>` (sin cambio de regla); H003 solo decide *cómo se consulta* esa clave ya calculada (columna propia + índice), no *cómo se calcula* (eso sigue en `src/domain/triage_rules.py`). La fusión automática de duplicados sigue fuera de alcance. |
| Restricciones de Dominio y Seguridad — Estados | Cumple. El conjunto de estados que cuentan como "abierto para duplicados" (`OPEN`, `IN_PROGRESS`, `ESCALATION_REQUIRED`) es una regla propia de H003 (clarificación de `spec.md`), distinta y no conflictiva con el conjunto "activo" de H002 (`OPEN`, `IN_PROGRESS`); ambos conjuntos son constantes internas fijas del adaptador de salida, nunca interpoladas. |
| Restricciones de Dominio y Seguridad — Seguridad SQL | Cumple. Las dos columnas nuevas y el índice nuevo siguen el mismo patrón ADR-001 (placeholders `?`, constantes internas fijas para conjuntos de estado). |
| Cumplimiento Operativo — Cambios estructurales (ADR) | **Sin violación, pero con una decisión estructural nueva que amerita registro**: el cambio de firma de `find_open_duplicates` (de `(component, symptom_category)` a `(duplicate_group_key)`) y la promoción de `require_naive_datetime` son refinamientos dentro del diseño ya decidido por `docs/adr/003-arquitectura-hexagonal.md` (puerto `Protocol`, dominio como única fuente de verdad), no una decisión arquitectónica nueva — no alteran qué capa conoce a cuál, solo el detalle interno de una consulta ya prevista. No se requiere un ADR nuevo por este motivo; si la implementación encuentra una tercera alternativa no contemplada en `research.md` (p. ej. cambiar de motor de persistencia), eso sí exigiría un ADR nuevo antes de integrarse. |
| Idioma | Cumple. Todos los artefactos nuevos (`research.md`, `data-model.md`, `contracts/`, `quickstart.md`, este `plan.md`) están en español, igual que el código/documentación existente. |

**Resultado**: PASA. No hay violaciones que requieran justificación en Complexity Tracking.

### Re-evaluación tras el diseño de Fase 1

Tras producir `research.md`, `data-model.md`, `contracts/incident-lifecycle-sla.md` y
`quickstart.md`, se repasó la tabla anterior contra el diseño concreto: la normalización
naive/aware quedó en un único punto de `src/domain/sla_calculator.py` reutilizado por una única
función de parseo en `src/application/services.py` (Principio I, Decisión 1 de `research.md`);
el puerto re-firmado (`find_open_duplicates`) no tiene llamador previo que romper (Decisión 2);
las dos excepciones nuevas (`IncidentConflictError`/`IncidentNotFoundError`) mapean 1:1 a
`409`/`404` sin que ningún adaptador reinterprete mensajes (Decisión 3); el reloj del sistema
solo se lee en el borde para los dos campos nuevos, igual que ya hacía H002 (Decisión 4); y los
19 escenarios de aceptación tienen una función `test_bdd_*` planeada 1:1 contra las fixtures ya
existentes (Decisión 8). **Resultado**: PASA sin cambios respecto a la evaluación inicial; ninguna
decisión de Fase 1 introdujo una violación nueva ni una decisión estructural que amerite un ADR
adicional.

## Project Structure

### Documentation (this feature)

```text
specs/003-incident-lifecycle-duplicates-sla/
├── spec.md                              # Ya existe (clarificado)
├── plan.md                              # Este archivo (/speckit.plan)
├── research.md                          # Fase 0 (/speckit.plan)
├── data-model.md                        # Fase 1 (/speckit.plan)
├── quickstart.md                        # Fase 1 (/speckit.plan)
├── contracts/
│   └── incident-lifecycle-sla.md        # Fase 1 (/speckit.plan) — contrato HTTP + CLI
└── tasks.md                             # Fase 2 (/speckit.tasks — fuera de este comando)
```

### Source Code (repository root = `week-1/starter-project/`)

```text
src/
├── domain/
│   ├── models.py                # + Incident.recommended_team: Optional[TeamName] = None
│   │                             # + Incident.duplicate_group_key: Optional[str] = None  (ambos aditivos)
│   ├── triage_rules.py           # sin cambios
│   ├── sla_calculator.py         # `_require_naive` -> `require_naive_datetime` (público, mismo cuerpo/ValueError)
│   └── ruff.toml                  # sin cambios (ninguna capa gana un import nuevo prohibido)
├── application/
│   ├── ports.py                   # find_open_duplicates(component, symptom_category) -> find_open_duplicates(duplicate_group_key)
│   ├── services.py                # + IncidentService.create_incident(...)
│   │                               # + IncidentService.evaluate_incident_sla(...)
│   │                               # + parse_naive_local_datetime(label, raw_value)  (función de módulo, reutilizada por ambos adaptadores)
│   │                               # + dataclass IncidentCreationResult
│   │                               # + excepciones IncidentConflictError, IncidentNotFoundError
│   └── ruff.toml                   # sin cambios
├── adapters/
│   ├── inbound/
│   │   ├── api/
│   │   │   ├── app.py              # + POST /api/v1/incidents; + GET /api/v1/incidents/{incident_id}/sla
│   │   │   │                        # + exception_handler(RequestValidationError) -> {"error": ...} / 422
│   │   │   └── schemas.py          # + CreateIncidentRequestSchema, IncidentCreatedResponseSchema, SLAEvaluationResponseSchema
│   │   ├── cli.py                  # + comando `create`; + comando `sla`
│   │   └── ruff.toml                # sin cambios
│   └── outbound/
│       ├── sqlite_repository.py    # + columnas recommended_team/duplicate_group_key; + idx_incidents_dup_key;
│       │                            # find_open_duplicates re-firmado; save_incident/get_incident actualizados
│       └── factory.py               # sin cambios
├── incident_repository.py          # SIN CAMBIOS — benchmark pedagógico de Semana 1
└── context_audit.py                 # sin cambios

tests/
├── conftest.py                      # sin cambios (fixtures reutilizadas — research.md, Decisión 8)
└── test_spec_003_lifecycle_sla.py   # nuevo: ~19 funciones test_bdd_* (una por escenario de aceptación de spec.md)

pyproject.toml                       # sin cambios (ninguna dependencia nueva)
```

**Structure Decision**: Se conserva el proyecto único con doble adaptador de entrada ya
establecido en H001/H002; H003 no introduce ningún paquete nuevo bajo `src/` — solo extiende
`domain/models.py`, `domain/sla_calculator.py`, `application/ports.py`,
`application/services.py`, `adapters/outbound/sqlite_repository.py`,
`adapters/inbound/api/{app.py,schemas.py}` y `adapters/inbound/cli.py`, más un archivo de
pruebas nuevo bajo `tests/`. No se introduce ninguna carpeta fuera de `src/`, `tests/` y
`specs/003-incident-lifecycle-duplicates-sla/`.

## Complexity Tracking

> Fill ONLY if Constitution Check has violations that must be justified

Sin violaciones — ver tabla de Constitution Check arriba. No aplica.
