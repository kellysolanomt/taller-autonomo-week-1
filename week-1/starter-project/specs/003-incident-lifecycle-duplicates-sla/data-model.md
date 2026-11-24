# Fase 1 — Modelo de datos: Ciclo de vida de incidentes, duplicados y SLA (H003)

## Entidades de dominio (`src/domain/models.py`)

### `Incident` (existente, con dos extensiones aditivas)

| Campo | Tipo | Notas |
|---|---|---|
| `incident_id` | `str` | Sin cambios. |
| `title` | `str` | Sin cambios. |
| `component` | `str` | Sin cambios. |
| `severity` | `SeverityLevel` | Sin cambios. |
| `status` | `IncidentStatus` | Sin cambios. |
| `created_at` | `datetime` | Sin cambios; naive. |
| `resolved_at` | `Optional[datetime]` | Sin cambios; naive. Igual a `created_at` cuando el incidente se registra directamente como `RESOLVED` (FR-002). |
| `symptom_category` | `Optional[SymptomCategory] = None` | Sin cambios (añadido en H002). |
| `recommended_team` | `Optional[TeamName] = None` | **Nuevo, aditivo.** Copia de `TriageResult.recommended_team` en el momento del registro (FR-016); persistido para que una futura lectura del incidente no necesite re-triajar el texto original. |
| `duplicate_group_key` | `Optional[str] = None` | **Nuevo, aditivo.** Copia de `TriageResult.duplicate_group_key` (`"<component>:<symptom_category>"`); es la columna que indexa `find_open_duplicates` (ver más abajo). `None` solo para incidentes creados antes de H003 sin este campo poblado. |

No se modifican `SLARule`, `SLAEvaluation`, `TriageResult` ni ninguna regla de
`triage_rules.py`/`sla_calculator.py`; `sla_calculator.py` solo gana la promoción de
`_require_naive` a `require_naive_datetime` (público, mismo cuerpo — ver `research.md`, Decisión 1).

## Tipos de aplicación (`src/application/services.py`)

Estructuras propias del caso de uso (no reglas de dominio), análogas a `ActiveIncidentsSummary` de H002.

### `IncidentCreationResult`

| Campo | Tipo | Origen |
|---|---|---|
| `incident_id` | `str` | Provisto o autogenerado (`research.md`, Decisión 5). |
| `title` | `str` | Solicitud. |
| `status` | `IncidentStatus` | Solicitud (default `"OPEN"`). |
| `created_at` | `datetime` | Resuelto por el adaptador antes de llamar al servicio. |
| `severity` | `SeverityLevel` | `TriageResult.severity`. |
| `component` | `str` | `TriageResult.component`. |
| `rationale` | `str` | `TriageResult.rationale`. |
| `recommended_team` | `TeamName` | `TriageResult.recommended_team`. |
| `duplicate_group_key` | `str` | `TriageResult.duplicate_group_key`. |
| `symptom_category` | `SymptomCategory` | `TriageResult.symptom_category`. |
| `impact_scope` | `ImpactScope` | `TriageResult.impact_scope`. |
| `consistency_ratio` | `float` | `TriageResult.consistency_ratio`. |
| `is_duplicate` | `bool` | `len(duplicate_of) > 0`. |
| `duplicate_of` | `list[str]` | IDs de `repository.find_open_duplicates(duplicate_group_key)`, consultados antes de guardar el incidente nuevo (FR-003; exclusión del propio id es automática — `research.md`, Decisión 2). |

Corresponde 1:1 a FR-016. Mapea sin pérdida a `IncidentCreatedResponseSchema` (ver `contracts/`).

No se define un dataclass nuevo para el resultado de `evaluate_incident_sla`: ese caso de uso
devuelve directamente `src.domain.models.SLAEvaluation` (ya tiene exactamente los campos de
FR-007: `incident_id`, `severity`, `elapsed_minutes`, `allowed_minutes`, `remaining_minutes`,
`is_breached`, `requires_escalation`), igual que `evaluate_sla_status` ya lo produce hoy.

### Excepciones (`src/application/services.py`)

| Excepción | Hereda de | Se lanza en | Traducción en el borde |
|---|---|---|---|
| `ValidationError` | `Exception` (existente) | `create_incident` (campos vacíos, `status` fuera de enum, `created_at` malformado/con `tzinfo`); `evaluate_incident_sla` (`reference_time` malformado/con `tzinfo`); `parse_naive_local_datetime` | `422` / código `1` |
| `IncidentConflictError` | `Exception` (nueva) | `create_incident`, cuando `incident_id` indicado ya existe | `409` / código `1` |
| `IncidentNotFoundError` | `Exception` (nueva, pedida explícitamente) | `evaluate_incident_sla`, cuando `repository.get_incident(incident_id)` devuelve `None` | `404` / código `1` |

