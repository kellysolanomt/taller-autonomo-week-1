---

description: "Task list template for feature implementation"
---

# Tasks: Resumen de incidentes activos (H002)

**Input**: Design documents from `specs/002-active-incidents-summary/` (`spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/incidents-summary.md`, `quickstart.md`)

**Prerequisites**: `plan.md` (completo), `spec.md` (3 historias de usuario P1/P2/P3, 8 escenarios de aceptación), `research.md` (6 decisiones), `data-model.md` (entidades y puerto), `contracts/incidents-summary.md` (contrato HTTP + CLI)

**Tests**: Incluidos y obligatorios para esta funcionalidad — Constitución 3.4 exige cobertura BDD automatizada, y la instrucción original del usuario pidió explícitamente `tests/test_spec_002_summary.py` con la verificación de cumplimiento de `IncidentRepositoryPort`. Todas las funciones `test_bdd_*` van en ese único archivo nuevo, siguiendo la convención del skill `bdd-acceptance` (una función por escenario de `spec.md`, almacenamiento aislado por prueba).

**Organization**: Tareas agrupadas por historia de usuario (US1 = Historia 1 HTTP, P1; US2 = Historia 2 CLI, P2; US3 = Historia 3 filtro por componente, P3), precedidas por Setup y Foundational.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Puede ejecutarse en paralelo (archivo distinto, sin dependencias pendientes)
- **[Story]**: Historia de usuario a la que pertenece la tarea (US1, US2, US3)
- Todas las rutas de archivo son relativas a `week-1/starter-project/`

## Path Conventions

