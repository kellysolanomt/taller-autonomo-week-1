# Quickstart — Validación de H004 (Persistencia relacional dedicada y runtime en contenedores)

Todos los comandos se ejecutan desde `week-1/starter-project/` (ver `AGENTS.md`).

## Prerrequisitos

```bash
uv sync
```

Para la sección 3 (validación con contenedores): Docker y Docker Compose instalados.

## 1. Verificación automatizada (primaria, sin Docker)

```bash
uv run pytest -v
```

Debe incluir, además de las pruebas de H001/H002 ya existentes, las funciones
`test_bdd_*` de `tests/test_spec_004_runtime_health.py`: éxito y fallo de `GET /health`
(con un doble de prueba para la base de datos inalcanzable, sin red real), paridad con el
comando CLI `health`, y la conformidad estructural de `create_repository` con
`IncidentRepositoryPort` para ambos esquemas de `DATABASE_URL` (ver `../research.md`,
Decisión 4 — esta prueba no requiere un servidor PostgreSQL en ejecución).

```bash
uv run python -m src.adapters.inbound.cli health
```

Con `DATABASE_URL` sin definir (SQLite en memoria por defecto), debe imprimir
`{"status": "ok", "database": "connected"}` y terminar con código de salida `0`.

## 2. Verificación de fronteras hexagonales

```bash
uv run ruff check src/
```

No debe reportar violaciones `TID251`/`TID252`. H004 añade `psycopg` como dependencia
nueva: `src/application/ruff.toml` y `src/adapters/inbound/ruff.toml` deben extender su
`banned-api` para prohibir `psycopg` y el import directo de
`src.adapters.outbound.postgres_repository`, igual que ya hacen con `sqlite3`/
`sqlite_repository` (ver `../plan.md`, Constitution Check, fila II).

## 3. Validación manual contra SQLite (sin contenedores)

```bash
curl -i http://127.0.0.1:8000/health
```

Con el servidor levantado localmente (`uv run uvicorn
src.adapters.inbound.api.app:app --reload`) y sin `DATABASE_URL` definida, debe responder
`200 OK` con `{"status": "ok", "database": "connected"}` (FR-008: SQLite en memoria, sin
contenedores).

## 4. Validación manual contra PostgreSQL en contenedores

```bash
docker compose up --build
```

Resultado esperado:

1. El servicio `db` (`postgres:16-alpine`) arranca y su `healthcheck` (`pg_isready`)
   reporta éxito antes de que `api` inicie su proceso (FR-011).
2. El servicio `api` arranca contra `DATABASE_URL=postgresql://...@db:5432/...` y su
   propio `healthcheck` (`GET /health`) reporta éxito una vez que puede alcanzar `db`.

En otra terminal, con el stack en ejecución:

```bash
curl -i http://127.0.0.1:8000/health
```

Debe responder `200 OK` con `{"status": "ok", "database": "connected"}`, esta vez
respaldado por PostgreSQL, no por SQLite (FR-005/FR-006: mismo contrato, motor distinto).

### 4.1 Paridad de resultado de negocio entre motores (FR-006, RNF-002, SC-002)

Como el registro de incidentes vía CLI/HTTP es alcance de H003 (aún no implementado), esta
verificación compara directamente el puerto de persistencia con el mismo incidente. Con el
stack de `docker compose up` ya saludable:

```bash
uv run python -c "
from datetime import datetime
from src.adapters.outbound.factory import create_repository
from src.domain.models import Incident

incident = Incident(
    incident_id='INC-PARIDAD-001', title='Prueba de paridad', component='payments-gateway',
    severity='P2', status='OPEN', created_at=datetime(2026, 11, 24, 9, 0, 0),
)
for url in ('sqlite:///./tmp-paridad.db', 'postgresql://incidentops:incidentops@localhost:5432/incidentops'):
    repo = create_repository(url)
    repo.save_incident(incident)
    print(url, '->', repo.get_incident('INC-PARIDAD-001'))
"
```

Ambas líneas impresas DEBEN mostrar el mismo `Incident` (mismos valores en todos los campos),
confirmando que el resultado de negocio es idéntico sin importar el motor activo.

```bash
docker compose stop db
curl -i http://127.0.0.1:8000/health
```

Debe responder `503 Service Unavailable` con `{"status": "error", "database":
"unavailable"}` (Escenario de Aceptación 3, Historia 1) — este es el único paso de esta
guía que requiere detener deliberadamente la base de datos para observar el fallo real.

```bash
docker compose start db
docker compose restart db
```

Tras el reinicio de `db`, los incidentes guardados previamente DEBEN seguir disponibles
(RNF-006, volumen persistente) — verificable repitiendo una consulta de triaje o resumen
ya usada en H001/H002 contra el mismo `incident_id`.

```bash
docker compose down
```

## 5. Referencias de contrato

- Forma exacta de `GET /health` y del comando `health`: `contracts/health-check.md`.
- Esquema SQL de PostgreSQL y mapeo de `create_repository`: `data-model.md`.
- Decisiones de diseño (driver, `ON CONFLICT`, estrategia de prueba sin PostgreSQL real,
  imagen de contenedor, credenciales de desarrollo): `research.md`.