El `ValueError` que lanza `evaluate_sla_status` cuando `reference_time < created_at` **no** se
envuelve: se propaga tal cual hasta el adaptador, que lo captura junto con `ValidationError`
(mismo patrón ya usado por `GET /api/v1/incidents/summary` en H002 — ver `research.md`, Decisión 3).

## Caso de uso (`IncidentService`)

```text
IncidentService(repository: IncidentRepositoryPort)   # constructor sin cambios

create_incident(
    title: str,
    raw_text: str,
    created_at: datetime,                 # siempre resuelto por el adaptador; nunca None aquí
    incident_id: Optional[str] = None,
    status: Optional[str] = None,         # None => "OPEN"
) -> IncidentCreationResult
# Raises: ValidationError, IncidentConflictError

evaluate_incident_sla(
    incident_id: str,
    reference_time: datetime,             # siempre resuelto por el adaptador; nunca None aquí
) -> SLAEvaluation
# Raises: IncidentNotFoundError, ValueError (propagado desde evaluate_sla_status)
```

Función auxiliar de módulo (no es un método de `IncidentService`; se importa igual desde ambos
adaptadores de entrada — `research.md`, Decisión 1):

```text
parse_naive_local_datetime(label: str, raw_value: Optional[str]) -> Optional[datetime]
# Raises: ValidationError (formato no ISO 8601, o tzinfo presente)
```

Algoritmo de `create_incident` (orquestación, sin regla de dominio nueva): ver `research.md`,
Decisión 7, pasos 1–7.

Algoritmo de `evaluate_incident_sla`:
1. `incident = repository.get_incident(incident_id)`; si `None`, `raise IncidentNotFoundError(...)`.
2. `return evaluate_sla_status(incident, reference_time)` (dominio puro, sin cambios; su propio
   `ValueError` por `reference_time` anterior a `created_at` se deja propagar).

Ninguno de los dos métodos lee el reloj del sistema ni reimplementa triaje o cálculo de SLA.

## Puerto de salida (`src/application/ports.py`)

### `IncidentRepositoryPort` — un método cambia de firma, el resto sin cambios

| Método | Firma | Cambio en H003 |
|---|---|---|
| `save_incident` | `(incident: Incident) -> None` | Sin cambio de firma; ahora persiste también `recommended_team` y `duplicate_group_key`. |
| `get_incident` | `(incident_id: str) -> Optional[Incident]` | Sin cambios. Ahora con caso de uso real: `evaluate_incident_sla` y la verificación de conflicto de `create_incident`. |
| `find_open_duplicates` | `(duplicate_group_key: str) -> list[Incident]` | **Cambia de `(component, symptom_category)` a `(duplicate_group_key)`** (`research.md`, Decisión 2). Ahora con caso de uso real en `create_incident`. Filtra `status in ("OPEN", "IN_PROGRESS", "ESCALATION_REQUIRED")` — conjunto propio de H003, distinto del `_ACTIVE_STATUSES` de H002. |
| `list_active_incidents` | `(component_filter: Optional[str] = None) -> list[Incident]` | Sin cambios (H002). |
| `check_health` | `() -> bool` | Sin cambios; sigue sin caso de uso propio (preparación H004). |

## Esquema SQLite (`src/adapters/outbound/sqlite_repository.py`)

```sql
CREATE TABLE IF NOT EXISTS incidents (
    incident_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    component TEXT NOT NULL,
    severity TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    resolved_at TEXT,
    symptom_category TEXT,              -- sin cambios (H002)
    recommended_team TEXT,              -- nuevo, nullable; aditivo (H003)
    duplicate_group_key TEXT            -- nuevo, nullable; aditivo (H003)
);

CREATE INDEX IF NOT EXISTS idx_incidents_component_status
ON incidents (component, status);        -- sin cambios (ADR-001 / H002)

CREATE INDEX IF NOT EXISTS idx_incidents_dup_key
ON incidents (duplicate_group_key, status);   -- nuevo (H003), pedido explícitamente por el usuario
```

- `save_incident`: el `INSERT OR REPLACE` gana las dos columnas nuevas (y sus dos `?` adicionales);
  sin cambios en el uso de placeholders (Constitución, Seguridad SQL).
- `find_open_duplicates(duplicate_group_key)`: pasa de filtrar por `component = ? AND
  symptom_category = ?` a filtrar por `duplicate_group_key = ?`, usando un nuevo conjunto interno
  fijo `_OPEN_FOR_DUPLICATES_STATUSES = ("OPEN", "IN_PROGRESS", "ESCALATION_REQUIRED")` (constante
  interna, nunca interpolada; distinta de `_ACTIVE_STATUSES` de H002, que sigue en
  `("OPEN", "IN_PROGRESS")` sin cambios).
- `_row_to_incident`: lee también `recommended_team` y `duplicate_group_key` de la fila.
- `get_incident`/`list_active_incidents`/`check_health`: sin cambios de comportamiento más allá de
  los dos campos nuevos que ahora viajan en cada `Incident` reconstruido.