Proyecto único (ver `plan.md` → Structure Decision): `src/`, `tests/` en la raíz de `week-1/starter-project/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Configuración de análisis estático y andamiaje del nuevo paquete de salida, sin lógica de negocio.

- [X] T001 [P] Añadir `[tool.ruff.lint]` con `select = ["E4", "E7", "E9", "F", "TID"]` en `pyproject.toml` (plan.md → Technical Context; skill `hexagonal-architecture` §3).
- [X] T002 [P] Crear `src/domain/ruff.toml` con `extend = "../../pyproject.toml"` y `banned-api`/`ban-relative-imports` para prohibir `fastapi`, `typer`, `pydantic`, `sqlite3`, `src.adapters`, `src.application` (skill `hexagonal-architecture` §3, capa `src/domain/`).
- [X] T003 [P] Crear `src/application/ruff.toml` con `extend = "../../pyproject.toml"` y `banned-api`/`ban-relative-imports` para prohibir `fastapi`, `typer`, `pydantic`, `sqlite3`, `src.adapters.*` concretos (skill `hexagonal-architecture` §3, capa `src/application/`).
- [X] T004 [P] Crear `src/adapters/inbound/ruff.toml` con `extend = "../../../pyproject.toml"` y `banned-api`/`ban-relative-imports` para prohibir `sqlite3`, `src.incident_repository`, `src.adapters.outbound.sqlite_repository` (import directo de repositorio concreto) (skill `hexagonal-architecture` §3, capa `src/adapters/inbound/`).
- [X] T005 [P] Crear el paquete `src/adapters/outbound/__init__.py` (vacío) como nueva carpeta de adaptadores de salida (plan.md → Project Structure).

**Checkpoint**: Fronteras de Ruff y el paquete `outbound/` existen; `uv run ruff check src/` corre sin error de configuración (aún no hay código que validar en las capas nuevas).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Puerto de salida, adaptador SQLite, fábrica por `DATABASE_URL` y el caso de uso compartido `get_active_incidents_summary`. Ninguna historia de usuario (US1/US2/US3) puede implementarse sin esto, porque las tres consultan el mismo método de `IncidentService` sobre el mismo puerto.

**⚠️ CRITICAL**: Ninguna tarea de US1/US2/US3 puede empezar hasta que esta fase esté completa.

- [X] T006 [P] Añadir el campo opcional `symptom_category: Optional[SymptomCategory] = None` a la entidad `Incident` en `src/domain/models.py` (data-model.md → Entidades de dominio, `Incident.symptom_category`: aditivo, preparación de H003, sin romper construcciones existentes).
- [X] T007 [P] Crear `src/application/ports.py` con `IncidentRepositoryPort` (`typing.Protocol`, `@runtime_checkable`) declarando `save_incident(incident: Incident) -> None`, `get_incident(incident_id: str) -> Optional[Incident]`, `find_open_duplicates(component: str, symptom_category: str) -> list[Incident]`, `list_active_incidents(component_filter: Optional[str] = None) -> list[Incident]` y `check_health() -> bool` (data-model.md → `IncidentRepositoryPort`, tabla de métodos completa).
- [X] T008 Implementar `SQLiteIncidentRepository` en `src/adapters/outbound/sqlite_repository.py`: esquema `incidents` con la columna nueva nullable `symptom_category TEXT` (data-model.md → esquema SQLite) y el índice compuesto `(component, status)` ya validado por ADR-001; implementar los 5 métodos del puerto, con `list_active_incidents(component_filter=None)` como una única consulta parametrizada con `?` que omite el predicado `component = ?` cuando `component_filter` es `None` (data-model.md → `IncidentRepositoryPort.list_active_incidents`; Constitución 3.3). Depende de T006, T007.
- [X] T009 Implementar `get_incident_repository()` en `src/adapters/outbound/factory.py`, leyendo `DATABASE_URL` (`os.environ`, por defecto `"sqlite:///:memory:"`), soportando solo el esquema `sqlite:///` y lanzando `ValueError` para cualquier otro (research.md → Decisión 5). Depende de T008.
- [X] T010 Añadir las dataclasses `ActiveIncidentSummaryItem` y `ActiveIncidentsSummary` en `src/application/services.py` con los campos citados exactamente como en data-model.md → Tipos de aplicación: `ActiveIncidentSummaryItem.incident_id`, `ActiveIncidentSummaryItem.title`, `ActiveIncidentSummaryItem.component`, `ActiveIncidentSummaryItem.severity`, `ActiveIncidentSummaryItem.status`, `ActiveIncidentSummaryItem.elapsed_minutes`, `ActiveIncidentSummaryItem.requires_escalation`, `ActiveIncidentsSummary.total_active`, `ActiveIncidentsSummary.breached_count`, `ActiveIncidentsSummary.incidents`.
- [X] T011 Refactorizar `IncidentService` en `src/application/services.py`: el constructor pasa a exigir `repository: IncidentRepositoryPort`; añadir `get_active_incidents_summary(component_filter: Optional[str], reference_time: datetime) -> ActiveIncidentsSummary`, que llama a `repository.list_active_incidents(component_filter)` y evalúa cada incidente con `evaluate_sla_status` de `src/domain/sla_calculator.py` (nunca dentro del repositorio) para construir `breached_count` y el detalle (research.md → Decisión 2; data-model.md → algoritmo del caso de uso). `reference_time` es siempre un argumento obligatorio; el método nunca lee el reloj del sistema (research.md → Decisión 3). Depende de T007, T008, T010.
- [X] T012 [P] Actualizar `create_app()` en `src/adapters/inbound/api/app.py` para aceptar `service: Optional[IncidentService] = None`, construyendo por defecto `IncidentService(get_incident_repository())`; la ruta `/api/v1/incidents/triage` existente sigue funcionando sin cambios de comportamiento. Depende de T009, T011.
- [X] T013 [P] Refactorizar `src/adapters/inbound/cli.py` a una función `create_cli_app(service: IncidentService) -> typer.Typer` que registre el comando `triage` existente; mantener `app = create_cli_app(IncidentService(get_incident_repository()))` como export de módulo para que `from src.adapters.inbound.cli import app as cli_app` siga funcionando en `tests/conftest.py`. Depende de T009, T011.
- [X] T014 Añadir a `tests/conftest.py` las fixtures `incident_repository` (nuevo `SQLiteIncidentRepository(":memory:")` por test), `incident_service` (`IncidentService(incident_repository)`), `summary_api_client` (`TestClient(create_app(service=incident_service))`) y `summary_cli_app` (`create_cli_app(incident_service)`), de modo que un mismo test comparta un único repositorio entre HTTP y CLI (research.md → Decisión 6; skill `bdd-acceptance` §"Almacenamiento aislado"). Depende de T012, T013.
- [X] T015 Ejecutar `uv run pytest -v` y `uv run python -m src.domain.sla_calculator` para confirmar que la suite de H001 (`tests/test_spec_001_triage.py`) y los casos borde de SLA siguen pasando sin cambios tras el refactor de `IncidentService` (plan.md → Constitution Check, filas 1.4/1.5). Depende de T014.

