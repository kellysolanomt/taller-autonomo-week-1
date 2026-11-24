# Fase 1 — Modelo de datos: Resumen de incidentes activos (H002)

## Entidades de dominio (`src/domain/models.py`)

### `Incident` (existente, con una extensión aditiva)

| Campo | Tipo | Notas |
|---|---|---|
| `incident_id` | `str` | Sin cambios. |
| `title` | `str` | Sin cambios. Es el `título` del detalle (FR-005). |
| `component` | `str` | Sin cambios. Es el `componente` del detalle y el valor que compara el filtro (FR-006). |
| `severity` | `SeverityLevel` | Sin cambios. |
| `status` | `IncidentStatus` | Sin cambios. Activo = `OPEN` o `IN_PROGRESS` (Constitución 1.7). |
| `created_at` | `datetime` | Sin cambios; naive. |
| `resolved_at` | `Optional[datetime]` | Sin cambios; naive. |
| `symptom_category` | `Optional[SymptomCategory] = None` | **Nuevo, aditivo.** No lo exige ningún escenario de H002; existe para que `find_open_duplicates` (puerto) sea una consulta real desde ya, preparando H003 sin reimplementar nada cuando llegue. |

No se modifican `SLARule`, `SLAEvaluation`, `TriageResult` ni ninguna regla de `triage_rules.py`/`sla_calculator.py`.

## Tipos de aplicación (`src/application/services.py`)

Son estructuras de datos propias del caso de uso (no reglas de dominio), análogas a cómo `TriageResult` es el resultado estructurado de `triage_incident`.

### `ActiveIncidentSummaryItem`

| Campo | Tipo | Origen |
|---|---|---|
| `incident_id` | `str` | `Incident.incident_id` |
| `title` | `str` | `Incident.title` |
| `component` | `str` | `Incident.component` |
| `severity` | `SeverityLevel` | `Incident.severity` |
| `status` | `IncidentStatus` | `Incident.status` |
| `elapsed_minutes` | `int` | `SLAEvaluation.elapsed_minutes` (vía `evaluate_sla_status`) |
| `requires_escalation` | `bool` | `SLAEvaluation.requires_escalation` |

Corresponde 1:1 a FR-005. No incluye `is_breached` por ítem: para un incidente activo (nunca `RESOLVED`), `is_breached=True ⟹ requires_escalation=True` porque el umbral de escalamiento (75% del SLA) es siempre menor o igual al umbral de incumplimiento (100%); el detalle ya "lo refleja" (Escenario de Aceptación 3, Historia 1) a través de `requires_escalation`, sin duplicar el dato.

### `ActiveIncidentsSummary`

| Campo | Tipo | Regla de agregación |
|---|---|---|
| `total_active` | `int` | `len(items)` |
| `breached_count` | `int` | Cantidad de incidentes cuya `SLAEvaluation.is_breached` es `True` (calculado, no persistido). |
| `incidents` | `list[ActiveIncidentSummaryItem]` | Un ítem por incidente activo que cumple el filtro. |

Validación de invariantes: `0 <= breached_count <= total_active == len(incidents)`, verificable directamente en las pruebas de los Casos Límite de `spec.md` ("todos incumplieron" / "ninguno incumplió").

## Puerto de salida (`src/application/ports.py`)

### `IncidentRepositoryPort` (`typing.Protocol`, `@runtime_checkable`)

| Método | Firma | Usado por H002 |
|---|---|---|
| `save_incident` | `(incident: Incident) -> None` | Sí — siembra de datos en pruebas y futura persistencia de H003. |
| `get_incident` | `(incident_id: str) -> Optional[Incident]` | No directamente por el caso de uso; disponible para pruebas y para H003. |
| `find_open_duplicates` | `(component: str, symptom_category: str) -> list[Incident]` | No — preparación explícita para H003 (ver `research.md`, Decisión 4). |
| `list_active_incidents` | `(component_filter: Optional[str] = None) -> list[Incident]` | **Sí, es el único método que consume `get_active_incidents_summary`.** `None` = sin filtro (FR-007); un valor = coincidencia exacta de `component` (FR-006, Supuestos de `spec.md`). Solo devuelve incidentes con `status in ("OPEN", "IN_PROGRESS")` (FR-009); nunca incluye `RESOLVED`. |
| `check_health` | `() -> bool` | No — preparación para H004 (chequeo de conectividad, ADR-003); no tiene escenario propio en H002. |

El puerto no evalúa SLA ni cuenta incumplimientos: solo devuelve entidades `Incident`. Eso es responsabilidad de `IncidentService` (ver más abajo), no del adaptador de salida.

## Caso de uso (`IncidentService`)

```text
IncidentService(repository: IncidentRepositoryPort)

get_active_incidents_summary(
    component_filter: Optional[str],
    reference_time: datetime,
) -> ActiveIncidentsSummary
```

Algoritmo (orquestación, no regla de dominio nueva):

1. `incidents = repository.list_active_incidents(component_filter)` — una sola consulta, sin N+1 (FR-009, SC-006).
2. Para cada `incident`, `evaluation = evaluate_sla_status(incident, reference_time)` (dominio puro, sin cambios).
3. Construir un `ActiveIncidentSummaryItem` por incidente con los campos de la tabla de arriba.
4. `total_active = len(items)`, `breached_count = sum(1 for e in evaluations if e.is_breached)`.
5. Devolver `ActiveIncidentsSummary(total_active, breached_count, items)`.

No valida la forma de `component_filter` (cualquier cadena es un filtro legal, incluida una que no coincida con nada — FR-008); no lanza `ValidationError` en ningún caso de este caso de uso, a diferencia de `triage_incident`.

## Esquema SQLite (`src/adapters/outbound/sqlite_repository.py`)

Reutiliza el esquema ya validado por ADR-001 (`src/incident_repository.py`), con una columna nueva y nullable:

```sql
CREATE TABLE IF NOT EXISTS incidents (
    incident_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    component TEXT NOT NULL,
    severity TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    resolved_at TEXT,
    symptom_category TEXT               -- nuevo, nullable; preparación H003
);

CREATE INDEX IF NOT EXISTS idx_incidents_component_status
ON incidents (component, status);        -- sin cambios (ADR-001)
```

`list_active_incidents` sigue el mismo patrón de ADR-001 (una sola consulta, placeholders `?` para el conjunto fijo de estados activos); cuando `component_filter` es `None`, el predicado `component = ?` simplemente se omite de la consulta construida (nunca se interpola el valor del filtro, solo se decide qué cláusula fija incluir).
