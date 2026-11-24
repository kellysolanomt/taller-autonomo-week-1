# Fase 0 — Investigación: Ciclo de vida de incidentes, duplicados y SLA (H003)

Todas las incógnitas de negocio de `spec.md` ya quedaron resueltas en su sección `## Clarifications`
(sesión 2026-11-24). Las incógnitas de esta fase son exclusivamente técnicas: cómo materializar
H003 sobre la arquitectura hexagonal ya vigente (ADR-003, `src/application/ports.py`,
`src/adapters/outbound/sqlite_repository.py`) sin reabrir decisiones de negocio ni reimplementar
reglas ya fijadas en `src/domain/`.

## Decisión 1 — Normalización naive/aware: un único punto en `src/domain/sla_calculator.py`, reutilizado por `src/application/services.py`

**Decisión**: El chequeo "este datetime no debe traer `tzinfo`" sigue viviendo exclusivamente en
`src/domain/sla_calculator.py`, pero se promueve de función privada (`_require_naive`) a función
pública reutilizable: `require_naive_datetime(name: str, value: Optional[datetime]) -> None`
(mismo cuerpo, mismo `ValueError`, ningún cambio de comportamiento). `evaluate_sla_status` sigue
llamándola igual que hoy para `created_at`/`resolved_at`/`reference_time`. Además, se añade una
única función de parseo en `src/application/services.py` —
`parse_naive_local_datetime(label: str, raw_value: Optional[str]) -> Optional[datetime]`— que:
1. devuelve `None` si `raw_value` es `None` (el llamador decide el valor por defecto, ver Decisión 4);
2. intenta `datetime.fromisoformat(raw_value)`, capturando `ValueError` y relanzando
   `ValidationError(f"{label} no es una fecha-hora ISO 8601 válida: ...")`;
3. llama a `require_naive_datetime(label, value)` (el helper de dominio) y traduce su `ValueError`
   a `ValidationError` con el mismo mensaje, para que el adaptador solo tenga que capturar un único
   tipo de excepción de "forma de la solicitud".

`IncidentService.create_incident` y la resolución de `reference_time` para
`evaluate_incident_sla` usan **la misma** `parse_naive_local_datetime`; ningún adaptador
(FastAPI/Typer) reimplementa el parseo ISO 8601 ni el rechazo de `tzinfo` — ambos importan y
llaman la misma función de `src/application/services.py`, igual que ya hacen con
`IncidentService`.

**Rationale**: La Constitución (Principio I) exige una única fuente de verdad para las reglas de
dominio — el rechazo de `tzinfo` es una regla de dominio (`evaluate_sla_status` ya la aplica) y no
puede reimplementarse en la aplicación ni en los adaptadores; solo se *reutiliza* bajo un nombre
público. El parseo de una cadena ISO 8601 a `datetime` no es una regla de dominio (es forma de la
solicitud), así que vive en `src/application/services.py`, consistente con el patrón ya
establecido por `triage_incident` ("único lugar donde se valida la forma de esa solicitud" —
AGENTS.md). Centralizar el parseo evita que FastAPI y Typer produzcan mensajes o comportamientos
distintos ante el mismo `created_at`/`reference_time` malformado (FR-018), que es exactamente el
tipo de divergencia que el skill `hexagonal-architecture` prohíbe entre adaptadores primarios.

**Alternativas consideradas**:
- *Dejar `_require_naive` privada y duplicar un chequeo de `tzinfo` en la aplicación*: rechazada —
  reimplementaría una regla de dominio fuera de `src/domain/`, violando el Principio I literalmente.
- *Parsear la cadena ISO 8601 en cada adaptador de entrada (FastAPI/Typer) por separado*: rechazada
  — duplica lógica de traducción entre adaptadores primarios y arriesga mensajes/validaciones
  divergentes ante el mismo valor malformado, lo que el skill `hexagonal-architecture` señala
  explícitamente como prohibido.
