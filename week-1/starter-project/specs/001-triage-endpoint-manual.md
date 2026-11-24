# Especificación 001 — Endpoint de triaje HTTP y CLI (H001)

- **Estado**: Aprobada para implementación (con enmienda, ver abajo)
- **Fecha**: 2026-11-21
- **Hito**: H001 — Triaje multi-interfaz
- **Ámbito**: `week-1/starter-project/`
- **Referencias**: `docs/constitution.md`, `docs/adr/003-arquitectura-hexagonal.md`, `docs/ROADMAP.md`

> **Enmienda (2026-11-21):** se adelanta a este corte de H001 la migración del
> motor de triaje/SLA a `src/domain/` (originalmente prevista para un hito
> posterior bajo la cláusula transitoria 3.5), y se ajustan en consecuencia
> las rutas de archivo de §2, §3 y §11. Además, esta implementación simplifica
> el contrato de errores a un envelope plano `{"error": "<mensaje>"}` (sin la
> taxonomía de códigos `EMPTY_FIELD`/`FIELD_TOO_LONG`/`VALIDATION_ERROR` de la
> versión original de §4.3/§6/§9) y no incorpora Ruff ni cambios a
> `docs/ROADMAP.md` en este cut. Decisión del equipo tras revisar este primer
> corte; sustituye las rutas de archivo, el contrato de errores y el alcance
> de pruebas estáticas de la versión original de este documento. Los
> escenarios BDD, el contrato de severidad/equipo/componente y las reglas de
> dominio (§7) no cambian.

## 1. Objetivo

Exponer el motor determinista de triaje como servicio HTTP para el frontend y como comando CLI para soporte, sin persistencia y sin duplicar la lógica de negocio. Ambas interfaces invocan el mismo caso de uso: `IncidentService.triage_incident`.

## 2. Decisiones de alcance

- Operación **stateless**: no se guardan reportes, resultados ni historial.
- Sin puertos de salida ni repositorio en H001.
- Sin procesamiento por lote, sin autenticación y sin adaptador MCP.
- El motor de triaje **se migra** a `src/domain/` (`models.py`, `triage_rules.py`, `sla_calculator.py`) como parte de este corte (ver enmienda). La capa de aplicación los importa; no se reimplementan reglas.
- `docs/ROADMAP.md` no se modifica en este corte (fuera de alcance de esta implementación).

## 3. Arquitectura

Dirección de dependencias: adaptadores → aplicación → dominio/motor.

- `src/domain/models.py`, `src/domain/triage_rules.py`, `src/domain/sla_calculator.py`: núcleo puro migrado en este corte.
- `src/application/services.py`: `ValidationError` y `IncidentService.triage_incident(incident_id: str, raw_text: str) -> TriageResult`. Valida la forma de la solicitud (campos no vacíos, longitud máxima) y delega en `classify_incident_report`.
- `src/adapters/inbound/api/schemas.py`: esquemas Pydantic v2 de entrada/salida del adaptador REST.
- `src/adapters/inbound/api/app.py`: aplicación FastAPI, expuesta como `create_app()` y como `app` a nivel de módulo.
- `src/adapters/inbound/cli.py`: aplicación Typer (`app`) con el subcomando `triage`.

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
- Campos desconocidos **no** se rechazan en este corte (`TriageRequestSchema` no fija `extra="forbid"`; ver §9).

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

Formato único, plano (sin taxonomía de códigos en este corte — ver enmienda):

```json
{
  "error": "raw_text no puede estar vacío."
}
```

| HTTP | Causa |
|---|---|
| `422` | Campo vacío (o solo espacios) tras `.strip()`, o fuera de longitud máxima (`incident_id` > 100, `raw_text` > 4000) |
| `500` | Fallo inesperado |

> Campo faltante o de tipo incorrecto en el JSON también responde `422`, pero
> con el cuerpo nativo de FastAPI/Pydantic (`{"detail": [...]}`), no con el
> envelope `{"error": "..."}` anterior — esa validación ocurre antes de llegar
> a `IncidentService` y no pasa por `ValidationError`.

### 4.4 Operación

- Sin autenticación en H001 (servicio interno).
- Sin configuración de CORS en este corte (ver enmienda); pendiente si el servicio se expone fuera del entorno controlado.
- OpenAPI y Swagger expuestos en `/openapi.json` y `/docs` (comportamiento por defecto de FastAPI).

## 5. Contrato CLI

```powershell
uv run python -m src.adapters.inbound.cli triage --incident-id INC-1001 --raw-text "..."
```

> La CLI expone `triage` como subcomando explícito (`typer.Typer()` con un
> `@app.callback()` de aplicación, para evitar que Typer colapse el único
> comando y omita el nombre del subcomando).

- Solo se admiten `--incident-id` y `--raw-text`; no hay lectura por stdin ni `--file` en H001.
- Éxito: JSON compacto UTF-8 (`ensure_ascii=False`) del mismo objeto de respuesta HTTP por `stdout`; código de salida `0`.
- Entrada vacía o solo espacios: JSON de error por `stderr`; código de salida `1`.
- Error de validación de tipo o longitud: JSON de error por `stderr`; código de salida `1`.
- Opción requerida ausente: se conserva el código `2` nativo de Typer/Click.
- La CLI invoca directamente el mismo `IncidentService.triage_incident` que usa el adaptador HTTP (sin pasar por `TriageRequestSchema`, que es específico del adaptador REST).

