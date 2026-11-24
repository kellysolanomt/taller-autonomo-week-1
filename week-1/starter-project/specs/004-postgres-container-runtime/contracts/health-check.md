# Contrato de interfaz: Chequeo de salud operativa (H004)

Referencia de negocio: `../spec.md` (Historia de Usuario 1). Referencia de diseño:
`../data-model.md`, `../research.md`.

## 1. Chequeo de salud — `GET /health`

### 1.1 Solicitud

```
GET /health
```

Sin cuerpo, sin parámetros, sin autenticación (igual que el resto de interfaces del
sistema en este corte — ver Supuestos de `spec.md`).

### 1.2 Respuesta exitosa — `200 OK`

```json
{
  "status": "ok",
  "database": "connected"
}
```

Se produce cuando `IncidentService.check_health()` devuelve `True`, es decir, cuando la
consulta real contra el motor de persistencia activo (`SELECT 1` o equivalente) tuvo
éxito (FR-002, FR-003).

### 1.3 Respuesta de fallo — `503 Service Unavailable`

```json
{
  "status": "error",
  "database": "unavailable"
}
```

Se produce cuando `IncidentService.check_health()` devuelve `False` (FR-004). A
diferencia de los errores `4xx` de H001-H003, este cuerpo **no** usa la forma
`{"error": "<mensaje>"}`: es un resultado de monitoreo válido, no un error de solicitud
mal formada, y su forma (`status`/`database`) está fijada explícitamente por `spec.md`.

### 1.4 Invariantes

- `status == "ok" ⟺ database == "connected"`; nunca una combinación mixta.
- Idempotente y de solo lectura: invocaciones repetidas sin cambios en la disponibilidad
  de la base de datos devuelven el mismo resultado (Escenario de Aceptación 5, Historia 1).
- Nunca cachea un resultado previo: cada invocación ejecuta la consulta real de nuevo
  (RNF-003).

## 2. Chequeo de salud — comando CLI `health`

### 2.1 Invocación

```
uv run python -m src.adapters.inbound.cli health
```

Sin argumentos ni opciones.

### 2.2 Salida exitosa

```json
{"status": "ok", "database": "connected"}
```

Impresa en stdout; código de salida `0`.

### 2.3 Salida de fallo

```json
{"status": "error", "database": "unavailable"}
```

Impresa en stdout (no en stderr: no es un error de validación de una solicitud, es un
resultado de monitoreo); código de salida `1`, para que un script u orquestador externo
pueda detectar el fallo por el código de salida sin tener que parsear el JSON (Supuestos
de `spec.md`: mismo patrón que el resto de la CLI usa el código de salida para señalar
éxito/fallo).

## 3. Chequeos de salud de la topología de contenedores (`docker-compose.yml`)

No son una interfaz adicional del servicio; son la forma en que Docker Compose consume
las dos interfaces anteriores y el chequeo nativo de PostgreSQL:

| Servicio | Mecanismo de chequeo | Consume |
|---|---|---|
| `db` | `pg_isready -U <usuario> -d <base>` | Nativo de la imagen `postgres:16-alpine`; no pasa por la API. |
| `api` | Petición HTTP a `GET /health` (sin `curl`; ver `../research.md`, Decisión 6) | La sección 1 de este contrato, sin duplicar su lógica. |

`api` declara `depends_on: db: condition: service_healthy` (FR-011): su proceso no
arranca hasta que el chequeo de `db` reporta éxito.
