---

description: "Task list template for feature implementation"
---

# Tasks: Ciclo de vida de incidentes, duplicados y SLA (H003)

**Input**: Design documents from `specs/003-incident-lifecycle-duplicates-sla/` (`spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/incident-lifecycle-sla.md`, `quickstart.md`)

**Prerequisites**: `plan.md` (completo, Constitution Check PASA), `spec.md` (3 historias de usuario P1/P2/P3, 19 escenarios de aceptación: 7+6+6), `research.md` (8 decisiones), `data-model.md` (entidades, excepciones y puerto), `contracts/incident-lifecycle-sla.md` (contrato HTTP + CLI)

**Tests**: Incluidos y obligatorios para esta funcionalidad — Constitución, Principio V, exige cobertura BDD automatizada para toda funcionalidad observable desde un adaptador de entrada, y la instrucción original del usuario pidió explícitamente `tests/test_spec_003_lifecycle_sla.py` con los 5+ escenarios BDD. Todas las funciones `test_bdd_*` van en ese único archivo nuevo, siguiendo la convención del skill `bdd-acceptance` (una función por escenario de `spec.md`, almacenamiento aislado por prueba, fixtures ya existentes de `tests/conftest.py` — research.md, Decisión 8).

**Organization**: Tareas agrupadas por historia de usuario (US1 = Historia 1 HTTP registro+duplicados, P1; US2 = Historia 2 HTTP auditoría de SLA, P2; US3 = Historia 3 paridad CLI, P3), precedidas por Setup y Foundational.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Puede ejecutarse en paralelo (archivo distinto, sin dependencias pendientes)
- **[Story]**: Historia de usuario a la que pertenece la tarea (US1, US2, US3)
- Todas las rutas de archivo son relativas a `week-1/starter-project/`

## Path Conventions

