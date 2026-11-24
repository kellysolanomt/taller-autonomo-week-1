---

description: "Task list template for feature implementation"
---

# Tasks: Persistencia relacional dedicada y runtime en contenedores (H004)

**Input**: Design documents from `specs/004-postgres-container-runtime/` (`spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/health-check.md`, `quickstart.md`)

**Prerequisites**: `plan.md` (completo, Constitution Check PASA con 1 ajuste de frontera pendiente), `spec.md` (3 historias de usuario P1/P2/P3, 15 escenarios de aceptación: 5+5+5), `research.md` (7 decisiones), `data-model.md` (puerto, servicio, esquemas por motor, fábrica, contrato de salud), `contracts/health-check.md` (contrato HTTP + CLI + healthchecks de Compose)

**Tests**: Incluidos y obligatorios para esta funcionalidad — Constitución, Principio V, exige cobertura BDD automatizada para toda funcionalidad observable desde un adaptador de entrada, y la instrucción original del usuario pidió explícitamente `tests/test_spec_004_runtime_health.py`. Todas las funciones `test_bdd_*`/`test_*` van en ese único archivo nuevo, siguiendo la convención del skill `bdd-acceptance`.

**Organization**: Tareas agrupadas por historia de usuario (US1 = Historia 1, chequeo de salud HTTP+CLI, P1; US2 = Historia 2, selección transparente de motor, P2; US3 = Historia 3, orquestación en contenedores, P3), precedidas por Setup y Foundational.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Puede ejecutarse en paralelo (archivo distinto, sin dependencias pendientes)
- **[Story]**: Historia de usuario a la que pertenece la tarea (US1, US2, US3)
- Todas las rutas de archivo son relativas a `week-1/starter-project/`

## Path Conventions