**Checkpoint**: El puerto, el adaptador SQLite, la fábrica y `get_active_incidents_summary` existen y no rompen H001. Las historias de usuario pueden empezar.

---

## Phase 3: User Story 1 - Consultar el resumen de incidentes activos por HTTP (Priority: P1) 🎯 MVP

**Goal**: Exponer `GET /api/v1/incidents/summary` devolviendo total activo, incumplimientos de SLA y detalle, sin exigir ningún filtro.

**Independent Test**: Enviar la consulta HTTP sin filtro contra un conjunto conocido de incidentes activos y resueltos y verificar que la respuesta solo cuenta/detalla los activos, con los incumplimientos correctos (spec.md → Historia 1, Escenarios 1-3).

### Tests for User Story 1 ⚠️

> Escribir estas pruebas primero y confirmar que fallan antes de implementar T019-T020.

- [X] T016 [US1] `test_bdd_resumen_http_incluye_incumplimientos_y_excluye_resueltos` en `tests/test_spec_002_summary.py`, usando `summary_api_client`: siembra incidentes activos (con y sin incumplimiento) y resueltos vía `incident_repository.save_incident`, consulta `GET /api/v1/incidents/summary?reference_time=<ISO8601 fijo>` sin filtro de componente (reference_time fijo y explícito para determinismo, Constitución Principio V), y verifica `total_active`, `breached_count` y que ningún incidente `RESOLVED` aparece en `incidents` (spec.md → Historia 1, Escenario de Aceptación 1; contracts/incidents-summary.md §1.2). Esta llamada con `reference_time` explícito también cubre la mitad "override" de FR-013.
- [X] T017 [US1] `test_bdd_resumen_http_vacio_sin_incidentes_activos` en `tests/test_spec_002_summary.py`, usando `summary_api_client`: sin incidentes sembrados, consulta `GET /api/v1/incidents/summary` **sin** indicar `reference_time` (ejercita la rama por defecto "instante de la consulta" de FR-013, vía `datetime.now()` en el adaptador) y verifica `200 OK` con `total_active: 0`, `breached_count: 0`, `incidents: []` (spec.md → Historia 1, Escenario 2; contracts/incidents-summary.md §1.2).
- [X] T018 [US1] `test_bdd_incidente_vencido_se_cuenta_como_incumplimiento_http` en `tests/test_spec_002_summary.py`, usando `summary_api_client`: siembra un incidente activo cuyo `elapsed_minutes` supera el máximo de su SLA y consulta con un `reference_time` fijo y explícito (determinismo, Constitución Principio V) que garantiza el incumplimiento; verifica que se cuenta en `breached_count` y que su ítem de detalle refleja `requires_escalation: true` (spec.md → Historia 1, Escenario 3; data-model.md → nota sobre `is_breached ⟹ requires_escalation` para incidentes activos).

### Implementation for User Story 1

- [X] T019 [US1] Añadir `ActiveIncidentItemSchema` y `ActiveIncidentsSummaryResponseSchema` a `src/adapters/inbound/api/schemas.py`, con los mismos campos de `ActiveIncidentSummaryItem`/`ActiveIncidentsSummary` (contracts/incidents-summary.md §1.2; data-model.md → Tipos de aplicación). *(Adelantada durante T012: `create_app()` necesitaba el esquema para compilar.)*
- [X] T020 [US1] Añadir la ruta `GET /api/v1/incidents/summary` en `src/adapters/inbound/api/app.py`: lee los query params opcionales `component` y `reference_time` (ISO 8601 naive); si `reference_time` no se indica, usar `datetime.now()` **solo en este punto del adaptador** (research.md → Decisión 3) y pasarlo como argumento concreto a `service.get_active_incidents_summary(...)`; mapear el resultado a `ActiveIncidentsSummaryResponseSchema` (contracts/incidents-summary.md §1.1-§1.3). Depende de T010, T011, T019. *(Adelantada durante T012; incluye manejo de `ValueError` → `422` para `reference_time` con zona horaria, contracts/incidents-summary.md §1.3.)*

