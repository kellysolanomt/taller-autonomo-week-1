# Contrato de interfaz: Ciclo de vida de incidentes, duplicados y SLA (H003)

Referencia de negocio: `../spec.md`. Referencia de diseño: `../data-model.md`, `../research.md`.

## 1. Registro de un incidente — `POST /api/v1/incidents`

### 1.1 Solicitud

```
POST /api/v1/incidents
Content-Type: application/json
```

```json
{
  "title": "Caída del gateway de pagos",
  "raw_text": "El gateway de pagos devuelve HTTP 502 para todos los comercios desde hace 10 minutos.",
  "incident_id": "INC-9001",
  "created_at": "2026-11-24T09:00:00",
  "status": "OPEN"
}
```

| Campo | Tipo | Obligatorio | Default si se omite | Regla |
|---|---|---|---|---|
| `title` | `string` | Sí | — | Rechazado (`422`) si está vacío o solo espacios (FR-015). |
| `raw_text` | `string` | Sí | — | Rechazado (`422`) si está vacío o solo espacios (FR-015). Mismo motor de clasificación que `POST /api/v1/incidents/triage` (H001). |
| `incident_id` | `string` | No | autogenerado `INC-<HEX8>` (8 hex) | Si se indica y ya existe, `409 Conflict` (FR-006); el incidente existente no se modifica. |
| `created_at` | `string` (ISO 8601, naive) | No | instante del registro | `422` si no es ISO 8601 válido o incluye `tzinfo` (FR-018/FR-020). **Tipo `string`, no `datetime`**: ver `../research.md`, Decisión 6. |
| `status` | `string` | No | `"OPEN"` | Uno de `OPEN`, `IN_PROGRESS`, `ESCALATION_REQUIRED`, `RESOLVED`; cualquier otro valor es `422` (FR-002). Si es `RESOLVED`, `resolved_at = created_at` (0 minutos transcurridos). |

No se requiere autenticación (igual que H001/H002).

### 1.2 Respuesta exitosa — `201 Created`

```json
{
  "incident_id": "INC-9001",
  "title": "Caída del gateway de pagos",
  "status": "OPEN",
  "created_at": "2026-11-24T09:00:00",
  "severity": "P0",
  "component": "payments-gateway",
  "rationale": "Síntoma 'outage' con alcance 'global' en payments-gateway -> P0; se enruta a Backend-Core.",
  "recommended_team": "Backend-Core",
  "duplicate_group_key": "payments-gateway:outage",
  "symptom_category": "outage",
  "impact_scope": "global",
  "consistency_ratio": 1.0,
  "is_duplicate": true,
  "duplicate_of": ["INC-8977"]
}
```

- `is_duplicate`/`duplicate_of` reflejan los incidentes **ya abiertos** (`OPEN`, `IN_PROGRESS`,
  `ESCALATION_REQUIRED`) con el mismo `duplicate_group_key`, excluyendo siempre el propio
  `incident_id` recién creado y cualquier `RESOLVED` (FR-003, FR-005). `duplicate_of: []` y
  `is_duplicate: false` cuando no hay ninguno.
- El incidente queda guardado igual, haya o no duplicado (FR-004): la alerta nunca bloquea el registro.
- `severity`, `component`, `rationale`, `recommended_team`, `duplicate_group_key`,
  `symptom_category`, `impact_scope`, `consistency_ratio` son exactamente los campos de
  `TriageResult` (H001), derivados de `raw_text` — nunca recibidos en la solicitud.

### 1.3 Errores

| Código | Causa | Cuerpo |
|---|---|---|
| `422 Unprocessable Entity` | `title`/`raw_text` vacío o solo espacios; `status` fuera del enum; `created_at` no ISO 8601 o con `tzinfo`; cuerpo JSON malformado o con un campo obligatorio ausente. | `{"error": "<mensaje>"}` |
| `409 Conflict` | `incident_id` indicado ya existe. | `{"error": "<mensaje>"}` |
| `500 Internal Server Error` | Fallo inesperado no cubierto por una regla de negocio (manejador genérico, sin cambios desde H001). | `{"error": "<mensaje>"}` |

Todo error de esta ruta —de regla de negocio o de forma de la solicitud— tiene siempre el mismo
cuerpo `{"error": <mensaje>}` (FR-019); un campo ausente o un JSON inválido producen `422` con ese
mismo cuerpo, nunca el cuerpo por defecto de FastAPI (`../research.md`, Decisión 7).

## 2. Auditoría de SLA — `GET /api/v1/incidents/{incident_id}/sla`

### 2.1 Solicitud

```
GET /api/v1/incidents/{incident_id}/sla?reference_time=2026-11-09T09:00:00
```