Proyecto único (ver `plan.md` → Structure Decision): `src/`, `tests/` y los artefactos de contenedores (`Dockerfile`, `.dockerignore`, `docker-compose.yml`) en la raíz de `week-1/starter-project/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Inicialización de proyecto para esta funcionalidad.

**Sin tareas nuevas**: `psycopg[binary]>=3.3.9` ya está declarado en `pyproject.toml` y resuelto en
`uv.lock` (añadido antes de este plan vía `uv add "psycopg[binary]"`); `research.md` no identifica
ninguna otra dependencia nueva. Continúa directamente en la Fase 2.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Infraestructura común bloqueante para las tres historias.

**Sin tareas nuevas**: a diferencia de H003, esta funcionalidad no requiere cambios de dominio ni
re-firmas de puerto compartidas por las tres historias — `IncidentRepositoryPort.check_health()`
ya existe desde H002 (sin implementación real hasta ahora) y no cambia de firma. Cada historia es
autocontenida: US1 solo necesita el método de servicio y las interfaces de entrada; US2 solo
necesita el adaptador PostgreSQL y la fábrica; US3 solo necesita los tres artefactos de
contenedores. Continúa directamente en la Fase 3.

---

## Phase 3: User Story 1 - Confirmar si el servicio está operativo contra su base de datos, por HTTP y CLI (Priority: P1) 🎯 MVP

**Goal**: Exponer `GET /health` y el comando CLI `health`, ambos delegando en
`IncidentService.check_health()`, que a su vez delega en `IncidentRepositoryPort.check_health()`
del repositorio ya inyectado (SQLite por defecto).

**Independent Test**: Apuntar el servicio a un repositorio SQLite en memoria (saludable) y
verificar `200 OK`/código de salida `0`; repetir con un doble de prueba cuyo `check_health()`
devuelve `False` y verificar `503`/código de salida `1` (spec.md → Historia 1, Escenarios 1-4).

### Tests for User Story 1 ⚠️

> Escribir estas pruebas primero y confirmar que fallan antes de implementar T006-T009.

- [X] T001 [P] [US1] `test_bdd_health_http_200_conectado` en `tests/test_spec_004_runtime_health.py` (archivo nuevo), usando `TestClient(create_app(service=IncidentService(SQLiteIncidentRepository(":memory:"))))`: `GET /health`; verificar `200 OK` con cuerpo exacto `{"status": "ok", "database": "connected"}` (spec.md → Historia 1, Escenario de Aceptación 1; contracts/health-check.md §1.2).
- [X] T002 [P] [US1] `test_bdd_health_http_503_doble_de_prueba` en `tests/test_spec_004_runtime_health.py`: definir en el propio archivo una clase doble de prueba `_UnhealthyRepository` que implementa los 5 métodos de `IncidentRepositoryPort` (`check_health` devuelve `False`; los demás no se ejercitan en esta prueba) y usarla para construir `TestClient(create_app(service=IncidentService(_UnhealthyRepository())))`; `GET /health`; verificar `503 Service Unavailable` con cuerpo exacto `{"status": "error", "database": "unavailable"}` (spec.md → Historia 1, Escenario de Aceptación 3; contracts/health-check.md §1.3).
- [X] T003 [P] [US1] `test_bdd_health_cli_exit0_conectado` en `tests/test_spec_004_runtime_health.py`, usando `CliRunner().invoke(create_cli_app(IncidentService(SQLiteIncidentRepository(":memory:"))), ["health"])`: verificar código de salida `0` y stdout con el mismo cuerpo JSON que T001 (spec.md → Historia 1, Escenario de Aceptación 2; contracts/health-check.md §2.2).
- [X] T004 [P] [US1] `test_bdd_health_cli_exit1_no_disponible` en `tests/test_spec_004_runtime_health.py`, reutilizando `_UnhealthyRepository` de T002 vía `create_cli_app(IncidentService(_UnhealthyRepository()))`: invocar `health`; verificar código de salida `1` y stdout con el mismo cuerpo JSON que T002 (spec.md → Historia 1, Escenario de Aceptación 4; contracts/health-check.md §2.3).
- [X] T005 [P] [US1] `test_bdd_health_http_idempotente_repetible` en `tests/test_spec_004_runtime_health.py`, reutilizando el cliente de T001: invocar `GET /health` dos veces seguidas sin cambios en el repositorio; verificar que ambas respuestas son idénticas (spec.md → Historia 1, Escenario de Aceptación 5).
- [X] T030 [P] [US1] `test_bdd_health_http_refleja_cambio_de_estado_sin_cache` en `tests/test_spec_004_runtime_health.py`: usando un repositorio doble con estado mutable (`_FlakyRepository`, cuyo `check_health()` devuelve `True` en la primera llamada y `False` en la segunda, p. ej. consumiendo una lista `[True, False]`) compartido por una única instancia de `IncidentService`/`TestClient`; invocar `GET /health` dos veces seguidas sobre ese mismo cliente; verificar que la primera respuesta es `200 OK` (`connected`) y la segunda es `503 Service Unavailable` (`unavailable`), confirmando que el resultado nunca se cachea entre invocaciones (spec.md → RNF-003; Casos Límite, "qué ocurre si la base de datos deja de estar disponible después de que el servicio ya inició correctamente"; SC-004).

### Implementation for User Story 1

- [X] T006 [P] [US1] En `src/application/services.py`, añadir `IncidentService.check_health(self) -> bool` que delega exactamente en `self._repository.check_health()`, sin transformar el resultado ni añadir reglas de negocio (data-model.md → `IncidentService.check_health()`).
- [X] T007 [P] [US1] En `src/adapters/inbound/api/schemas.py`, añadir `HealthResponseSchema` (`status: str`, `database: str`) (data-model.md → contrato de `GET /health`, campos `status`/`database`; contracts/health-check.md §1.2-1.3).
- [X] T008 [US1] En `src/adapters/inbound/api/app.py`, añadir la ruta `GET /health`: si `service.check_health()` es `True`, responder `200 OK` con `HealthResponseSchema(status="ok", database="connected")`; si es `False`, responder `JSONResponse(status_code=503, content={"status": "error", "database": "unavailable"})` (contracts/health-check.md §1.2-1.3). Depende de T006, T007.
- [X] T009 [US1] En `src/adapters/inbound/cli.py`, añadir el comando `health` dentro de `create_cli_app`: invoca `service.check_health()`; imprime en stdout `{"status": "ok", "database": "connected"}` y termina con `typer.Exit(code=0)` (o retorno normal) si `True`; imprime `{"status": "error", "database": "unavailable"}` y `raise typer.Exit(code=1)` si `False` (contracts/health-check.md §2.2-2.3). Depende de T006.

**Checkpoint**: La Historia 1 es funcional y comprobable de forma independiente (MVP), sin tocar
`factory.py` ni ningún adaptador PostgreSQL.

---

## Phase 4: User Story 2 - Elegir el motor de persistencia por entorno sin cambiar código (Priority: P2)

**Goal**: Añadir `PostgresIncidentRepository` (mismo `IncidentRepositoryPort` que SQLite, SQL
nativo vía `psycopg`) y `factory.create_repository(database_url)`, que selecciona el adaptador por
el esquema de la URL.

**Independent Test**: Verificar, sin necesidad de un servidor PostgreSQL en ejecución, que
`create_repository("sqlite:///:memory:")` devuelve un `SQLiteIncidentRepository` funcional, que
`PostgresIncidentRepository` cumple estructuralmente `IncidentRepositoryPort`, y que un esquema no
soportado se rechaza explícitamente (spec.md → Historia 2, Escenarios 1-5; research.md →
Decisión 4).

### Tests for User Story 2 ⚠️

- [X] T010 [P] [US2] `test_sqlite_repository_cumple_incident_repository_port` en `tests/test_spec_004_runtime_health.py`: `isinstance(SQLiteIncidentRepository(":memory:"), IncidentRepositoryPort)` es `True` (research.md → Decisión 4).
- [X] T011 [P] [US2] `test_postgres_repository_cumple_incident_repository_port_estructural` en `tests/test_spec_004_runtime_health.py`: `issubclass(PostgresIncidentRepository, IncidentRepositoryPort)` es `True`, **sin instanciar la clase ni abrir ninguna conexión** (research.md → Decisión 4; FR-006).
- [X] T012 [P] [US2] `test_create_repository_esquema_sqlite` en `tests/test_spec_004_runtime_health.py`: `create_repository("sqlite:///:memory:")` devuelve una instancia de `SQLiteIncidentRepository` (spec.md → Historia 2, Escenario de Aceptación 2; FR-005).
- [X] T013 [P] [US2] `test_get_incident_repository_sin_database_url_usa_sqlite_memoria` en `tests/test_spec_004_runtime_health.py`, con `monkeypatch.delenv("DATABASE_URL", raising=False)`: `get_incident_repository()` devuelve una instancia de `SQLiteIncidentRepository` respaldada por `:memory:` (spec.md → Historia 2, Escenario de Aceptación 3; FR-005).
- [X] T014 [P] [US2] `test_create_repository_esquema_postgresql_selecciona_adaptador` en `tests/test_spec_004_runtime_health.py`: con `monkeypatch.setattr` sobre el símbolo `PostgresIncidentRepository` dentro del módulo `src.adapters.outbound.factory` por una clase doble mínima que cumple el puerto sin red; `create_repository("postgresql://user:pass@host:5432/db")` devuelve una instancia de esa clase doble, confirmando que la rama PostgreSQL de la fábrica se selecciona (spec.md → Historia 2, Escenario de Aceptación 1; research.md → Decisiones 4 y 5).
- [X] T015 [P] [US2] `test_create_repository_esquema_no_soportado_lanza_valueerror` en `tests/test_spec_004_runtime_health.py`: `create_repository("mysql://host/db")` lanza `ValueError` mencionando el esquema `"mysql://"` (spec.md → Historia 2, Escenario de Aceptación 5; FR-007).

### Implementation for User Story 2

- [X] T016 [US2] Crear `src/adapters/outbound/postgres_repository.py` con `class PostgresIncidentRepository`: `__init__(self, dsn: str)` abre `psycopg.connect(dsn, row_factory=psycopg.rows.dict_row, autocommit=True)` y crea el esquema (`sla_policies`, `incidents` con `created_at`/`resolved_at` `TEXT`, e índice `idx_incidents_component_status` sobre `(component, status)`) (data-model.md → "Esquema de datos por motor → PostgreSQL"; research.md → Decisiones 1 y 3).
- [X] T017 [US2] En `postgres_repository.py`: implementar `save_incident` (`INSERT INTO incidents (...) VALUES (%s, ...) ON CONFLICT (incident_id) DO UPDATE SET ...`), `get_incident`, `find_open_duplicates`, `list_active_incidents` (todos parametrizados con `%s`) y `check_health` (`SELECT 1`, capturando `psycopg.Error` → `False`) (data-model.md → tabla de sentencias SQL por método; research.md → Decisión 2). Depende de T016.
- [X] T018 [US2] En `src/adapters/outbound/factory.py`: añadir `create_repository(database_url: str) -> IncidentRepositoryPort` que selecciona por esquema (`postgresql://` → `PostgresIncidentRepository(dsn=database_url)`; `sqlite:///` → `SQLiteIncidentRepository(db_path=...)`; cualquier otro esquema → `ValueError` explícito citando el esquema recibido); refactorizar `get_incident_repository()` para que delegue en `create_repository(os.environ.get("DATABASE_URL", _DEFAULT_DATABASE_URL))`, sin cambiar su firma actual (data-model.md → `create_repository`/`get_incident_repository`; research.md → Decisión 5; FR-005, FR-007). Depende de T016.
- [X] T019 [P] [US2] Actualizar `src/application/ruff.toml` y `src/adapters/inbound/ruff.toml`: añadir entradas `banned-api` para `"psycopg"` y `"src.adapters.outbound.postgres_repository"`, con el mismo formato de mensaje que las entradas existentes para `sqlite3`/`sqlite_repository` (plan.md → Constitution Check, fila II; Constitución, Principio IV).

