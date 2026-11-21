# Especificación 001 — Endpoint de triaje HTTP y CLI (H001)

- **Estado**: Aprobada para implementación
- **Fecha**: 2026-11-21
- **Hito**: H001 — Triaje multi-interfaz
- **Ámbito**: `week-1/starter-project/`
- **Referencias**: `docs/constitution.md`, `docs/adr/003-arquitectura-hexagonal.md`, `docs/ROADMAP.md`

## 1. Objetivo

Exponer el motor determinista de triaje como servicio HTTP para el frontend y como comando CLI para soporte, sin persistencia y sin duplicar la lógica de negocio. Ambas interfaces invocan el mismo caso de uso: `IncidentService.triage_incident`.

## 2. Decisiones de alcance

- Operación **stateless**: no se guardan reportes, resultados ni historial.
- Sin puertos de salida ni repositorio en H001.
- Sin procesamiento por lote, sin autenticación y sin adaptador MCP.
- El motor de triaje **no se mueve**: `src/triage_rules.py` y `src/models.py` permanecen en su ubicación actual. La capa de aplicación los importa; no se reimplementan reglas.
- Se actualiza `docs/ROADMAP.md` para que H001 refleje este contrato.

## 3. Arquitectura

Dirección de dependencias: adaptadores → aplicación → dominio/motor.

- `src/application/ports.py`: puerto de entrada `TriageUseCase` con `typing.Protocol`.
- `src/application/incident_service.py`: `IncidentService.triage_incident(incident_id: str, raw_text: str) -> TriageResult`. Recibe datos ya validados y delega en `classify_incident_report`.
- `src/adapters/inbound/schemas.py`: esquema Pydantic v2 compartido por HTTP y CLI.
- `src/adapters/inbound/http.py`: aplicación FastAPI (`app`).
- `src/adapters/inbound/cli.py`: aplicación Typer (`app`) con el subcomando `triage`.
- `src/domain/` no se introduce en H001; la cláusula transitoria 3.5 de la Constitución ampara el uso del motor actual desde la aplicación.

## 4. Contrato HTTP

### 4.1 Solicitud

```http
POST /api/v1/incidents/triage
Content-Type: application/json
```

```json
{
  "incident_id": "INC-1001",
  "raw_text": "URGENTE: El gateway de pagos devuelve HTTP 502 Bad Gateway..."
}
```

- Ambos campos son obligatorios y de tipo `string`.
- Campos desconocidos se rechazan (`extra="forbid"`).

### 4.2 Respuesta exitosa

`200 OK` con todos los campos de `TriageResult`, en objeto plano y `snake_case`:

```json
{
  "incident_id": "INC-1001",
  "severity": "P0",
  "component": "payments-gateway",
  "rationale": "Síntoma 'outage' con alcance 'global' en payments-gateway -> P0; se enruta a Backend-Core.",
  "recommended_team": "Backend-Core",
  "duplicate_group_key": "payments-gateway:outage",
  "symptom_category": "outage",
  "impact_scope": "global",
  "consistency_ratio": 1.0
}
```

- Los enums se serializan como string (`"P0"`, `"Backend-Core"`).
- `rationale` es informativo; el frontend no debe usarlo para lógica.
- `consistency_ratio` se expone tal como lo produce el motor (hoy siempre `1.0`).

### 4.3 Errores

Formato único:

```json
{
  "error": {
    "code": "EMPTY_FIELD",
    "message": "raw_text no puede estar vacío"
  }
}
```

| Código | HTTP | Causa |
|---|---|---|
| `EMPTY_FIELD` | `422` | Campo vacío o solo espacios tras `.strip()` |
| `FIELD_TOO_LONG` | `422` | `raw_text` > 4000 o `incident_id` > 100 |
| `VALIDATION_ERROR` | `422` | Campo faltante, tipo incorrecto o campo extra |
| `INTERNAL_ERROR` | `500` | Fallo inesperado |

### 4.4 Operación

- Sin autenticación en H001 (servicio interno).
- CORS configurable por `INCIDENTOPS_CORS_ORIGINS` (lista separada por comas); valor por defecto `*` en H001.
- OpenAPI y Swagger expuestos en `/openapi.json` y `/docs`.