Proyecto único (ver `plan.md` → Structure Decision): `src/`, `tests/` en la raíz de `week-1/starter-project/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Inicialización de proyecto para esta funcionalidad.

**Sin tareas nuevas**: H003 no agrega dependencias, configuración de Ruff, ni paquetes nuevos bajo
`src/` (plan.md → Technical Context; research.md no identifica ninguna necesidad de este tipo).
Los `ruff.toml` jerárquicos de `src/domain/`, `src/application/` y `src/adapters/inbound/` ya
cubren exactamente las mismas fronteras que necesita H003. Continúa directamente en la Fase 2.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Extensión del dominio, re-firma del puerto de salida, esquema SQLite con el índice de
duplicados, y la función de parseo de fecha/hora compartida. Ninguna historia de usuario (US1/US2/
US3) puede implementarse sin esto, porque las tres dependen de `Incident.duplicate_group_key`
persistido y de `find_open_duplicates`/`parse_naive_local_datetime` ya disponibles.

**⚠️ CRITICAL**: Ninguna tarea de US1/US2/US3 puede empezar hasta que esta fase esté completa.

- [ ] T001 [P] Añadir los campos opcionales `recommended_team: Optional[TeamName] = None` y `duplicate_group_key: Optional[str] = None` a la entidad `Incident` en `src/domain/models.py` (data-model.md → Entidades de dominio, `Incident.recommended_team` e `Incident.duplicate_group_key`: ambos aditivos, sin romper construcciones existentes).
- [ ] T002 [P] En `src/domain/sla_calculator.py`, promover `_require_naive` a una función pública `require_naive_datetime(name: str, value: Optional[datetime]) -> None` (mismo cuerpo, mismo `ValueError`; actualizar las tres llamadas internas de `evaluate_sla_status`) (research.md → Decisión 1). Antes y después del cambio, ejecutar `uv run python -m src.domain.sla_calculator` como prueba de caracterización (Constitución, Principio V) y confirmar que los 15 casos borde y los 4 casos de error de ADR-002 siguen reportando exactamente los mismos resultados.
- [ ] T003 [P] En `src/application/ports.py`, cambiar la firma de `IncidentRepositoryPort.find_open_duplicates` de `(component: str, symptom_category: str) -> list[Incident]` a `find_open_duplicates(duplicate_group_key: str) -> list[Incident]` (data-model.md → `IncidentRepositoryPort.find_open_duplicates`; research.md → Decisión 2).
- [ ] T004 En `src/adapters/outbound/sqlite_repository.py`: añadir las columnas nullable `recommended_team TEXT` y `duplicate_group_key TEXT` a la tabla `incidents`, el índice `CREATE INDEX IF NOT EXISTS idx_incidents_dup_key ON incidents (duplicate_group_key, status)` (data-model.md → Esquema SQLite), actualizar `save_incident` (dos placeholders `?` nuevos) y `_row_to_incident` para persistir/leer ambas columnas, y reimplementar `find_open_duplicates(duplicate_group_key)` sobre una nueva constante interna fija `_OPEN_FOR_DUPLICATES_STATUSES = ("OPEN", "IN_PROGRESS", "ESCALATION_REQUIRED")` (distinta de `_ACTIVE_STATUSES` de H002), con la condición `duplicate_group_key = ? AND status IN (?, ?, ?)` parametrizada. Depende de T001, T003.
- [ ] T005 [P] En `src/application/services.py`, añadir la función de módulo `parse_naive_local_datetime(label: str, raw_value: Optional[str]) -> Optional[datetime]`: devuelve `None` si `raw_value` es `None`; intenta `datetime.fromisoformat(raw_value)` capturando `ValueError` y relanzando `ValidationError(f"{label} no es una fecha-hora ISO 8601 válida: ...")`; luego llama a `require_naive_datetime(label, value)` (de `src.domain.sla_calculator`) traduciendo su `ValueError` a `ValidationError` con el mismo mensaje (research.md → Decisión 1). Depende de T002.
- [ ] T006 Ejecutar `uv run pytest -v` y confirmar que `tests/test_spec_001_triage.py` y `tests/test_spec_002_summary.py` siguen pasando sin cambios tras T001-T005 (plan.md → Constitution Check, fila Principio I/V). Depende de T001-T005.

**Checkpoint**: El dominio extendido, el puerto re-firmado, el esquema SQLite con el índice de
duplicados y el parser compartido existen y no rompen H001/H002. Las historias de usuario pueden
empezar.

---

## Phase 3: User Story 1 - Registrar un incidente entrante y ser alertado de duplicados abiertos, por HTTP (Priority: P1) 🎯 MVP

**Goal**: Exponer `POST /api/v1/incidents`, que clasifica el reporte (motor de H001), lo guarda de
forma persistente y señala en la misma respuesta si hay incidentes equivalentes ya abiertos.

**Independent Test**: Enviar un incidente nuevo por HTTP, verificar que queda guardado (`201`,
`is_duplicate: false`), repetir el envío con el mismo componente/síntoma mientras el primero sigue
abierto y verificar que la respuesta señala el duplicado (spec.md → Historia 1, Escenarios 1-2).

### Tests for User Story 1 ⚠️

> Escribir estas pruebas primero y confirmar que fallan antes de implementar T014-T016.

- [ ] T007 [P] [US1] `test_bdd_registro_http_sin_duplicado_abierto` en `tests/test_spec_003_lifecycle_sla.py`, usando `summary_api_client`: `POST /api/v1/incidents` con `title`/`raw_text` válidos y sin ningún incidente abierto equivalente sembrado; verificar `201 Created`, el incidente disponible en una consulta posterior (`incident_repository.get_incident`), `is_duplicate: false` y `duplicate_of: []` (spec.md → Historia 1, Escenario de Aceptación 1; contracts/incident-lifecycle-sla.md §1.2).
- [ ] T008 [P] [US1] `test_bdd_registro_http_con_duplicado_abierto` en `tests/test_spec_003_lifecycle_sla.py`, usando `summary_api_client`: siembra (vía `incident_repository.save_incident`) un incidente `OPEN` con el mismo `component`/`symptom_category` que producirá el nuevo registro; `POST /api/v1/incidents` con un `raw_text` que clasifique igual; verificar `201 Created`, `is_duplicate: true` y `duplicate_of` listando exactamente el id sembrado (sin incluir el nuevo id) (spec.md → Historia 1, Escenario de Aceptación 2; contracts/incident-lifecycle-sla.md §1.2).
- [ ] T009 [P] [US1] `test_bdd_registro_http_duplicado_resuelto_no_cuenta` en `tests/test_spec_003_lifecycle_sla.py`, usando `summary_api_client`: siembra un incidente equivalente pero con `status="RESOLVED"`; `POST /api/v1/incidents` con las mismas características; verificar `is_duplicate: false` y `duplicate_of: []` (spec.md → Historia 1, Escenario de Aceptación 3; FR-005).
- [ ] T010 [P] [US1] `test_bdd_registro_http_incident_id_conflicto_409` en `tests/test_spec_003_lifecycle_sla.py`, usando `summary_api_client`: siembra un incidente con `incident_id="INC-DUP0001"`; `POST /api/v1/incidents` con ese mismo `incident_id`; verificar `409 Conflict`, cuerpo `{"error": ...}`, y que `incident_repository.get_incident("INC-DUP0001")` sigue devolviendo el incidente original sin modificar (spec.md → Historia 1, Escenario de Aceptación 4; FR-006).
- [ ] T011 [P] [US1] `test_bdd_registro_http_title_o_raw_text_vacio_422` en `tests/test_spec_003_lifecycle_sla.py`, usando `summary_api_client`: `POST /api/v1/incidents` con `title` vacío/solo espacios en un caso y `raw_text` vacío/solo espacios en otro; verificar `422 Unprocessable Entity` en ambos y que no se guarda ningún incidente (spec.md → Historia 1, Escenario de Aceptación 5; FR-015).
- [ ] T012 [P] [US1] `test_bdd_registro_http_defaults_autogenerados` en `tests/test_spec_003_lifecycle_sla.py`, usando `summary_api_client`: `POST /api/v1/incidents` omitiendo `incident_id`, `created_at` y `status`; verificar `201 Created` con `incident_id` que coincide con el patrón `INC-[0-9A-F]{8}`, `status: "OPEN"` y `created_at` igual al instante del registro (ventana de tolerancia razonable) (spec.md → Historia 1, Escenario de Aceptación 6; research.md → Decisión 5).
- [ ] T013 [US1] `test_bdd_registro_http_status_resolved_sla_cero_minutos` en `tests/test_spec_003_lifecycle_sla.py`, usando `summary_api_client`: `POST /api/v1/incidents` con `status: "RESOLVED"` explícito; verificar `201 Created` y, con `created_at` conocido, que `GET /api/v1/incidents/{incident_id}/sla` (ruta de la Fase 4/US2) responde `elapsed_minutes: 0` para cualquier `reference_time` posterior válido (spec.md → Historia 1, Escenario de Aceptación 7). **Depende de T025 (ruta de SLA, Fase 4)**: escribir la aserción de registro ahora, pero solo ejecutar/validar la aserción de SLA una vez completada la Fase 4, igual que el patrón de dependencia cruzada ya usado en H002 (tasks.md, T023 dependía de T020).

### Implementation for User Story 1

- [ ] T014 [US1] Añadir `CreateIncidentRequestSchema` (`title: str`, `raw_text: str`, `incident_id: Optional[str] = None`, `created_at: Optional[str] = None`, `status: Optional[str] = None`) e `IncidentCreatedResponseSchema` (todos los campos de `IncidentCreationResult`) a `src/adapters/inbound/api/schemas.py` (contracts/incident-lifecycle-sla.md §1.1-§1.2; research.md → Decisión 6, campos como `str` para evitar el cuerpo de error propio de Pydantic).
- [ ] T015 [US1] En `src/application/services.py`: añadir el dataclass `IncidentCreationResult` con los campos citados en data-model.md → `IncidentCreationResult` (`incident_id`, `title`, `status`, `created_at`, `severity`, `component`, `rationale`, `recommended_team`, `duplicate_group_key`, `symptom_category`, `impact_scope`, `consistency_ratio`, `is_duplicate`, `duplicate_of`); añadir la excepción `IncidentConflictError(Exception)`; añadir `IncidentService.create_incident(title, raw_text, created_at, incident_id=None, status=None) -> IncidentCreationResult` siguiendo el algoritmo de research.md → Decisión 7 (pasos 1-7: validar campos no vacíos, resolver/validar `status` contra el enum de `IncidentStatus`, resolver/verificar `incident_id` vía `repository.get_incident` y `secrets.token_hex(4).upper()` si se omite, clasificar con `classify_incident_report`, buscar duplicados con `repository.find_open_duplicates(triage.duplicate_group_key)` antes de guardar, construir y guardar el `Incident` con `resolved_at = created_at` si `status == "RESOLVED"`). Depende de T001, T003, T004, T005.
- [ ] T016 [US1] Añadir la ruta `POST /api/v1/incidents` en `src/adapters/inbound/api/app.py`: resuelve `created_at` con `parse_naive_local_datetime("created_at", request.created_at)` si se indica, o `datetime.now()` si se omite (research.md → Decisión 4); llama a `service.create_incident(...)`; mapea el resultado a `IncidentCreatedResponseSchema` con `201`; captura `ValidationError` → `422`, `IncidentConflictError` → `409` (ambos con cuerpo `{"error": ...}`). Además, registrar en `create_app()` un `@app.exception_handler(RequestValidationError)` que devuelva `422` con cuerpo `{"error": str(exc)}` en vez del cuerpo por defecto de FastAPI (research.md → Decisión 7; FR-019). Depende de T014, T015.

**Checkpoint**: La Historia 1 es funcional y comprobable de forma independiente (MVP), salvo la
mitad de T013 que depende de la Fase 4.

---

## Phase 4: User Story 2 - Auditar por HTTP el estado de SLA de un incidente registrado, para cualquier instante de referencia (Priority: P2)

**Goal**: Exponer `GET /api/v1/incidents/{incident_id}/sla`, reutilizando `evaluate_sla_status` del
dominio sin reimplementar ninguna regla de SLA.

**Independent Test**: Registrar un incidente con una fecha de apertura conocida (vía
`incident_repository.save_incident`, sin depender de US1) y consultar su SLA por HTTP para
distintos instantes de referencia, verificando los minutos/incumplimiento/escalamiento esperados
(spec.md → Historia 2, Escenarios 1, 6).

### Tests for User Story 2 ⚠️

- [ ] T017 [P] [US2] `test_bdd_sla_http_abierto_instante_posterior` en `tests/test_spec_003_lifecycle_sla.py`, usando `summary_api_client`: siembra un incidente `OPEN` con `created_at` conocido; `GET .../sla?reference_time=<posterior>`; verificar `200 OK` con `elapsed_minutes`, `is_breached` y `requires_escalation` calculados para ese instante (spec.md → Historia 2, Escenario de Aceptación 1).
- [ ] T018 [P] [US2] `test_bdd_sla_http_resuelto_no_acumula` en `tests/test_spec_003_lifecycle_sla.py`, usando `summary_api_client`: siembra un incidente `RESOLVED` con `resolved_at` conocido; consulta con un `reference_time` muy posterior a `resolved_at`; verificar que el resultado refleja el estado final hasta la resolución, sin acumular minutos después (spec.md → Historia 2, Escenario de Aceptación 2; FR-012).
- [ ] T019 [P] [US2] `test_bdd_sla_http_incidente_inexistente_404` en `tests/test_spec_003_lifecycle_sla.py`, usando `summary_api_client`: `GET /api/v1/incidents/INC-NO-EXISTE/sla`; verificar `404 Not Found` con cuerpo `{"error": ...}` (spec.md → Historia 2, Escenario de Aceptación 3; FR-010).
- [ ] T020 [P] [US2] `test_bdd_sla_http_sin_reference_time_usa_instante_consulta` en `tests/test_spec_003_lifecycle_sla.py`, usando `summary_api_client`: siembra un incidente `OPEN`; `GET .../sla` **sin** `reference_time` (ejercita `datetime.now()` en el adaptador); verificar `200 OK` con un `elapsed_minutes` consistente con "ahora" (tolerancia razonable) (spec.md → Historia 2, Escenario de Aceptación 4; FR-008).
- [ ] T021 [P] [US2] `test_bdd_sla_http_reference_time_anterior_a_apertura_422` en `tests/test_spec_003_lifecycle_sla.py`, usando `summary_api_client`: siembra un incidente con `created_at` conocido; `GET .../sla?reference_time=<anterior a created_at>`; verificar `422 Unprocessable Entity` (spec.md → Historia 2, Escenario de Aceptación 5; FR-009). Repetir el mismo caso con el incidente en `status="RESOLVED"` para cubrir FR-017 explícitamente.
- [ ] T022 [P] [US2] `test_bdd_sla_http_p2_horario_habil_ejemplo_numerico` en `tests/test_spec_003_lifecycle_sla.py`, usando `summary_api_client`: siembra un incidente P2 `OPEN` con `created_at="2026-11-06T17:00:00"` (viernes); `GET .../sla?reference_time=2026-11-09T09:00:00` (lunes); verificar exactamente `200 OK`, `elapsed_minutes=120`, `allowed_minutes=480`, `remaining_minutes=360`, `is_breached=false`, `requires_escalation=false` (spec.md → Historia 2, Escenario de Aceptación 6; contracts/incident-lifecycle-sla.md §2.2).

### Implementation for User Story 2

- [ ] T023 [US2] En `src/application/services.py`: añadir la excepción `IncidentNotFoundError(Exception)`; añadir `IncidentService.evaluate_incident_sla(incident_id: str, reference_time: datetime) -> SLAEvaluation`, que llama a `repository.get_incident(incident_id)` (lanzando `IncidentNotFoundError` si es `None`) y delega en `evaluate_sla_status` de `src.domain.sla_calculator` (dominio puro, sin cambios); el `ValueError` de "referencia anterior a la apertura" se deja propagar sin envolver (research.md → Decisión 3). Depende de T004.
- [ ] T024 [US2] Añadir `SLAEvaluationResponseSchema` (mismos campos de `SLAEvaluation`: `incident_id`, `severity`, `elapsed_minutes`, `allowed_minutes`, `remaining_minutes`, `is_breached`, `requires_escalation`) a `src/adapters/inbound/api/schemas.py` (contracts/incident-lifecycle-sla.md §2.2).
- [ ] T025 [US2] Añadir la ruta `GET /api/v1/incidents/{incident_id}/sla` en `src/adapters/inbound/api/app.py`: resuelve `reference_time` con `parse_naive_local_datetime("reference_time", reference_time)` si se indica como query param `str`, o `datetime.now()` si se omite; llama a `service.evaluate_incident_sla(...)`; mapea a `SLAEvaluationResponseSchema` con `200`; captura `IncidentNotFoundError` → `404`, `(ValidationError, ValueError)` → `422` (todos con cuerpo `{"error": ...}`). Depende de T023, T024.

**Checkpoint**: Las Historias 1 y 2 funcionan juntas e independientemente; T013 (US1) puede
completarse ahora.

---

## Phase 5: User Story 3 - Obtener el mismo registro, alerta de duplicados y auditoría de SLA desde el CLI (Priority: P3)

**Goal**: Paridad de resultado de negocio entre HTTP y CLI para el registro y la auditoría de SLA
(FR-001, FR-007).

**Independent Test**: Ejecutar los comandos `create` y `sla` con los mismos incidentes e instantes
de referencia usados en las Historias 1 y 2, verificando que cada resultado es idéntico al
obtenido por HTTP (spec.md → Historia 3, Escenarios 1-2).

### Tests for User Story 3 ⚠️

- [ ] T026 [P] [US3] `test_bdd_cli_create_duplicado_mismo_resultado_que_http` en `tests/test_spec_003_lifecycle_sla.py`, usando `summary_cli_app` vía `cli_runner.invoke` sobre el **mismo** `incident_repository`/`incident_service` que un `summary_api_client` sembrado con un incidente abierto equivalente: ejecutar `create`; verificar código de salida `0` y que `is_duplicate`/`duplicate_of` en la salida JSON coinciden con el caso HTTP equivalente de T008 (spec.md → Historia 3, Escenario de Aceptación 1).
- [ ] T027 [P] [US3] `test_bdd_cli_sla_mismo_resultado_que_http_p2_horario_habil` en `tests/test_spec_003_lifecycle_sla.py`, usando `summary_cli_app`: mismo incidente P2 e instantes de T022; ejecutar `sla --reference-time 2026-11-09T09:00:00`; verificar código de salida `0` y los mismos valores exactos (`elapsed_minutes=120`, `allowed_minutes=480`, `remaining_minutes=360`, `is_breached=false`, `requires_escalation=false`) (spec.md → Historia 3, Escenario de Aceptación 2).
- [ ] T028 [P] [US3] `test_bdd_cli_sla_incidente_inexistente_exit1` en `tests/test_spec_003_lifecycle_sla.py`, usando `summary_cli_app`: ejecutar `sla --incident-id INC-NO-EXISTE`; verificar código de salida `1` y `{"error": ...}` en la salida (spec.md → Historia 3, Escenario de Aceptación 3).
- [ ] T029 [P] [US3] `test_bdd_cli_create_title_o_raw_text_vacio_exit1` en `tests/test_spec_003_lifecycle_sla.py`, usando `summary_cli_app`: ejecutar `create` con `--title ""` y con `--raw-text "   "`; verificar código de salida `1` en ambos casos y que no se guarda ningún incidente (spec.md → Historia 3, Escenario de Aceptación 4).
- [ ] T030 [P] [US3] `test_bdd_cli_create_incident_id_conflicto_exit1` en `tests/test_spec_003_lifecycle_sla.py`, usando `summary_cli_app`: siembra un incidente con un `incident_id` fijo; ejecutar `create --incident-id <el mismo>`; verificar código de salida `1`, `{"error": ...}` en la salida, y que el incidente ya registrado no se modifica (spec.md → Historia 3, Escenario de Aceptación 5).
- [ ] T031 [P] [US3] `test_bdd_cli_sla_reference_time_anterior_exit1` en `tests/test_spec_003_lifecycle_sla.py`, usando `summary_cli_app`: siembra un incidente con `created_at` conocido; ejecutar `sla --reference-time <anterior>`; verificar código de salida `1` (spec.md → Historia 3, Escenario de Aceptación 6).

### Implementation for User Story 3

- [ ] T032 [US3] Añadir el comando `create` dentro de `create_cli_app` en `src/adapters/inbound/cli.py`, con opciones `--title`, `--raw-text` (obligatorias), `--incident-id`, `--created-at`, `--status` (opcionales, todas `str`); mismo tratamiento de `created_at` por defecto que T016 (`datetime.now()` solo si se omite `--created-at`); imprime en `stdout` el mismo cuerpo JSON que `IncidentCreatedResponseSchema` y termina en código `0`; captura `ValidationError`/`IncidentConflictError` → imprime `{"error": ...}` en `stderr` y `raise typer.Exit(code=1)` (contracts/incident-lifecycle-sla.md §3). Depende de T015.
- [ ] T033 [US3] Añadir el comando `sla` dentro de `create_cli_app` en `src/adapters/inbound/cli.py`, con opciones `--incident-id` (obligatoria) y `--reference-time` (opcional, `str`); mismo tratamiento por defecto que T025; imprime en `stdout` el mismo cuerpo JSON que `SLAEvaluationResponseSchema` y termina en código `0`; captura `IncidentNotFoundError`/`ValidationError`/`ValueError` → imprime `{"error": ...}` en `stderr` y `raise typer.Exit(code=1)` (contracts/incident-lifecycle-sla.md §3). Depende de T023.

**Checkpoint**: Las tres historias de usuario son funcionales y comprobables de forma
independiente.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Cobertura de los requisitos transversales de forma/validación (FR-018/FR-019/FR-020)
que no quedan cubiertos por los 19 escenarios de aceptación numerados, verificación del índice
nuevo, fronteras hexagonales y limpieza documental.

- [ ] T034 [P] `test_bdd_created_at_malformado_no_usa_codigo_propio_del_framework` en `tests/test_spec_003_lifecycle_sla.py`, usando `summary_api_client` y `summary_cli_app`: `POST /api/v1/incidents` con `created_at: "no-es-una-fecha"` → `422` con `{"error": ...}`; `create --created-at no-es-una-fecha` → código de salida `1` (nunca `2` de Typer/Click) con `{"error": ...}` en `stderr` (spec.md → Casos Límite; FR-018).
- [ ] T035 [P] `test_bdd_tzinfo_en_created_at_o_reference_time_es_422_nunca_500` en `tests/test_spec_003_lifecycle_sla.py`, usando `summary_api_client`: `POST /api/v1/incidents` con `created_at: "2026-11-24T09:00:00+00:00"` y `GET .../sla?reference_time=2026-11-24T09:00:00-05:00` sobre un incidente ya sembrado; verificar `422` con `{"error": ...}` en ambos casos, nunca `500` (spec.md → Casos Límite; FR-020).
- [ ] T036 [P] `test_bdd_status_fuera_de_enum_422` en `tests/test_spec_003_lifecycle_sla.py`, usando `summary_api_client`: `POST /api/v1/incidents` con `status: "CERRADO"` (fuera de `OPEN`/`IN_PROGRESS`/`ESCALATION_REQUIRED`/`RESOLVED`); verificar `422` con `{"error": ...}` (spec.md → Casos Límite; FR-002).
- [ ] T037 `test_bdd_post_incidents_campo_obligatorio_ausente_cuerpo_error_uniforme` en `tests/test_spec_003_lifecycle_sla.py`, usando `summary_api_client`: `POST /api/v1/incidents` con un cuerpo JSON que omite `title` por completo (no solo vacío); verificar `422` con cuerpo exactamente `{"error": "<mensaje>"}`, nunca el cuerpo por defecto de FastAPI (`{"detail": [...]}`) (research.md → Decisión 7; FR-019). Depende de T016 (manejador de `RequestValidationError`).
- [ ] T038 `test_bdd_indice_duplicate_group_key_existe` en `tests/test_spec_003_lifecycle_sla.py`, usando `incident_repository`: ejecutar `PRAGMA index_list(incidents)` sobre `incident_repository.conn` y verificar que `idx_incidents_dup_key` está presente, confirmando el índice pedido explícitamente por el usuario sobre `(duplicate_group_key, status)` (data-model.md → Esquema SQLite). Depende de T004.
- [ ] T039 Ejecutar `uv run ruff check src/` y confirmar que no hay violaciones `TID251`/`TID252` nuevas en `src/domain/`, `src/application/` o `src/adapters/inbound/` tras T001-T005, T014-T016, T023-T025, T032-T033 (plan.md → Constitution Check, Principio IV). Depende de esas tareas.
- [ ] T040 [P] Actualizar la sección "Scope and layout" de `AGENTS.md` para documentar los campos nuevos de `Incident`, la firma actualizada de `find_open_duplicates`, las rutas `POST /api/v1/incidents`/`GET /api/v1/incidents/{incident_id}/sla` y los comandos `create`/`sla` del CLI (plan.md → Project Structure).
- [ ] T041 Ejecutar `quickstart.md` de punta a punta (secciones 1-4: `pytest`, `ruff check`, `curl`, CLI) y confirmar manualmente la paridad HTTP/CLI del registro y la auditoría de SLA con un `DATABASE_URL` de archivo compartido (quickstart.md §4). Depende de T016, T025, T032, T033, T039.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Sin tareas — Foundational puede iniciar de inmediato.
- **Foundational (Phase 2)**: **Bloquea** US1, US2 y US3; las tres dependen de `Incident.duplicate_group_key` (T001), `find_open_duplicates` re-firmado (T003, T004) y `parse_naive_local_datetime` (T005).
- **User Stories (Phase 3-5)**: Todas dependen de Foundational. US1 es el MVP; US2 no depende de US1 (su prueba independiente siembra directamente vía `incident_repository`); US3 reutiliza `create_incident` (T015) y `evaluate_incident_sla` (T023) de US1/US2 para construir los comandos CLI, por lo que su implementación depende de ambas, aunque sus pruebas pueden escribirse antes.
- **Polish (Phase 6)**: Depende de que las historias que se quieran entregar estén completas; T037 depende puntualmente de T016 y T038 de T004.

### User Story Dependencies

- **US1 (P1)**: Puede iniciar tras Foundational. Sin dependencia funcional de otras historias, salvo la mitad de T013 (verificación de SLA posterior a un registro `RESOLVED`), que depende de que exista la ruta de SLA de US2.
- **US2 (P2)**: Puede iniciar tras Foundational; es independiente de US1 (siembra sus propios incidentes directamente en el repositorio para sus pruebas).
- **US3 (P3)**: Depende funcionalmente de T015 (US1) y T023 (US2) para su implementación (T032/T033 invocan esos mismos métodos de `IncidentService`); sus pruebas (T026-T031) pueden escribirse en paralelo con US1/US2, pero solo pasan una vez implementados T032/T033.

### Within Each User Story

- Pruebas `test_bdd_*` antes de la implementación correspondiente (T007-T013 antes de T014-T016; T017-T022 antes de T023-T025; T026-T031 antes de T032-T033).
- Todas las funciones de prueba viven en el mismo archivo nuevo (`tests/test_spec_003_lifecycle_sla.py`): no se marcan `[P]` entre sí dentro de una misma historia para evitar conflictos de edición concurrente sobre el mismo archivo, salvo que se coordinen bloques de código no solapados.

### Parallel Opportunities

- Fase 2: T001, T002, T003, T005 pueden iniciar en paralelo (archivos distintos, sin dependencia mutua entre sí); T004 depende de T001 y T003; T006 depende de todas.
- Entre historias: una vez cerrada Foundational, un equipo podría avanzar T007-T013 (US1), T017-T022 (US2) y T026-T031 (US3, como pruebas que fallarán hasta T032/T033) en paralelo; en la práctica, al depender la implementación de US3 de US1 y US2, se recomienda el orden P1 → P2 → P3 para la implementación, aunque las pruebas de las tres historias puedan redactarse desde el inicio.
- T040 (actualizar `AGENTS.md`) es independiente de T034-T039/T041 y puede hacerse en paralelo con ellas.

---

## Parallel Example: Foundational (Phase 2)

```bash
# T001, T002, T003 y T005 pueden iniciar juntos (archivos distintos, sin dependencia entre ellos):
Task: "Añadir recommended_team/duplicate_group_key a Incident en src/domain/models.py"
Task: "Promover _require_naive a require_naive_datetime en src/domain/sla_calculator.py"
Task: "Re-firmar find_open_duplicates(duplicate_group_key) en src/application/ports.py"
Task: "Añadir parse_naive_local_datetime en src/application/services.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Completar Fase 1: Setup (sin tareas).
2. Completar Fase 2: Foundational (bloqueante para todo lo demás).
3. Completar Fase 3: User Story 1 (`POST /api/v1/incidents`), salvo la mitad de T013.
4. **Detener y validar**: ejecutar `uv run pytest -v tests/test_spec_003_lifecycle_sla.py -k US1` (o el subconjunto equivalente) y las secciones 1-3 de `quickstart.md` relativas al registro.
5. Esto ya satisface SC-001 y SC-003 para la interfaz HTTP.