**Checkpoint**: La Historia 2 es funcional y comprobable de forma independiente, sin Docker ni un
servidor PostgreSQL en ejecución.

---

## Phase 5: User Story 3 - Levantar el servicio de forma reproducible en contenedores (Priority: P3)

**Goal**: Empaquetar `api` en una imagen Docker reproducible y orquestar `api` + `db`
(PostgreSQL) con Docker Compose, reutilizando `GET /health` (US1) y `create_repository` (US2).

**Independent Test**: Verificar estáticamente que `Dockerfile`, `.dockerignore` y
`docker-compose.yml` declaran la topología esperada (sin requerir que Docker esté instalado para
correr `pytest`); la validación dinámica real con Docker vive en `quickstart.md` §4 (spec.md →
Historia 3, Escenarios 1-5).

### Tests for User Story 3 ⚠️

- [X] T020 [P] [US3] `test_dockerfile_usa_python312_slim_y_uv` en `tests/test_spec_004_runtime_health.py`: leer `Dockerfile` como texto y verificar que contiene `FROM python:3.12-slim` y al menos una invocación de `uv` (p. ej. `uv sync` o `uv run`) (spec.md → Historia 3, Escenario de Aceptación 5; research.md → Decisión 6).
- [X] T021 [P] [US3] `test_dockerignore_excluye_entornos_virtuales_y_artefactos_de_prueba` en `tests/test_spec_004_runtime_health.py`: leer `.dockerignore` como texto y verificar que incluye entradas para `.venv`, `__pycache__`, `.git` y `tests` (RNF-004).
- [X] T022 [P] [US3] `test_docker_compose_declara_api_y_db_con_healthchecks_y_depends_on` en `tests/test_spec_004_runtime_health.py`: leer `docker-compose.yml` como texto y verificar, mediante búsqueda de subcadenas (sin parseo YAML, para no añadir una dependencia de prueba nueva), que declara los servicios `api` y `db`; que `db` usa `postgres:16-alpine`, un `healthcheck` basado en `pg_isready` y un volumen con nombre; y que `api` declara `depends_on` con `condition: service_healthy` sobre `db`, una variable `DATABASE_URL` que apunta a `db`, y su propio `healthcheck` sobre `/health` (spec.md → Historia 3, Escenarios de Aceptación 1, 2 y 4; contracts/health-check.md §3; RNF-006).