- *Dejar que Pydantic (`datetime` como tipo de campo) y el tipo `datetime` de `typer.Option` hagan
  el parseo*: rechazada — ambos frameworks producen su **propio** cuerpo/código de error ante un
  valor inválido (FastAPI: `422` con cuerpo `{"detail": [...]}`; Typer/Click: código de salida `2`),
  violando FR-018/FR-019 (cuerpo siempre `{"error": ...}`, nunca el código del framework). Por eso
  los nuevos campos declaran tipo `Optional[str]` en los esquemas/opciones (ver Decisión 6).

## Decisión 2 — `find_open_duplicates` se re-indexa por `duplicate_group_key`, no por `(component, symptom_category)`

**Decisión**: La firma del puerto de salida cambia de
`find_open_duplicates(component: str, symptom_category: str) -> list[Incident]` (preparación sin
caso de uso, H002) a `find_open_duplicates(duplicate_group_key: str) -> list[Incident]` (con caso
de uso real en H003). `Incident` (dominio) gana el campo aditivo
`duplicate_group_key: Optional[str] = None`, persistido como columna propia en SQLite, con índice
compuesto `idx_incidents_dup_key` sobre `(duplicate_group_key, status)`. La búsqueda de duplicados
ocurre **antes** de guardar el incidente nuevo (ver Decisión 7), por lo que la exclusión del propio
`incident_id` recién creado (FR-003) es automática: ese identificador todavía no existe en la
tabla en el momento de la consulta, sin necesidad de un parámetro `exclude_incident_id`.

**Rationale**: H002 (Decisión 4 de su `research.md`) dejó explícitamente para H003 la decisión
entre consultar por `(component, symptom_category)` separados o por la clave ya combinada; ahora
que existe un caso de uso real y que el propio dominio ya materializa esa clave en
`TriageResult.duplicate_group_key`, persistirla como columna propia permite un índice directo
`(duplicate_group_key, status)` — una sola condición de igualdad en vez de dos — y evita que el
adaptador de salida tenga que conocer el formato `<component>:<symptom_category>` (esa
composición es responsabilidad exclusiva de `src/domain/triage_rules.py`). Es un cambio de firma
seguro: H002 nunca conectó este método a un caso de uso (solo verificaba cumplimiento del
`Protocol` en pruebas), así que no hay llamador existente que se rompa.

**Alternativas consideradas**:
- *Mantener `(component, symptom_category)` y añadir un índice sobre ambas columnas*: rechazada —
  obliga al llamador a conocer y pasar dos valores que el dominio ya combina en una sola clave;
  el índice de dos columnas no es más eficiente que uno sobre la columna combinada y filtra peor
  cuando `component`/`symptom_category` quedan nulos para incidentes antiguos sin triaje.
- *Calcular `duplicate_group_key` al vuelo en cada consulta (`component || ':' || symptom_category`
  en SQL)*: rechazada — reimplementaría en SQL una composición que ya es responsabilidad del
  dominio (Principio I), y no podría indexarse directamente sin una columna generada.

## Decisión 3 — Dos excepciones de aplicación nuevas, mapeadas 1:1 a códigos HTTP/CLI

**Decisión**: `src/application/services.py` añade dos excepciones, hermanas de `ValidationError`
y con el mismo rol ("forma o estado de la solicitud", nunca una regla de dominio nueva):

| Excepción | Se lanza cuando | HTTP | CLI |
|---|---|---|---|
| `ValidationError` (existente, reutilizada) | `title`/`raw_text` vacíos; `status` fuera del enum; `created_at`/`reference_time` malformado o con `tzinfo` | `422` | código `1` |
| `IncidentConflictError` (nueva) | `incident_id` indicado ya existe (`repository.get_incident` lo encuentra) | `409` | código `1` |
| `IncidentNotFoundError` (nueva, pedida explícitamente) | `evaluate_incident_sla` no encuentra el `incident_id` consultado | `404` | código `1` |

