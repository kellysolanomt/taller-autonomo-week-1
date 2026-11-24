# Contrato de interfaz: Resumen de incidentes activos (H002)

Referencia de negocio: `../spec.md`. Referencia de diseño: `../data-model.md`, `../research.md`.

## 1. Contrato HTTP

### 1.1 Solicitud

```
GET /api/v1/incidents/summary
```

Parámetros de consulta (query params), ambos opcionales:

| Parámetro | Tipo | Default si se omite | Regla |
|---|---|---|---|
| `component` | `string` | ninguno (sin filtro) | Coincidencia exacta, sensible a mayúsculas/minúsculas (Supuestos de `spec.md`). Un valor que no coincide con ningún incidente activo devuelve un resumen vacío válido (FR-008), nunca un error. |
| `reference_time` | `string` (ISO 8601, datetime naive) | instante en que se procesa la solicitud (FR-013) | Si se indica, debe ser naive (sin offset de zona horaria); un valor con zona horaria produce el mismo `ValueError` de `evaluate_sla_status`, propagado como `422`. |

No hay cuerpo de solicitud. No se requiere autenticación (Supuestos de `spec.md`, consistente con H001).

### 1.2 Respuesta exitosa — `200 OK`

```json
{
  "total_active": 3,
  "breached_count": 1,
  "incidents": [
    {
      "incident_id": "INC-1042",
      "title": "Latencia elevada en reporte de órdenes",
      "component": "reporting-api",
      "severity": "P2",
      "status": "OPEN",
      "elapsed_minutes": 495,
      "requires_escalation": true
    }
  ]
}
```

- Siempre `200 OK`, incluso cuando `total_active` es `0` (Escenario de Aceptación 2, Historia 1; Escenario de Aceptación 2, Historia 3). El cuerpo en ese caso es `{"total_active": 0, "breached_count": 0, "incidents": []}`.
- El orden del arreglo `incidents` no está garantizado por el contrato (Supuestos de `spec.md`); cualquier orden estable es válido.
- Ningún incidente con `status` distinto de `OPEN`/`IN_PROGRESS` aparece en `incidents` (FR-009).

### 1.3 Errores

| Código | Causa | Cuerpo |
|---|---|---|
| `422 Unprocessable Entity` | `reference_time` con zona horaria, o con formato no parseable como fecha/hora ISO 8601 naive. | `{"error": "<mensaje>"}` |
| `500 Internal Server Error` | Fallo inesperado no cubierto por una regla de negocio (mismo manejador genérico que H001). | `{"error": "<mensaje>"}` |

No existe ningún caso de `component` inválido: cualquier cadena es un filtro legal (FR-006/FR-008), por lo que `component` nunca produce un error de validación.

### 1.4 Operación

Igual que H001: `uv run uvicorn src.adapters.inbound.api.app:app --reload` desde `week-1/starter-project`.

## 2. Contrato CLI

```
uv run python -m src.adapters.inbound.cli summary [--component <texto>] [--reference-time <ISO8601>]
```

| Opción | Obligatoria | Regla |
|---|---|---|
| `--component` | No | Misma semántica que el query param `component`. |
| `--reference-time` | No | Misma semántica que el query param `reference_time`; mismo formato ISO 8601 naive. |

### 2.1 Salida estándar (éxito)

Imprime en `stdout` el mismo cuerpo JSON que la respuesta HTTP `200 OK` (mismas claves: `total_active`, `breached_count`, `incidents`), y termina con código de salida `0` — incluyendo el caso de resumen vacío (Escenario de Aceptación 2, Historia 2), que **no** es un error.

### 2.2 Salida de error

Si `--reference-time` tiene zona horaria o formato inválido, imprime `{"error": "<mensaje>"}` en `stderr` y termina con código de salida `1`, igual que el patrón ya usado por el comando `triage`.

## 3. Paridad HTTP/CLI (FR-002, SC-002)

Para la misma combinación de `component`/`reference_time` (o su ausencia) sobre el mismo conjunto de incidentes, el cuerpo JSON de la respuesta HTTP y el de la salida estándar de la CLI deben ser idénticos en contenido de negocio (mismo `total_active`, mismo `breached_count`, mismo contenido de `incidents` salvo el orden). Ambos adaptadores invocan exclusivamente `IncidentService.get_active_incidents_summary(...)`; ninguno reimplementa el cálculo.