### Implementation for User Story 3

- [X] T023 [P] [US3] Crear `Dockerfile` en la raíz de `week-1/starter-project/`: `FROM python:3.12-slim`; copiar el binario de `uv` desde la imagen oficial `ghcr.io/astral-sh/uv`; copiar `pyproject.toml`/`uv.lock` y ejecutar `uv sync --frozen --no-dev`; copiar `src/`; `EXPOSE 8000`; `CMD` arranca `uv run uvicorn src.adapters.inbound.api.app:app --host 0.0.0.0 --port 8000` (research.md → Decisión 6; FR-013).
- [X] T024 [P] [US3] Crear `.dockerignore` en la raíz de `week-1/starter-project/` excluyendo `.venv/`, `__pycache__/`, `*.pyc`, `.git/`, `.pytest_cache/`, `.ruff_cache/` y `tests/` (RNF-004).
- [X] T025 [P] [US3] Crear `docker-compose.yml` en la raíz de `week-1/starter-project/` con el servicio `db` (`image: postgres:16-alpine`; `environment` con credenciales de desarrollo documentadas como no aptas para producción; `volumes` con un volumen con nombre para `/var/lib/postgresql/data`; `healthcheck` con `pg_isready -U <usuario> -d <base>`) y el servicio `api` (`build: .`; `depends_on: db: condition: service_healthy`; `environment: DATABASE_URL=postgresql://...@db:5432/...`; `ports: ["8000:8000"]`; `healthcheck` vía un script Python de una línea contra `http://localhost:8000/health`, sin `curl`) (data-model.md → "Stack de contenedores"; research.md → Decisiones 6 y 7; contracts/health-check.md §3). Nota de tiempo de ejecución (no de autoría): para que el stack funcione al levantarlo, T008 (ruta `/health`) y T018 (soporte `postgresql://` en la fábrica) deben estar implementados.