El `ValueError` que ya lanza `evaluate_sla_status` cuando `reference_time < created_at` (FR-009/
FR-017) **no** se envuelve en una excepción nueva: se deja propagar tal cual, igual que ya hace
hoy `GET /api/v1/incidents/summary` (H002) con el mismo `ValueError` de dominio. El adaptador de
entrada captura `(ValidationError, ValueError)` juntos para el `422` de la ruta de SLA, exactamente
el mismo patrón ya probado en `app.py`/`cli.py` para `summary`.

**Rationale**: FR-006/FR-010 exigen distinguir `409` (conflicto de identificador) y `404`
(incidente inexistente) de `422` (forma de la solicitud); una sola `ValidationError` no puede
expresar esa distinción sin que el adaptador inspeccione el mensaje (fragile). Dos excepciones
nuevas, de nombre explícito, permiten que cada adaptador las traduzca con un `except` dedicado,
igual que ya hace con `ValidationError` desde H001. No envolver el `ValueError` de
"referencia anterior a la apertura" evita reintroducir una regla de dominio (la comparación de
fechas) fuera de `src/domain/sla_calculator.py`: seguimos dejando que el dominio decida cuándo es
inválido, y la aplicación solo traduce el tipo de excepción al borde.

**Alternativas consideradas**:
- *Una sola `ValidationError` con subtipos o un código de error embebido en el mensaje*: rechazada
  — obliga a los adaptadores a parsear el mensaje para decidir el código HTTP, violando la
  separación de responsabilidades y arriesgando que REST y CLI interpreten el mensaje de forma
  distinta (rompe paridad, Artículo 2.2).
- *Envolver también el `ValueError` de "referencia anterior a creación" en una excepción de
  aplicación nueva*: rechazada — no aporta nada sobre el patrón ya vigente y probado en H002
  (`except ValueError` en la ruta de `summary`), y añadiría una capa de traducción sin beneficio.

## Decisión 4 — Reloj del sistema y valores por defecto de `created_at`/`reference_time`

**Decisión**: Igual patrón que H002 (su `research.md`, Decisión 3), extendido a los dos campos
nuevos. `IncidentService.create_incident` exige `created_at: datetime` como argumento obligatorio
(nunca `Optional`, nunca lee el reloj); `IncidentService.evaluate_incident_sla` exige
`reference_time: datetime` como argumento obligatorio, con la misma restricción. La ruta FastAPI y
el comando Typer son los únicos lugares que invocan `datetime.now()`, y solo cuando el campo
correspondiente llega como `None` (omitido por quien llama):

```text
raw_created_at: Optional[str]  (desde el cuerpo JSON / --created-at)
created_at = parse_naive_local_datetime("created_at", raw_created_at) if raw_created_at is not None else datetime.now()
```

y de forma simétrica para `reference_time` en la ruta/comando de SLA.

**Rationale**: El Principio I prohíbe literalmente leer el reloj del sistema en `src/domain/` y
`src/application/`; AGENTS.md lo repite como regla de verificación. FR-002 y FR-008 sí exigen que
el sistema, en su conjunto, use el instante de la solicitud cuando no se indique uno — ambas reglas
son compatibles si la lectura del reloj ocurre solo en el borde, exactamente como ya hace H002.

**Alternativas consideradas**:
- *`created_at`/`reference_time` opcionales dentro de `IncidentService`, con `datetime.now()`
  interno*: rechazada — viola el Principio I literalmente y rompe el determinismo de las pruebas
  de aplicación (tendrían que mockear el reloj, prohibido por el skill `bdd-acceptance`).

## Decisión 5 — Autogeneración de `incident_id`

