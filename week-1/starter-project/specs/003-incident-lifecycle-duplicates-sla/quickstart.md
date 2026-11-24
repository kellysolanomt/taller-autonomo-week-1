# Quickstart — Validación de H003 (Ciclo de vida, duplicados y SLA)

Todos los comandos se ejecutan desde `week-1/starter-project/` (ver `AGENTS.md`).

## Prerrequisitos

```bash
uv sync
```

## 1. Verificación automatizada (primaria)

```bash
uv run pytest -v
```

Debe incluir, además de las pruebas de H001 (`tests/test_spec_001_triage.py`) y H002
(`tests/test_spec_002_summary.py`), las funciones `test_bdd_*` de
`tests/test_spec_003_lifecycle_sla.py` — una por cada Escenario de Aceptación de `../spec.md`
(7 de la Historia 1, 6 de la Historia 2, 6 de la Historia 3). Ver el contrato esperado de cada
función en `../contracts/incident-lifecycle-sla.md` y el modelo de datos en `../data-model.md`.

```bash
uv run python -m src.domain.sla_calculator
```

No debe reportar fallos; H003 no modifica ninguna regla de SLA, solo promueve
`_require_naive` a `require_naive_datetime` (mismo cuerpo, mismo `ValueError`).

## 2. Verificación de fronteras hexagonales

```bash
uv run ruff check src/
```

No debe reportar violaciones `TID251`/`TID252`. H003 no introduce ningún import nuevo prohibido
por capa (no se añade ninguna dependencia nueva a `pyproject.toml`), así que no hace falta tocar
ningún `ruff.toml` existente.

## 3. Validación manual por HTTP

```bash
uv run uvicorn src.adapters.inbound.api.app:app --reload
```

En otra terminal:

```bash
# Registro sin incidente equivalente abierto -> 201, is_duplicate: false
curl -X POST "http://127.0.0.1:8000/api/v1/incidents" \
  -H "Content-Type: application/json" \
  -d '{"title": "Caída del gateway de pagos", "raw_text": "El gateway de pagos devuelve HTTP 502 para todos los comercios desde hace 10 minutos."}'

# Registro de un incidente equivalente (mismo componente/síntoma) -> 201, is_duplicate: true
curl -X POST "http://127.0.0.1:8000/api/v1/incidents" \
  -H "Content-Type: application/json" \
  -d '{"title": "Otro reporte del mismo gateway", "raw_text": "El gateway de pagos sigue devolviendo HTTP 502 a todos los comercios."}'

# Reintento con el mismo incident_id -> 409 Conflict
curl -X POST "http://127.0.0.1:8000/api/v1/incidents" \
  -H "Content-Type: application/json" \
  -d '{"title": "x", "raw_text": "y", "incident_id": "INC-FIXED01"}'
curl -X POST "http://127.0.0.1:8000/api/v1/incidents" \
  -H "Content-Type: application/json" \
  -d '{"title": "x", "raw_text": "y", "incident_id": "INC-FIXED01"}'

# Auditoría de SLA con instante de referencia explícito -> 200
curl "http://127.0.0.1:8000/api/v1/incidents/INC-FIXED01/sla?reference_time=2026-11-24T12:00:00"

# Incidente inexistente -> 404
curl "http://127.0.0.1:8000/api/v1/incidents/INC-NO-EXISTE/sla"
```

Resultado esperado: `201 Created` en los dos primeros registros (el segundo con
`is_duplicate: true` y `duplicate_of` listando el primero, si comparten
`duplicate_group_key`); `409 Conflict` en el cuarto comando (mismo `incident_id` que el tercero);
`200 OK` con el detalle de SLA en el quinto; `404 Not Found` en el sexto. Ver cuerpos exactos en
`../contracts/incident-lifecycle-sla.md`.

## 4. Validación manual por CLI (paridad con el paso 3)

```bash
uv run python -m src.adapters.inbound.cli create \
  --title "Caída del gateway de pagos" \
  --raw-text "El gateway de pagos devuelve HTTP 502 para todos los comercios desde hace 10 minutos."

uv run python -m src.adapters.inbound.cli create \
  --title "x" --raw-text "y" --incident-id INC-FIXED01
uv run python -m src.adapters.inbound.cli create \
  --title "x" --raw-text "y" --incident-id INC-FIXED01   # debe terminar en código 1 (409 equivalente)

uv run python -m src.adapters.inbound.cli sla --incident-id INC-FIXED01 --reference-time 2026-11-24T12:00:00
uv run python -m src.adapters.inbound.cli sla --incident-id INC-NO-EXISTE   # debe terminar en código 1 (404 equivalente)
```

Resultado esperado: mismo contenido de negocio que el paso 3 para la misma combinación de
entradas, código de salida `0` en los registros/consultas válidos y `1` en el conflicto de
identificador y en el incidente inexistente (ver `../contracts/incident-lifecycle-sla.md` §4,
paridad HTTP/CLI).

Nota: la API (paso 3) y la CLI (paso 4) corren en procesos separados; con el `DATABASE_URL` por
defecto (`:memory:`), cada proceso tiene su propio dataset efímero, así que para verificar
paridad real sobre el **mismo** incidente hay que fijar `DATABASE_URL` a un archivo compartido
antes de levantar ambos procesos, igual que en H002:

```bash
# PowerShell
$env:DATABASE_URL = "sqlite:///./tmp-h003.db"
```

Las pruebas automatizadas del paso 1 no necesitan este paso: inyectan el mismo repositorio en
memoria a la API y a la CLI dentro del mismo proceso de test (`tests/conftest.py`, fixtures
`incident_service`/`summary_api_client`/`summary_cli_app`, reutilizadas sin cambios — ver
`../research.md`, Decisión 8).

## 5. Qué NO verifica este quickstart

- Fusión automática de duplicados, escalamiento o reasignación automática, edición del historial
  de incidentes, ni políticas de retención/archivado: fuera de alcance de H003 (`../spec.md`,
  Supuestos).
- `check_health` del puerto de salida: sin caso de uso propio en H003 (preparación H004).
- El benchmark pedagógico de `src/incident_repository.py`: no se modifica ni se reemplaza por este
  hito.