**Checkpoint**: Las tres historias son funcionales y comprobables de forma independiente; la
validación dinámica completa contra PostgreSQL real queda en `quickstart.md` §4.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Verificación de fronteras hexagonales, regresión completa y validación manual de
punta a punta.

- [X] T026 Ejecutar `uv run ruff check src/` y confirmar que no hay violaciones `TID251`/`TID252` nuevas en `src/domain/`, `src/application/` o `src/adapters/inbound/` tras T006-T009 y T016-T019 (plan.md → Constitution Check, Principio IV). Depende de T006-T009, T016-T019.
- [X] T027 Ejecutar `uv run pytest -v` y confirmar que `tests/test_spec_001_triage.py` y `tests/test_spec_002_summary.py` siguen pasando sin cambios, junto con las 15 funciones nuevas de `tests/test_spec_004_runtime_health.py` (T001-T005, T010-T015, T020-T022, T030) (Constitución, Principio V). Depende de T001-T025, T030.
- [X] T028 [P] Actualizar la sección "Scope and layout"/"Commands" de `AGENTS.md` para documentar `GET /health`, el comando CLI `health`, `create_repository`, `PostgresIncidentRepository` y los comandos de Docker Compose (plan.md → Project Structure).
- [ ] T029 Ejecutar `quickstart.md` de punta a punta (secciones 1-4: `pytest` sin Docker, `ruff check`, `curl` contra SQLite local, y `docker compose up` con validación completa contra PostgreSQL — incluyendo detener `db` para observar el `503` real y reiniciarla para confirmar la persistencia del volumen) y confirmar manualmente los resultados esperados. Depende de T008, T009, T016-T018, T023-T025, T026, T027. **Parcial (2026-11-24)**: secciones 1-3 verificadas (pytest 30/30, ruff limpio, CLI `health` y `curl` contra SQLite local devuelven `200 OK`/`{"status":"ok","database":"connected"}`); la sección 4 (Docker Compose contra PostgreSQL real) no pudo ejecutarse en este entorno porque el daemon de Docker Desktop no está en ejecución (`docker compose up` falla con "failed to connect to the docker API"). Pendiente de validación manual por el usuario en una máquina con Docker Desktop activo.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Sin tareas — Foundational puede iniciar de inmediato.
- **Foundational (Phase 2)**: Sin tareas — las tres historias pueden iniciar de inmediato tras Setup.
- **User Stories (Phase 3-5)**: Las tres pueden implementarse en cualquier orden relativo entre sí (ninguna depende funcionalmente del código de otra), pero se recomienda el orden de prioridad P1 → P2 → P3 porque US3 (orquestación en contenedores) solo tiene sentido operativo una vez que `/health` (US1) y el soporte `postgresql://` (US2) existen.
- **Polish (Phase 6)**: Depende de que las historias que se quieran entregar estén completas.

### User Story Dependencies