**Decisión**: Cuando se omite `incident_id`, `IncidentService.create_incident` genera
`f"INC-{secrets.token_hex(4).upper()}"` (8 caracteres hexadecimales en mayúsculas, p. ej.
`INC-3F2A9B10`). Antes de usarlo (y antes de usar uno indicado explícitamente), se verifica con
`repository.get_incident(candidate_id)`; si por una colisión improbable el generado ya existe, se
reintenta con un nuevo valor aleatorio (no es un caso de negocio a exponer: es un detalle interno
de generación, nunca produce `409` para el llamador que omitió `incident_id`).

**Rationale**: `secrets.token_hex` es la función estándar recomendada para identificadores no
predecibles (preferible a `random`), vive en la biblioteca estándar (sin dependencia nueva,
Constitución Artículo 3) y produce exactamente el formato pedido por FR-002
(`INC-<HEX8>`). La generación es responsabilidad de la aplicación (forma de la solicitud, valor
por defecto), no del dominio ni del adaptador de salida.

**Alternativas consideradas**:
- *UUID4 truncado*: rechazada — no calza con el formato `INC-<HEX8>` (8 caracteres) pedido
  explícitamente por la clarificación de `spec.md`.
- *Contador incremental persistido*: rechazada — introduce estado adicional en el repositorio y
  una condición de carrera entre procesos (API y CLI) que `secrets.token_hex` evita por diseño.

## Decisión 6 — Los campos de fecha/hora y `status` viajan como `str` en los adaptadores de entrada

**Decisión**: `CreateIncidentRequestSchema.created_at` y `CreateIncidentRequestSchema.status` son
`Optional[str]` (no `Optional[datetime]` ni un `Literal`/enum de Pydantic); el query param
`reference_time` de la ruta de SLA y las opciones `--created-at`/`--reference-time`/`--status` de
Typer también son `Optional[str]`. Toda validación de formato (ISO 8601, `tzinfo`, pertenencia al
enum de `IncidentStatus`) ocurre dentro de `IncidentService` (o su función auxiliar
`parse_naive_local_datetime`), nunca en la capa de deserialización de FastAPI/Typer.

**Rationale**: Es la única forma de garantizar FR-018/FR-019/FR-020 (cuerpo siempre
`{"error": ...}`, código de salida siempre `1` en CLI) sin que Pydantic o Typer/Click intercepten
el valor inválido antes de que el código de la aplicación lo vea y respondan con su propio formato
de error (`RequestValidationError` de FastAPI; código de salida `2` de Click/Typer).

**Alternativas consideradas**:
- *Declarar `created_at: Optional[datetime]` y capturar `RequestValidationError`/el error de Click
  para reformatear su mensaje*: rechazada — es más código para lograr lo mismo que ya logra
  `str` + validación explícita, y el mensaje de error de Pydantic/Click no es el mismo que el de
  `require_naive_datetime` (p. ej. Pydantic sí acepta ofsets de zona horaria sin rechazarlos, lo
  que obligaría a una segunda vuelta de validación igualmente).

## Decisión 7 — Orden de operaciones de `create_incident` y manejo uniforme de errores de forma en FastAPI

**Decisión**: `IncidentService.create_incident` ejecuta, en este orden:
1. Validar `title`/`raw_text` no vacíos (reutilizando la misma regla que `triage_incident`, sin
   reimplementarla: ambos llaman a un helper interno compartido `_require_non_blank`).
2. Resolver/validar `status` (default `"OPEN"`; rechazar valores fuera del enum).
3. Resolver/verificar `incident_id` (autogenerar si se omite — Decisión 5 — o verificar conflicto
   con `repository.get_incident` si se indica explícitamente; `IncidentConflictError` si ya existe).
4. Clasificar con `classify_incident_report(incident_id, raw_text)` (dominio puro, sin cambios).
5. Buscar duplicados abiertos con `repository.find_open_duplicates(triage.duplicate_group_key)`
   (antes de guardar: ver Decisión 2 para la exclusión automática del propio id).