| Parámetro | Tipo | Obligatorio | Default si se omite | Regla |
|---|---|---|---|---|
| `incident_id` | `string` (ruta) | Sí | — | Si no corresponde a ningún incidente registrado, `404 Not Found` (FR-010). |
| `reference_time` | `string` (query, ISO 8601, naive) | No | instante de la consulta (FR-008) | `422` si no es ISO 8601 válido, incluye `tzinfo`, o es anterior al `created_at` del incidente — esta última comparación aplica sin importar el estado, incluso `RESOLVED` (FR-009/FR-017). **Tipo `string`, no `datetime`**: ver `../research.md`, Decisión 6. |

### 2.2 Respuesta exitosa — `200 OK`

```json
{
  "incident_id": "INC-9001",
  "severity": "P2",
  "elapsed_minutes": 120,
  "allowed_minutes": 480,
  "remaining_minutes": 360,
  "is_breached": false,
  "requires_escalation": false
}
```

Ejemplo numérico de referencia (Historia 2, Escenario de Aceptación 6 de `../spec.md`): un
incidente P2 creado el viernes `2026-11-06T17:00:00`, consultado el lunes `2026-11-09T09:00:00`,
produce exactamente el cuerpo de arriba (1 hora hábil del viernes + 1 hora hábil del lunes; el
fin de semana no consume SLA — regla ya vigente de `src/domain/sla_calculator.py`, sin cambios).

Un incidente ya `RESOLVED` refleja su estado final hasta la resolución, sin seguir acumulando
minutos (FR-012) — comportamiento ya existente de `evaluate_sla_status`, reutilizado sin cambios.

### 2.3 Errores

| Código | Causa | Cuerpo |
|---|---|---|
| `404 Not Found` | `incident_id` no corresponde a ningún incidente registrado. | `{"error": "<mensaje>"}` |
| `422 Unprocessable Entity` | `reference_time` no ISO 8601, con `tzinfo`, o anterior al `created_at` del incidente (cualquier estado). | `{"error": "<mensaje>"}` |
| `500 Internal Server Error` | Fallo inesperado no cubierto por una regla de negocio. | `{"error": "<mensaje>"}` |

### 2.4 Operación (ambas rutas)

Igual que H001/H002: `uv run uvicorn src.adapters.inbound.api.app:app --reload` desde
`week-1/starter-project`.

## 3. Contrato CLI

```
uv run python -m src.adapters.inbound.cli create --title "<texto>" --raw-text "<texto>" \
    [--incident-id <texto>] [--created-at <ISO8601>] [--status <OPEN|IN_PROGRESS|ESCALATION_REQUIRED|RESOLVED>]

uv run python -m src.adapters.inbound.cli sla --incident-id <texto> [--reference-time <ISO8601>]
```

| Comando | Opción | Obligatoria | Regla |
|---|---|---|---|
| `create` | `--title` | Sí | Misma semántica que `title` en el cuerpo HTTP. |
| `create` | `--raw-text` | Sí | Misma semántica que `raw_text`. |
| `create` | `--incident-id` | No | Misma semántica que `incident_id`. |
| `create` | `--created-at` | No | Misma semántica que `created_at`; opción `str`, nunca `datetime` (ver `../research.md`, Decisión 6), para que un formato inválido nunca termine con el código de salida propio de Typer/Click. |
| `create` | `--status` | No | Misma semántica que `status`. |
| `sla` | `--incident-id` | Sí | Misma semántica que el parámetro de ruta `incident_id`. |
| `sla` | `--reference-time` | No | Misma semántica que el query param `reference_time`; opción `str`, misma razón que `--created-at`. |

### 3.1 Salida estándar (éxito)

`create` imprime en `stdout` el mismo cuerpo JSON que la respuesta HTTP `201 Created` (mismas
claves) y termina con código de salida `0`. `sla` imprime en `stdout` el mismo cuerpo JSON que la
respuesta HTTP `200 OK` y termina con código de salida `0`.

### 3.2 Salida de error

Ante cualquiera de las condiciones de error de las secciones 1.3/2.3, ambos comandos imprimen
`{"error": "<mensaje>"}` en `stderr` y terminan con código de salida `1` — nunca con el código de
salida propio de Typer/Click (p. ej. `2`) ni con una traza no controlada (FR-018).

## 4. Paridad HTTP/CLI (FR-001, FR-007, SC-002)

Para la misma solicitud de registro (mismos `title`/`raw_text`/`incident_id`/`created_at`/`status`)
o la misma auditoría de SLA (mismo `incident_id`/`reference_time`) sobre el mismo conjunto de
incidentes ya guardados, el cuerpo JSON de la respuesta HTTP y el de la salida estándar de la CLI
deben ser idénticos en contenido de negocio. Ambos adaptadores invocan exclusivamente
`IncidentService.create_incident(...)` / `IncidentService.evaluate_incident_sla(...)`; ninguno
reimplementa triaje, verificación de duplicados o cálculo de SLA (skill `hexagonal-architecture`,
sección 2).