## 5. Contrato CLI

```powershell
uv run python -m src.adapters.inbound.cli triage --incident-id INC-1001 --raw-text "..."
```

- Solo se admiten `--incident-id` y `--raw-text`; no hay lectura por stdin ni `--file` en H001.
- Éxito: JSON compacto UTF-8 (`ensure_ascii=False`) del mismo objeto de respuesta HTTP por `stdout`; código de salida `0`.
- Entrada vacía o solo espacios: JSON de error por `stderr`; código de salida `1`.
- Error de validación de tipo o longitud: JSON de error por `stderr`; código de salida `1`.
- Opción requerida ausente: se conserva el código `2` nativo de Typer/Click.
- La CLI usa el mismo `TriageRequest` y el mismo `IncidentService` que HTTP.

## 6. Validación

La validación tiene dos capas complementarias; un linter estático **no** puede validar payloads en runtime.

### 6.1 Runtime — Pydantic v2

`TriageRequest` en `src/adapters/inbound/schemas.py`:

- `incident_id`: `str`, `.strip()` no vacío, máximo 100; se conserva recortado.
- `raw_text`: `str`, `.strip()` no vacío, máximo 4000; se conserva **original** para clasificar.
- `extra="forbid"`.
- Errores emitidos con `PydanticCustomError`: `empty_field`, `field_too_long`, `validation_error`.
- HTTP traduce estos errores al envelope del punto 4.3; CLI los traduce a JSON de error con exit `1`.

`IncidentService` no repite validaciones: recibe valores ya validados. El dominio no conoce Pydantic.

### 6.2 Estática — Ruff

- Dependencia de desarrollo `ruff`.
- Configuración en `pyproject.toml`: `target-version = "py310"`, `line-length = 100`, reglas `E`, `F`, `I`, `UP`, `B`.
- Se aplica al código nuevo (`src/application/`, `src/adapters/`, `tests/`); no se reformatean los módulos existentes.
- Comandos:

```powershell
uv run ruff check src/application src/adapters tests
uv run ruff format --check src/application src/adapters tests
```

## 7. Reglas de dominio aplicables

- El triaje deriva severidad, componente, equipo y clave de duplicado de síntoma + alcance; nunca de palabras de urgencia como "urgente" o "hoy".
- Texto normalizado a minúsculas y sin tildes.
- `data_exposure` es siempre P0; alcances `individual` y `staging` topan en P2 para el resto.
- Equipos válidos: `Backend-Core`, `Platform-SRE`, `Data-DBA`, `Security-IAM`.
- `duplicate_group_key` actual: `<component>:<symptom_category>`.
- Determinismo: mismas entradas producen la misma salida; no se lee el reloj del sistema.

## 8. Escenarios BDD

### Escenario 1: Caída crítica HTTP 502 en pasarela de pagos

```gherkin
Given un reporte con incident_id "INC-1001" y raw_text que describe
  "HTTP 502 Bad Gateway" en el gateway de pagos con alcance global
When se envía POST /api/v1/incidents/triage con ese reporte
Then la respuesta es 200 OK
And severity es "P0"
And component es "payments-gateway"
And recommended_team es "Backend-Core"
And duplicate_group_key es "payments-gateway:outage"
```

> El valor se mantiene como `payments-gateway:outage` porque el contrato del
> motor es `<component>:<symptom_category>` (Constitución 1.8) y el motor no se
> mueve ni se modifica en H001. El valor `payments-gateway:http-502-outage`
> queda descartado: exigiría cambiar la regla de dominio (ADR) o mapear la
> salida en el adaptador, prohibido por la Constitución 1.1/2.5.

### Escenario 2: Cuenta individual bloqueada mencionando "hoy"

```gherkin
Given un reporte con incident_id "INC-1002" y raw_text que indica que la
  cuenta de un solo usuario está bloqueada y que se necesita acceder "hoy"
When se envía POST /api/v1/incidents/triage con ese reporte
Then la respuesta es 200 OK
And severity es "P2"
And recommended_team es "Security-IAM"
And severity no es "P0" (la palabra "hoy" no produce falso positivo)
```

### Escenario 3: Entradas vacías o con solo espacios