**Checkpoint**: La Historia 1 es funcional y comprobable de forma independiente (MVP).

---

## Phase 4: User Story 2 - Obtener el mismo resumen desde la línea de comandos (Priority: P2)

**Goal**: Paridad de resultado de negocio entre HTTP y CLI para la misma consulta (FR-002, SC-002).

**Independent Test**: Ejecutar el comando `summary` con el mismo conjunto de incidentes usado en la Historia 1 y verificar que el total, los incumplimientos y el detalle son idénticos a los de la consulta HTTP (spec.md → Historia 2, Escenarios 1-2).

### Tests for User Story 2 ⚠️

- [X] T021 [US2] `test_bdd_paridad_resumen_http_cli_mismo_conjunto` en `tests/test_spec_002_summary.py`, usando `summary_api_client` y `summary_cli_app` sobre el **mismo** `incident_service`/`incident_repository` del test: siembra el mismo conjunto de incidentes activos, consulta por HTTP y por CLI sin filtro, y verifica que `total_active`, `breached_count` y el contenido de `incidents` coinciden en ambas respuestas (spec.md → Historia 2, Escenario de Aceptación 1; contracts/incidents-summary.md §3).
- [X] T022 [US2] `test_bdd_resumen_cli_vacio_sin_incidentes_activos` en `tests/test_spec_002_summary.py`, usando `summary_cli_app` vía `cli_runner.invoke`: sin incidentes activos, ejecuta el comando `summary` y verifica código de salida `0` y salida JSON con `total_active: 0` (spec.md → Historia 2, Escenario 2; contracts/incidents-summary.md §2.1).

### Implementation for User Story 2

- [X] T023 [US2] Añadir el comando `summary` dentro de `create_cli_app` en `src/adapters/inbound/cli.py`, con opciones `--component` y `--reference-time` (mismo tratamiento de `reference_time` por defecto que en T020: `datetime.now()` solo si no se indica), imprimiendo en `stdout` el mismo cuerpo JSON (`total_active`, `breached_count`, `incidents`) que la ruta HTTP y terminando con código de salida `0` (contracts/incidents-summary.md §2). Depende de T013, T020. *(Adelantada durante T013.)*

**Checkpoint**: Las Historias 1 y 2 funcionan juntas e independientemente.

---

## Phase 5: User Story 3 - Filtrar el resumen por componente (Priority: P3)

**Goal**: Acotar el resumen a un componente específico, reutilizando la ruta HTTP y el comando CLI ya construidos (el parámetro `component_filter` ya existe en `get_active_incidents_summary` desde la Fase 2 — ver T011).

**Independent Test**: Consultar el resumen con el filtro de un componente conocido (por HTTP) y verificar que el total, los incumplimientos y el detalle solo incluyen incidentes activos de ese componente (spec.md → Historia 3, Escenarios 1-3).

**Nota**: Esta historia no requiere código de producción nuevo — el filtrado por componente ya quedó implementado en el puerto (T008), en el caso de uso (T011) y expuesto por ambos adaptadores (T020, T023). Las tareas de esta fase son exclusivamente de verificación, consistente con la nota de `spec.md`: "aporta valor por sí mismo pero no es indispensable para que el resumen exista". La paridad CLI del filtro ya quedó cubierta por T021 (Historia 2); estas pruebas usan `summary_api_client`.

### Tests for User Story 3 ⚠️

- [X] T024 [US3] `test_bdd_filtro_por_componente_limita_resumen` en `tests/test_spec_002_summary.py`, usando `summary_api_client`: siembra incidentes activos de varios componentes, consulta `GET /api/v1/incidents/summary?component=<uno>` y verifica que el total, los incumplimientos y el detalle solo incluyen ese componente (spec.md → Historia 3, Escenario de Aceptación 1).
- [X] T025 [US3] `test_bdd_filtro_componente_sin_incidentes_activos` en `tests/test_spec_002_summary.py`, usando `summary_api_client`: consulta con `component` que no tiene incidentes activos (pero sí resueltos o inexistente) y verifica `200 OK` con `total_active: 0`, `incidents: []` (spec.md → Historia 3, Escenario 2; FR-008).
- [X] T026 [US3] `test_bdd_sin_filtro_incluye_todos_los_componentes` en `tests/test_spec_002_summary.py`, usando `summary_api_client`: siembra incidentes activos de varios componentes, consulta sin `component` y verifica que todos aparecen en el detalle (spec.md → Historia 3, Escenario 3).