### Incremental Delivery

1. Setup + Foundational → base lista.
2. + User Story 1 → probar de forma independiente → demo de registro con alerta de duplicados (MVP).
3. + User Story 2 → probar la auditoría de SLA de forma independiente (incluye completar T013) → demo de auditoría (SC-004, SC-005).
4. + User Story 3 → probar paridad HTTP/CLI de forma independiente → demo CLI (SC-002).
5. Cada historia agrega valor sin romper la anterior; las 19 funciones `test_bdd_*` de las historias de usuario, más las 5 pruebas transversales de la Fase 6 (T034-T038), quedan como regresión permanente.

---

## Notes

- `[P]` = archivos distintos sin dependencias pendientes entre sí.
- `[Story]` identifica a qué historia de usuario pertenece cada tarea de las Fases 3-5; Setup, Foundational y Polish no llevan `[Story]`.
- Cada campo con restricción de `data-model.md` (`Incident.recommended_team`, `Incident.duplicate_group_key`, los campos de `IncidentCreationResult`, las excepciones `IncidentConflictError`/`IncidentNotFoundError`, y la firma re-indexada de `IncidentRepositoryPort.find_open_duplicates`) queda citado explícitamente en al menos una tarea de implementación (T001, T003, T004, T015, T023).
- Ejecutar `uv run pytest -v` tras cada tarea o grupo lógico de tareas (Constitución, Principio V); `uv run ruff check src/` tras completar Foundational y de nuevo al cierre (T039).
- Evitar: pruebas vagas sin escenario citado de `spec.md`, ediciones concurrentes al mismo archivo de test, y dependencias cruzadas entre historias que rompan su independencia (la única excepción documentada es T013, análoga a la ya aceptada en H002).