6. Construir el `Incident` (con `resolved_at = created_at` si `status == "RESOLVED"`, `None` en
   cualquier otro caso) y guardarlo con `repository.save_incident`.
7. Devolver `IncidentCreationResult` combinando el `Incident` guardado, los campos de `TriageResult`
   y `is_duplicate`/`duplicate_of` calculados en el paso 5.

Además, `create_app()` (FastAPI) registra un manejador explícito para
`fastapi.exceptions.RequestValidationError` que devuelve `422` con cuerpo `{"error": <mensaje>}`
en vez del cuerpo por defecto de FastAPI (`{"detail": [...]}`), para que un campo obligatorio
ausente o un JSON malformado en `POST /api/v1/incidents` cumplan FR-019 igual que cualquier otro
`422` de esta funcionalidad. Este manejador es adicional al manejador genérico de `Exception` ya
existente (`500`, sin cambios) y se aplica a toda la app (beneficia también, sin romperlas, a las
rutas ya existentes de H001/H002, que hoy no tienen escenario de prueba que ejercite un campo
ausente).

**Rationale**: El orden fija "conflicto de identificador" antes que "clasificación/duplicados" para
no hacer trabajo de clasificación sobre una solicitud que de todas formas se va a rechazar, y para
que el incidente ya existente nunca se toque (FR-006: "el incidente ya existente no se modifica").
`RequestValidationError` es la única ruta por la que FastAPI puede producir un cuerpo distinto a
`{"error": ...}` incluso con los campos declarados como `str` (p. ej. JSON sintácticamente
inválido, o `title` ausente del cuerpo); FR-019 lo exige explícitamente ("errores de forma de la
solicitud... JSON inválido").

**Alternativas consideradas**:
- *Verificar duplicados antes que el conflicto de identificador*: rechazada — haría el triaje
  (costo de clasificación) antes de saber si la solicitud se va a rechazar por conflicto, sin
  beneficio, y complicaría innecesariamente el mensaje de error si ambas condiciones coincidieran.
- *No registrar un manejador de `RequestValidationError` y aceptar el cuerpo por defecto de FastAPI
  para "campos faltantes/JSON inválido"*: rechazada — contradice FR-019 literalmente.

## Decisión 8 — Pruebas de aceptación reutilizan las fixtures de `tests/conftest.py` sin cambios

**Decisión**: `tests/test_spec_003_lifecycle_sla.py` reutiliza tal cual las fixtures ya definidas
para H002 (`incident_repository`, `incident_service`, `summary_api_client`, `summary_cli_app`),
sin añadir fixtures nuevas a `conftest.py`. Donde el nombre `summary_api_client`/`summary_cli_app`
no refleje bien el propósito de una prueba de H003, el test usa igualmente esas fixtures
(aceptando el nombre heredado) en vez de duplicar la construcción de `TestClient(create_app(...))`
/ `create_cli_app(...)` con otro nombre.

**Rationale**: Esas fixtures ya construyen `create_app(service=...)`/`create_cli_app(service)`
inyectando un `IncidentService` sobre un `SQLiteIncidentRepository(":memory:")` nuevo y aislado por
prueba — exactamente el requisito del skill `bdd-acceptance` ("nunca una instancia global
compartida entre pruebas") y lo que H003 también necesita, sin ningún campo ni comportamiento
adicional específico de H002 que H003 deba evitar. Introducir fixtures paralelas solo
duplicaría código de construcción ya correcto.

**Alternativas consideradas**:
- *Renombrar las fixtures a nombres neutros (`api_client_isolated`, `cli_app_isolated`)*: rechazada
  por alcance — renombrar fixtures ya usadas por `tests/test_spec_002_summary.py` es un cambio
  cosmético ajeno a H003 y arriesga un diff innecesario sobre pruebas ya verdes; puede proponerse
  como mejora futura, no como parte de este plan.