**Checkpoint**: Las tres historias de usuario son funcionales y comprobables de forma independiente.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Verificación de cumplimiento del puerto, fronteras hexagonales y limpieza documental.

- [X] T027 En `tests/test_spec_002_summary.py`, añadir una prueba de cumplimiento estructural: instanciar `SQLiteIncidentRepository(":memory:")` y verificar `isinstance(repo, IncidentRepositoryPort)` (requiere `@runtime_checkable` del puerto, T007), confirmando que implementa los 5 métodos de `IncidentRepositoryPort` (requisito explícito del usuario en la instrucción original de `/speckit.plan`). Depende de T008; se añade después de T016-T026 en el mismo archivo.
- [X] T028 Ejecutar `uv run ruff check src/` y corregir cualquier violación `TID251`/`TID252` detectada en `src/domain/`, `src/application/` o `src/adapters/inbound/` (plan.md → Technical Context; skill `hexagonal-architecture`, checklist final). Depende de T001-T004, T006-T013.
- [X] T029 [P] Actualizar la sección "Scope and layout" de `AGENTS.md` para documentar `src/adapters/outbound/` y `src/application/ports.py`, reemplazando la nota ahora obsoleta de que `src/incident_repository.py` "sigue en `src/` tal como estaba" (plan.md → Constitution Check, nota operativa).
- [X] T030 Ejecutar `quickstart.md` de punta a punta (pasos 1-4: `pytest`, `ruff check`, `curl`, CLI) y confirmar manualmente la paridad HTTP/CLI con un `DATABASE_URL` de archivo compartido (quickstart.md §4). Depende de T015, T020, T023, T027, T028.
- [X] T031 `test_bdd_resumen_es_solo_lectura_sin_efectos_secundarios` en `tests/test_spec_002_summary.py`, usando `summary_api_client` y `summary_cli_app` sobre la misma fixture `incident_repository`: siembra incidentes activos, consulta el resumen dos veces (una por HTTP y una por CLI) y verifica que `incident_repository.list_active_incidents()` devuelve exactamente el mismo conjunto antes y después de ambas consultas, y que ambas respuestas son idénticas entre sí (spec.md → FR-011 "no debe crear, modificar, cerrar ni reclasificar ningún incidente"; FR-012 "una consulta repetida... produce el mismo resultado; la consulta en sí no deja efectos ni estado adicional"). Depende de T014, T020, T023.
- [X] T032 Prueba de rendimiento en `tests/test_spec_002_summary.py`: sembrar ~100 incidentes activos vía `incident_repository.save_incident` (mezcla de componentes y severidades, análoga a `seed_synthetic_incidents` de `src/incident_repository.py` pero a escala de guardia, no de benchmark de 10,000) y verificar que `summary_api_client.get("/api/v1/incidents/summary")` responde en menos de 2 segundos, sin paginar (spec.md → SC-006). Depende de T014, T020.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Sin dependencias — puede iniciar de inmediato.
- **Foundational (Phase 2)**: Depende de que Setup exista (los `ruff.toml` validan las capas que aquí se crean); **bloquea** US1, US2 y US3.
- **User Stories (Phase 3-5)**: Todas dependen de Foundational. US1 es el MVP; US2 reutiliza la misma lógica de servicio que US1 (T020) para construir el comando CLI; US3 no añade código nuevo, solo pruebas sobre lo que T008/T011/T020/T023 ya construyeron.
- **Polish (Phase 6)**: Depende de que las historias que se quieran entregar estén completas.

### User Story Dependencies

