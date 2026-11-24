# Fase 1 — Modelo de datos: Persistencia relacional dedicada y runtime en contenedores (H004)

## Puerto de salida (`src/application/ports.py`)

### `IncidentRepositoryPort` (`typing.Protocol`, `@runtime_checkable`)

Sin cambios de firma (el método ya existe desde H002, sin implementación real hasta
ahora):

| Método | Firma | Uso en H004 |
|---|---|---|
| `check_health` | `() -> bool` | **Implementado por primera vez en ambos adaptadores concretos.** `True` = la consulta de verificación tuvo éxito; `False` = falló (sin distinguir el motivo exacto, ver `research.md`, Decisión 1). |
| `save_incident`, `get_incident`, `find_open_duplicates`, `list_active_incidents` | Sin cambios | `PostgresIncidentRepository` los implementa con el mismo contrato observable que `SQLiteIncidentRepository` (FR-006); ningún escenario de H004 los ejercita directamente, pero deben seguir cumpliendo el puerto (ver Decisión 4 de `research.md`). |

## Tipos de aplicación (`src/application/services.py`)

### `IncidentService.check_health() -> bool`

| Aspecto | Valor |
|---|---|
| Entrada | Ninguna (sin parámetros; no depende de `reference_time` ni de ningún estado). |
| Salida | `bool` — delega exactamente en `self._repository.check_health()`, sin transformar el resultado. |
| Reglas de negocio | Ninguna; es orquestación pura hacia el puerto, igual en espíritu a como `get_active_incidents_summary` orquesta `list_active_incidents` sin reimplementarlo. |
| Determinismo | No lee el reloj del sistema ni ningún otro estado externo distinto del repositorio inyectado. |

## Esquema de datos por motor

### SQLite (`src/adapters/outbound/sqlite_repository.py`) — sin cambios de esquema

`check_health()` ya implementado (H002/H003, preparación): `SELECT 1` vía `self.conn`,
captura `sqlite3.Error` y devuelve `False`. H004 no modifica este adaptador; solo deja de
ser el único adaptador de salida existente.

### PostgreSQL (`src/adapters/outbound/postgres_repository.py`) — nuevo

```sql
CREATE TABLE IF NOT EXISTS sla_policies (
    severity TEXT PRIMARY KEY,
    max_resolution_minutes INTEGER NOT NULL,
    operates_24x7 BOOLEAN NOT NULL
);

CREATE TABLE IF NOT EXISTS incidents (
    incident_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    component TEXT NOT NULL,
    severity TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,       -- ISO 8601 como texto (ADR-004, Decisión 3); no TIMESTAMP
    resolved_at TEXT,               -- ISO 8601 como texto, nullable
    symptom_category TEXT
);

CREATE INDEX IF NOT EXISTS idx_incidents_component_status
ON incidents (component, status);   -- mismo índice de ADR-001, replicado por motor
```

| Método | Sentencia SQL (parametrizada con `%s`) | Equivalente en SQLite |
|---|---|---|
| `save_incident` | `INSERT INTO incidents (...) VALUES (%s, ...) ON CONFLICT (incident_id) DO UPDATE SET title = EXCLUDED.title, component = EXCLUDED.component, severity = EXCLUDED.severity, status = EXCLUDED.status, created_at = EXCLUDED.created_at, resolved_at = EXCLUDED.resolved_at, symptom_category = EXCLUDED.symptom_category` | `INSERT OR REPLACE INTO incidents (...) VALUES (?, ...)` |
| `get_incident` | `SELECT * FROM incidents WHERE incident_id = %s` | `SELECT * FROM incidents WHERE incident_id = ?` |
| `find_open_duplicates` | `SELECT * FROM incidents WHERE component = %s AND symptom_category = %s AND status IN (%s, %s) ORDER BY incident_id` | Mismo predicado con `?` |
| `list_active_incidents` | `SELECT * FROM incidents WHERE [component = %s AND] status IN (%s, %s) ORDER BY incident_id` | Mismo predicado con `?` |
| `check_health` | `SELECT 1` (captura `psycopg.Error` → `False`) | `SELECT 1` (captura `sqlite3.Error` → `False`) |

Mapeo de fila → `Incident`: idéntico a `SQLiteIncidentRepository._row_to_incident`, leyendo
por clave de diccionario (`row_factory=psycopg.rows.dict_row`) en vez de `sqlite3.Row`
(ver `research.md`, Decisión 1).

## Configuración de motor de persistencia (`src/adapters/outbound/factory.py`)

| Función | Firma | Responsabilidad |
|---|---|---|
| `create_repository` | `(database_url: str) -> IncidentRepositoryPort` | Función pura: decide el adaptador por el esquema de `database_url`. `postgresql://...` → `PostgresIncidentRepository(dsn=database_url)`; `sqlite:///...` → `SQLiteIncidentRepository(db_path=...)`; cualquier otro esquema → `ValueError` explícito (FR-007). |
| `get_incident_repository` | `() -> IncidentRepositoryPort` | Sin cambio de firma; ahora delega en `create_repository(os.environ.get("DATABASE_URL", _DEFAULT_DATABASE_URL))`. Sigue siendo el único punto que los adaptadores de entrada (`api/app.py`, `cli.py`) invocan (FR-005, Constitución Principio II). |

## Contrato observable de `GET /health` / comando `health`

Ver `contracts/health-check.md` para el detalle de ambas interfaces.

| Campo | Tipo | Valores posibles |
|---|---|---|
| `status` | `str` | `"ok"` \| `"error"` |
| `database` | `str` | `"connected"` \| `"unavailable"` |

Invariante: `status == "ok" ⟺ database == "connected"` (nunca una combinación mixta);
corresponde 1:1 al resultado booleano de `IncidentService.check_health()`.

## Stack de contenedores (`docker-compose.yml`) — no es una entidad de datos

No introduce ninguna entidad persistida nueva; es la topología de despliegue de las
entidades anteriores (ver `contracts/health-check.md` y `quickstart.md` para su
comportamiento observable).