```gherkin
Given una solicitud con raw_text " " o con incident_id ""
When se envía POST /api/v1/incidents/triage
Then la respuesta es 422 Unprocessable Entity
And el cuerpo contiene error.code "EMPTY_FIELD"
```

### Escenario 4: Paridad en CLI

```gherkin
Given el comando
  triage --incident-id INC-1001 --raw-text "URGENTE: El gateway de pagos devuelve HTTP 502..."
When se ejecuta con uv run python -m src.adapters.inbound.cli
Then la salida estándar contiene JSON válido
And severity es "P0"
And recommended_team es "Backend-Core"
And el código de salida es 0
```

## 9. Casos borde y criterios de aceptación adicionales

| Caso | Entrada | Resultado esperado |
|---|---|---|
| Fuga de datos entre tenants | `INC-1007` | `P0` aunque el alcance sea individual |
| Certificado en staging | `INC-1010` | `P3`, `Platform-SRE` |
| Latencia con alcance global | `INC-1003` | `P2` |
| Solo palabras de urgencia | `raw_text` con "urgente"/"hoy" sin síntoma | No eleva la severidad |
| `raw_text` vacío | `""` | `422 EMPTY_FIELD` |
| `raw_text` solo espacios | `"   "` | `422 EMPTY_FIELD` |
| `incident_id` vacío | `""` | `422 EMPTY_FIELD` |
| `incident_id` solo espacios | `"   "` | `422 EMPTY_FIELD` |
| `raw_text` > 4000 | Texto largo | `422 FIELD_TOO_LONG` |
| `incident_id` > 100 | Texto largo | `422 FIELD_TOO_LONG` |
| Campo faltante | Sin `raw_text` | `422 VALIDATION_ERROR` |
| Tipo incorrecto | `raw_text: 123` | `422 VALIDATION_ERROR` |
| Campo extra | `{"foo": "bar"}` | `422 VALIDATION_ERROR` |
| Repetición idéntica | Dos solicitudes iguales | Misma respuesta; sin estado persistido |
| CLI con `raw_text` vacío | `--raw-text ""` | Error JSON en stderr; exit `1` |

## 10. Pruebas y verificación

Pruebas de aceptación con `pytest`, escenarios `Given/When/Then` en docstrings y `TestClient`/`CliRunner`:

```powershell
uv sync
uv run ruff check src/application src/adapters tests
uv run ruff format --check src/application src/adapters tests
uv run pytest -q
```

Ejecución manual:

```powershell
uv run uvicorn src.adapters.inbound.http:app --reload
uv run python -m src.adapters.inbound.cli triage --incident-id INC-1001 --raw-text "..."
```

## 11. Archivos previstos

Crear:

- `src/application/__init__.py`
- `src/application/ports.py`
- `src/application/incident_service.py`
- `src/adapters/__init__.py`
- `src/adapters/inbound/__init__.py`
- `src/adapters/inbound/schemas.py`
- `src/adapters/inbound/http.py`
- `src/adapters/inbound/cli.py`
- `tests/acceptance/test_h001_http.py`
- `tests/acceptance/test_h001_cli.py`

Modificar:

- `pyproject.toml`: `fastapi`, `uvicorn`, `pydantic`, `typer`; dev `pytest`, `httpx`, `ruff`; configuración de pytest y ruff.
- `docs/ROADMAP.md`: H001 con REST + CLI stateless y referencia a esta especificación.
- `AGENTS.md`: comandos nuevos y corrección de la nota sobre FastAPI/pytest.

No modificar:

- `src/triage_rules.py`
- `src/models.py`
- `src/sla_calculator.py`
- `src/incident_repository.py`

## 12. Supuestos y puntos abiertos

1. **`duplicate_group_key` del Escenario 1**: resuelto a `payments-gateway:outage`, conforme a la Constitución 1.8 y a la decisión de no mover el motor.
2. **Exit `2` de Typer** para opciones requeridas ausentes: se mantiene el comportamiento nativo; no se fuerza a `1`.
3. **Alcance de Ruff**: solo código nuevo, para no introducir cambios ajenos en los módulos existentes.
4. **CORS por defecto `*`**: aceptable para H001 interno; debe restringirse antes de exponer el servicio fuera del entorno controlado.