- **US1 (P1)**: Puede iniciar tras Foundational. Sin dependencia de US2/US3; usa el `SQLiteIncidentRepository` ya existente.
- **US2 (P2)**: Puede iniciar tras Foundational, en paralelo con US1. Sin dependencia funcional de US1 (sus pruebas no invocan `/health`).
- **US3 (P3)**: Sus tareas de implementación (T023-T025) son archivos independientes que pueden escribirse en paralelo con US1/US2, pero el stack solo es operativamente correcto una vez que T008 (US1) y T018 (US2) existen — ver nota en T025.

### Within Each User Story

- Pruebas antes de la implementación correspondiente (T001-T005, T030 antes de T006-T009; T010-T015 antes de T016-T019; T020-T022 antes de T023-T025).
- Todas las funciones de prueba nuevas viven en el mismo archivo (`tests/test_spec_004_runtime_health.py`); se marcan `[P]` entre sí porque son funciones independientes sin dependencias de datos compartidas, siguiendo la misma convención ya usada en `tests/test_spec_003_lifecycle_sla.py`.

### Parallel Opportunities

- Tras Setup/Foundational (ambos sin tareas), un equipo puede avanzar US1 (T001-T009), US2 (T010-T019) y US3 (T020-T025) en paralelo desde el inicio.
- Dentro de US1: T001-T005 en paralelo entre sí; T006 y T007 en paralelo entre sí (archivos distintos); T008 depende de ambos, T009 depende de T006.
- Dentro de US2: T010-T015 en paralelo entre sí; T019 (ruff.toml) puede escribirse en paralelo con T016-T018 (archivos distintos, sin bloqueo real de autoría).
- Dentro de US3: T020-T022 en paralelo entre sí; T023, T024 y T025 en paralelo entre sí (tres archivos distintos).
- T028 (actualizar `AGENTS.md`) es independiente y puede hacerse en paralelo con T026/T027/T029.

---

## Parallel Example: Historias de Usuario (tras Foundational)

```bash
# US1, US2 y US3 pueden iniciar juntas (sin dependencia funcional entre sí):
Task: "Añadir IncidentService.check_health() en src/application/services.py"
Task: "Crear PostgresIncidentRepository en src/adapters/outbound/postgres_repository.py"
Task: "Crear Dockerfile en la raíz de week-1/starter-project/"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Completar Fase 1: Setup (sin tareas).
2. Completar Fase 2: Foundational (sin tareas).
3. Completar Fase 3: User Story 1 (`GET /health` + comando `health`).
4. **Detener y validar**: ejecutar `uv run pytest -v tests/test_spec_004_runtime_health.py` (subconjunto US1) y `quickstart.md` §§1 y 3.
5. Esto ya satisface SC-001 para el chequeo de salud contra SQLite.

### Incremental Delivery

1. Setup + Foundational → base lista (sin trabajo adicional).
2. + User Story 1 → probar de forma independiente → demo del chequeo de salud (MVP).
3. + User Story 2 → probar la selección de motor de forma independiente (sin Docker) → demo de `create_repository`.
4. + User Story 3 → levantar `docker compose up` → demo completa contra PostgreSQL real (SC-003, SC-004, SC-005).
5. Cada historia agrega valor sin romper la anterior; las 15 funciones de prueba nuevas quedan como regresión permanente junto con las ya existentes de H001/H002.

---

## Notes

- `[P]` = archivos distintos sin dependencias de autoría pendientes entre sí.
- `[Story]` identifica a qué historia de usuario pertenece cada tarea de las Fases 3-5; Setup, Foundational y Polish no llevan `[Story]`.
- Cada campo con restricción de `data-model.md` (`IncidentService.check_health()`, `HealthResponseSchema.status`/`.database`, el esquema de `PostgresIncidentRepository`, y las firmas de `create_repository`/`get_incident_repository`) queda citado explícitamente en al menos una tarea de implementación (T006, T007, T016, T017, T018).
- Ejecutar `uv run pytest -v` tras cada historia completa; `uv run ruff check src/` tras completar US1 y US2 (T026) y de nuevo al cierre.
- Evitar: pruebas de contenedores que dependan de que Docker esté instalado para que `pytest` pase (T020-T022 son estáticas por diseño); añadir `pyyaml` u otra dependencia de prueba nueva solo para parsear `docker-compose.yml` (se usa búsqueda de subcadenas, ver T022).