## 6. Validación

En este corte, la validación de forma de la solicitud vive en un único lugar
—`IncidentService.triage_incident` (`src/application/services.py`)— y la
comparten HTTP y CLI; no hay una capa Pydantic de validación de campos propia
del payload con códigos de error (ver enmienda).

- `incident_id`: no vacío tras `.strip()`, máximo 100 caracteres; se usa recortado.
- `raw_text`: no vacío tras `.strip()`, máximo 4000 caracteres; se usa **original** para clasificar.
- Cualquier violación lanza `ValidationError` (excepción de aplicación, no de Pydantic).
- HTTP traduce `ValidationError` al envelope plano del punto 4.3 (`422`); CLI la traduce a JSON de error por `stderr` con exit `1`.
- `src/adapters/inbound/api/schemas.py` sí usa Pydantic v2, pero solo para la forma del request/response HTTP (tipos de campo); no define reglas de longitud ni mensajes de error propios.
- El dominio no conoce Pydantic ni Typer.
- Ruff y su configuración en `pyproject.toml` **no se incorporan en este corte** (no estaban en el alcance pedido); queda como trabajo pendiente para un corte posterior.

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
> motor es `<component>:<symptom_category>` (Constitución 1.8); la migración
> de `src/triage_rules.py` a `src/domain/triage_rules.py` en este corte reubica
> el módulo pero no modifica sus reglas. El valor `payments-gateway:http-502-outage`
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
And el cuerpo contiene una clave "error" con un mensaje descriptivo
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
| `raw_text` vacío | `""` | `422`, `{"error": "..."}` |
| `raw_text` solo espacios | `"   "` | `422`, `{"error": "..."}` |
| `incident_id` vacío | `""` | `422`, `{"error": "..."}` |
| `incident_id` solo espacios | `"   "` | `422`, `{"error": "..."}` |
| `raw_text` > 4000 | Texto largo | `422`, `{"error": "..."}` |
| `incident_id` > 100 | Texto largo | `422`, `{"error": "..."}` |
| Campo faltante | Sin `raw_text` | `422` (error de validación de Pydantic, forma del payload) |
| Tipo incorrecto | `raw_text: 123` | `422` (error de validación de Pydantic, forma del payload) |
| Repetición idéntica | Dos solicitudes iguales | Misma respuesta; sin estado persistido |
| CLI con `raw_text` vacío | `--raw-text ""` | Error JSON en stderr; exit `1` |

> Nota: el rechazo de campos extra (`extra="forbid"`) no se implementó en este
> corte; `TriageRequestSchema` solo fija los tipos de `incident_id`/`raw_text`.

## 10. Pruebas y verificación

Pruebas de aceptación con `pytest`, escenarios `Given/When/Then` en docstrings y `TestClient`/`CliRunner`:

```powershell
uv sync
uv run pytest -v
```

Ejecución manual:

```powershell
uv run uvicorn src.adapters.inbound.api.app:app --reload
uv run python -m src.adapters.inbound.cli triage --incident-id INC-1001 --raw-text "..."
```

## 11. Archivos previstos

Crear:

- `src/domain/__init__.py`, `src/domain/models.py`, `src/domain/triage_rules.py`, `src/domain/sla_calculator.py`
- `src/application/__init__.py`, `src/application/services.py`
- `src/adapters/__init__.py`, `src/adapters/inbound/__init__.py`, `src/adapters/inbound/api/__init__.py`
- `src/adapters/inbound/api/schemas.py`, `src/adapters/inbound/api/app.py`
- `src/adapters/inbound/cli.py`
- `tests/conftest.py`, `tests/test_spec_001_triage.py`

Modificar:

- `pyproject.toml`: `fastapi`, `uvicorn`, `pydantic`, `typer`; dev `pytest`, `httpx`; configuración de pytest.
- `src/incident_repository.py`: imports actualizados a `src.domain.models` / `src.domain.sla_calculator` (corrige además un import roto preexistente).
- `AGENTS.md`: nueva estructura hexagonal, comandos nuevos y corrección de la nota sobre pytest.
- Esta especificación (enmienda registrada arriba).

Eliminar:

- `src/models.py` (migrado a `src/domain/models.py`, sin shim de compatibilidad).

No modificar:

- `src/context_audit.py`

No realizado en este corte (fuera de alcance pedido):

- `docs/ROADMAP.md`
- Ruff (dependencia y configuración)

## 12. Supuestos y puntos abiertos

1. **`duplicate_group_key` del Escenario 1**: resuelto a `payments-gateway:outage`, conforme a la Constitución 1.8; no cambia por la migración a `src/domain/`, que solo reubica el motor sin tocar sus reglas.
2. **Exit `2` de Typer** para opciones requeridas ausentes: se mantiene el comportamiento nativo; no se fuerza a `1`. (Para que `triage` exista como subcomando explícito en vez de colapsarse al único comando, el `Typer()` del CLI registra un `@app.callback()` de aplicación; ver §5.)
3. **Ruff y taxonomía de códigos de error**: no implementados en este corte (ver enmienda); quedan como trabajo pendiente para un hito posterior si se requiere paridad total con la especificación original.
4. **CORS por defecto `*`**: no implementado en este corte (no hay configuración CORS); si se expone el servicio fuera del entorno controlado, debe añadirse antes.
