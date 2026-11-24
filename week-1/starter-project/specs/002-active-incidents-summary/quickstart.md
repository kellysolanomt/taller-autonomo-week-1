# Quickstart — Validación de H002 (Resumen de incidentes activos)

Todos los comandos se ejecutan desde `week-1/starter-project/` (ver `AGENTS.md`).

## Prerrequisitos

```bash
uv sync
```

## 1. Verificación automatizada (primaria)

```bash
uv run pytest -v
```

Debe incluir, además de los 4 escenarios de H001 (`tests/test_spec_001_triage.py`), las 8 funciones `test_bdd_*` de `tests/test_spec_002_summary.py` — una por cada Escenario de Aceptación de `../spec.md` (3 de la Historia 1, 2 de la Historia 2, 3 de la Historia 3). Ver el contrato esperado de cada función en `../contracts/incidents-summary.md` y el modelo de datos en `../data-model.md`.

```bash
uv run python -m src.domain.sla_calculator
```

No debe reportar fallos (sigue siendo la verificación de los casos borde de SLA ya fijados por ADR-002; H002 no les cambia ninguna regla).

## 2. Verificación de fronteras hexagonales (nueva en H002)

```bash
uv run ruff check src/
```

No debe reportar violaciones `TID251`/`TID252`. Un fallo aquí indica que una capa importó algo prohibido por `docs/constitution.md` Artículo 2 (ver skill `hexagonal-architecture` para el mapa de qué puede importar cada carpeta).

## 3. Validación manual por HTTP

```bash
uv run uvicorn src.adapters.inbound.api.app:app --reload
```

En otra terminal:

```bash
curl "http://127.0.0.1:8000/api/v1/incidents/summary"
curl "http://127.0.0.1:8000/api/v1/incidents/summary?component=payments-gateway"
curl "http://127.0.0.1:8000/api/v1/incidents/summary?reference_time=2026-11-23T12:00:00"
```

Resultado esperado: `200 OK` en los tres casos, incluso si algún filtro no coincide con ningún incidente activo (cuerpo con `total_active: 0`, nunca un error). Con la base de datos por defecto (`DATABASE_URL` sin definir → `sqlite:///:memory:`) y sin ningún incidente sembrado, los tres deben devolver `{"total_active": 0, "breached_count": 0, "incidents": []}`.

## 4. Validación manual por CLI (paridad con el paso 3)

```bash
uv run python -m src.adapters.inbound.cli summary
uv run python -m src.adapters.inbound.cli summary --component payments-gateway
uv run python -m src.adapters.inbound.cli summary --reference-time 2026-11-23T12:00:00
```

Resultado esperado: mismo contenido de negocio que el paso 3 para la misma combinación de filtros, código de salida `0` en los tres casos (ver `../contracts/incidents-summary.md` §3, paridad HTTP/CLI).

Nota: la API (paso 3) y la CLI (paso 4) corren en procesos separados; con el `DATABASE_URL` por defecto (`:memory:`), cada proceso tiene su propio dataset efímero vacío, por lo que ambos coinciden trivialmente en "resumen vacío". Para validar paridad con datos reales en esta prueba manual, fijar `DATABASE_URL` a un archivo compartido, p. ej.:

```bash
# PowerShell
$env:DATABASE_URL = "sqlite:///./tmp-h002.db"
```

y repetir los pasos 3 y 4 apuntando al mismo archivo desde ambos procesos. Las pruebas automatizadas del paso 1 no necesitan este paso: inyectan el mismo repositorio en memoria a la API y a la CLI dentro del mismo proceso de test (ver `../research.md`, Decisión 6).

## 5. Qué NO verifica este quickstart

- Paginación, exportación de reportes o notificaciones automáticas: fuera de alcance de H002 (`spec.md`, Supuestos).
- `find_open_duplicates` y `check_health` del puerto: no tienen caso de uso propio en H002 (preparación para H003/H004, ver `../research.md`, Decisiones 4 y 5); su verificación en este hito se limita a la comprobación de cumplimiento del `Protocol` en `tests/test_spec_002_summary.py`, no a un escenario de negocio.
- El benchmark pedagógico de `src/incident_repository.py` (`uv run python -m src.incident_repository`): sigue siendo válido tal cual, no se modifica ni se reemplaza por este hito.