- **US1 (P1)**: Puede iniciar tras Foundational. Sin dependencia de otras historias.
- **US2 (P2)**: Puede iniciar tras Foundational; su implementación (T023) reutiliza el patrón de T020 pero no requiere que T020 esté mergeado primero si se coordinan las firmas de antemano — en la práctica, implementar US1 antes simplifica US2.
- **US3 (P3)**: Depende funcionalmente de que T008/T011 (Foundational) y T020/T023 (US1/US2) ya existan, porque no añade código propio, solo pruebas sobre esas rutas.

### Within Each User Story

- Pruebas `test_bdd_*` antes de la implementación correspondiente (T016-T018 antes de T019-T020; T021-T022 antes de T023).
- Todas las funciones de prueba de una historia viven en el mismo archivo nuevo (`tests/test_spec_002_summary.py`): no se marcan `[P]` entre sí para evitar conflictos de edición concurrente sobre el mismo archivo.

### Parallel Opportunities

- Fase 1: T001-T005 (archivos distintos).
- Fase 2: T006 y T007 en paralelo (archivos distintos, sin dependencia mutua); T012 y T013 en paralelo una vez completados T009 y T011 (archivos distintos: `api/app.py` vs `cli.py`).
- Entre historias: una vez cerrada Foundational, un equipo podría trabajar T019-T020 (US1) y, en paralelo, preparar T023 (US2) si ya acordó la firma del comando `summary`; en la práctica, al depender T023 de T020, se recomienda el orden secuencial P1 → P2 → P3 indicado arriba.
- T029 (actualizar `AGENTS.md`) es independiente de T027/T028/T030 y puede hacerse en paralelo con ellas.

---

## Parallel Example: Foundational (Phase 2)

```bash
# T006 y T007 pueden iniciar juntos (archivos distintos, sin dependencia entre ellos):
Task: "Añadir symptom_category opcional a Incident en src/domain/models.py"
Task: "Definir IncidentRepositoryPort en src/application/ports.py"

# Tras T009 y T011, T012 y T013 pueden iniciar juntos (archivos distintos):
Task: "Actualizar create_app() en src/adapters/inbound/api/app.py"
Task: "Refactorizar cli.py a create_cli_app() en src/adapters/inbound/cli.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Completar Fase 1: Setup.
2. Completar Fase 2: Foundational (bloqueante para todo lo demás).
3. Completar Fase 3: User Story 1 (`GET /api/v1/incidents/summary`).
4. **Detener y validar**: ejecutar `uv run pytest -v tests/test_spec_002_summary.py` y los pasos 1-3 de `quickstart.md`.
5. Esto ya satisface SC-001 y SC-004 para la interfaz HTTP.

### Incremental Delivery

1. Setup + Foundational → base lista.
2. + User Story 1 → probar de forma independiente → demo HTTP (MVP).
3. + User Story 2 → probar paridad HTTP/CLI de forma independiente → demo CLI (SC-002).
4. + User Story 3 → probar filtro por componente de forma independiente → demo filtrado (SC-003).
5. Cada historia agrega valor sin romper la anterior; las 8 funciones `test_bdd_*` de las historias de usuario, más la prueba de solo-lectura (T031, FR-011/FR-012), la prueba de rendimiento (T032, SC-006) y la prueba de cumplimiento del puerto (T027), quedan como regresión permanente.

---

## Notes

- `[P]` = archivos distintos sin dependencias pendientes entre sí.
- `[Story]` identifica a qué historia de usuario pertenece cada tarea de las Fases 3-5; Setup, Foundational y Polish no llevan `[Story]`.
- Cada campo con restricción de `data-model.md` (`Incident.symptom_category`, los campos de `ActiveIncidentSummaryItem`/`ActiveIncidentsSummary`, y los 5 métodos de `IncidentRepositoryPort`) queda citado explícitamente en al menos una tarea de implementación (T006, T007, T008, T010, T011).
- Ejecutar `uv run pytest -v` tras cada tarea o grupo lógico de tareas (Constitución, Principio V); `uv run ruff check src/` tras completar Foundational y de nuevo al cierre (T028).
- Evitar: pruebas vagas sin escenario citado de `spec.md`, ediciones concurrentes al mismo archivo de test, y dependencias cruzadas entre historias que rompan su independencia.
