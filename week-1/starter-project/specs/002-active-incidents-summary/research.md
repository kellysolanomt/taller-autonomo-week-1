# Fase 0 — Investigación: Resumen de incidentes activos (H002)

Todas las incógnitas de `spec.md` ya quedaron resueltas en su sección `## Clarifications` (sesión 2026-11-23). Las incógnitas de esta fase son exclusivamente técnicas: cómo materializar la Arquitectura Hexagonal (ADR-003) para H002 sin reabrir decisiones de negocio.

## Decisión 1 — Forma del puerto de salida

**Decisión**: `IncidentRepositoryPort` se define como `typing.Protocol` en `src/application/ports.py`, con las cinco operaciones indicadas: `save_incident(incident)`, `get_incident(incident_id)`, `find_open_duplicates(component, symptom_category)`, `list_active_incidents(component_filter=None)` y `check_health()`.

**Rationale**: La Constitución 2.2 ya exige que `src/application/` defina puertos con `typing.Protocol`; ADR-003 ya decide que el repositorio SQLite implementa un puerto de salida. H002 es la primera vez que existe una segunda pieza de infraestructura real detrás de ese puerto (el chequeo de conectividad y el futuro motor de H004 lo reutilizarán sin tocar la aplicación).

**Alternativas consideradas**:
- *Clase base abstracta (`abc.ABC`)*: rechazada — exige herencia explícita del adaptador concreto; `Protocol` permite verificación estructural (`isinstance` con `@runtime_checkable`) sin acoplar el adaptador a un módulo de aplicación en tiempo de ejecución, y es lo que la Constitución ya fija.
- *Repositorio concreto sin puerto, usado directo desde los adaptadores de entrada*: rechazada — impide intercambiar el motor en H004 y obliga a los adaptadores de entrada a importar `sqlite3` o una clase concreta, violando el Artículo 2.3.

## Decisión 2 — Dónde vive la evaluación de SLA del resumen

**Decisión**: `SQLiteIncidentRepository.list_active_incidents` devuelve únicamente entidades `Incident` (persistencia pura). `IncidentService.get_active_incidents_summary` es quien llama a `src/domain/sla_calculator.evaluate_sla_status` por cada incidente para construir el detalle y los agregados.

**Rationale**: El repositorio heredado (`src/incident_repository.py`, método `get_active_incidents_summary`) mezcla la consulta SQL con la evaluación de SLA — exactamente el acoplamiento que ADR-003 señala como problema a resolver ("el repositorio SQLite no solo persiste, sino que también orquesta la evaluación de SLA"). Mantenerlo en el adaptador de salida duplicaría la regla de negocio el día que exista un segundo motor (H004) y rompería la Constitución 1.1 (una sola fuente de verdad para SLA).

**Alternativas consideradas**:
- *Dejar la evaluación de SLA en el repositorio SQLite (como hoy)*: rechazada por la razón anterior.
- *Evaluar SLA en el adaptador de entrada (FastAPI/Typer)*: rechazada — duplicaría la orquestación en dos adaptadores de entrada, rompiendo la paridad HTTP/CLI (Artículo 2.2 exige que `IncidentService` sea el único orquestador del caso de uso).

## Decisión 3 — Reloj del sistema y `reference_time` por defecto (FR-013)

**Decisión**: `IncidentService.get_active_incidents_summary(component_filter, reference_time)` exige `reference_time` como argumento obligatorio y nunca lee el reloj. El valor por defecto "instante de la consulta" se resuelve **solo** en el borde: la ruta FastAPI y el comando Typer leen `datetime.now()` únicamente cuando el llamador (query param HTTP / opción CLI) no proporciona `reference_time`, y pasan siempre un valor concreto hacia `IncidentService`.

**Rationale**: La Constitución 1.2 prohíbe leer el reloj del sistema en dominio y aplicación; `AGENTS.md` lo repite como regla de verificación ("Changes must stay deterministic: never read the system clock; `reference_time` is injected"). FR-013 sí exige que el sistema, en su conjunto, pueda comportarse con el instante de la consulta cuando no se indique uno. Ambas reglas son compatibles si la lectura del reloj ocurre exclusivamente en el "borde" (adaptadores de entrada, que ya son el *composition root* según el Artículo 2.5), nunca en `src/domain/` ni en `src/application/`. Las pruebas de aceptación siguen inyectando siempre un `reference_time` explícito, preservando el determinismo de la suite.

**Alternativas consideradas**:
- *`reference_time: Optional[datetime] = None` en el propio `IncidentService`, con `datetime.now()` interno si es `None`*: rechazada — viola literalmente la Constitución 1.2 y rompe la determinación de las pruebas de aplicación (tendrían que mockear el reloj).

## Decisión 4 — `find_open_duplicates` sin caso de uso en H002

**Decisión**: El puerto incluye `find_open_duplicates(component: str, symptom_category: str) -> list[Incident]` desde ya, con una implementación real (no un *stub*) en `SQLiteIncidentRepository`, pero **sin** conectarlo a ningún caso de uso de `IncidentService` en este corte. Para que la consulta sea genuina, `Incident` (dominio) gana un campo opcional `symptom_category: Optional[SymptomCategory] = None` (aditivo, con valor por defecto; no rompe construcciones existentes de `Incident`), y el esquema de `incidents` en SQLite gana una columna `symptom_category TEXT` nullable.

**Rationale**: La Constitución 1.8 define la clave de duplicados (`<component>:<symptom_category>`) y reserva la fusión automática para H003; el usuario pidió el método en el puerto ahora, como preparación explícita. Añadir el campo a `Incident` en vez de inventar un parámetro adicional en `save_incident` evita una firma ad-hoc y deja that el dominio describa completamente al incidente persistido, cerrando el ciclo con `TriageResult.duplicate_group_key` (que ya expone `symptom_category`) de cara a H003.

**Alternativas consideradas**:
- *No incluir `find_open_duplicates` hasta H003*: rechazada — el usuario lo pidió explícitamente en el puerto para este hito, y no tiene costo real dado que `Incident` ya puede cargar el dato de forma opcional.
- *`find_open_duplicates(duplicate_group_key: str)` (clave ya combinada)*: rechazada — obligaría a persistir la clave combinada como columna derivada; es más simple y más consultable guardar `component` y `symptom_category` por separado y combinar en el llamador cuando exista (H003).
- *Stub que lanza `NotImplementedError`*: rechazada — el método entra en el "contrato cumplido por `SQLiteIncidentRepository`" verificado por prueba (ver `tests/test_spec_002_summary.py`); un stub haría fallar esa verificación de cumplimiento o la volvería trivial.

## Decisión 5 — Selección de repositorio vía `DATABASE_URL`

**Decisión**: `src/adapters/outbound/factory.py` expone `get_incident_repository() -> IncidentRepositoryPort`, que lee `os.environ.get("DATABASE_URL", "sqlite:///:memory:")`. Solo reconoce el esquema `sqlite:///`; el resto de la URL después de ese prefijo es la ruta pasada directamente a `sqlite3.connect(...)` (`":memory:"` o una ruta relativa simple). Cualquier otro esquema lanza `ValueError` explícito en vez de degradar silenciosamente.

**Rationale**: La Constitución 3.2 exige un ADR previo para cambiar de motor de base de datos; H002 no cambia de motor, solo decide *dónde* vive el archivo SQLite, así que no hay violación. El cableado concreto (leer una variable de entorno) es responsabilidad del borde (Artículo 2.5), no de la aplicación ni del dominio.

**Alternativas consideradas**:
- *Soportar también `postgresql://` u otro motor ya en H002*: rechazada — ningún escenario de `spec.md` lo requiere y violaría la Constitución 3.2 (exige ADR previo); queda para H004.
- *Caché de instancia (singleton de proceso) en la fábrica*: rechazada por ahora — no hay un escenario de H002 que lo necesite; cada proceso (API o CLI) construye su propio repositorio al arrancar, igual que el patrón ya usado por `create_app()`/`_service` en H001. Para compartir datos entre el proceso de la API y una invocación de CLI en la misma máquina, se debe fijar `DATABASE_URL` a un archivo real; el valor por defecto en memoria es apto solo para desarrollo/pruebas.

## Decisión 6 — Paridad HTTP/CLI en las pruebas con almacenamiento aislado

**Decisión**: `create_app()` (FastAPI) y el nuevo `create_cli_app(service)` (Typer) aceptan un `IncidentService` ya construido. Las pruebas de paridad (Historia de Usuario 2) construyen **un solo** `SQLiteIncidentRepository(":memory:")` y **un solo** `IncidentService` por test, y lo inyectan tanto en el cliente HTTP como en la app CLI de esa prueba, de modo que ambos adaptadores leen el mismo conjunto de incidentes sembrado en el `Given` del escenario.

**Rationale**: El skill `bdd-acceptance` exige almacenamiento aislado por `test_bdd_*` (nunca una instancia global compartida entre pruebas) y que la fixture de almacenamiento se inyecte en la construcción del cliente/app de ese test, igual que `create_app()` ya permite inyectar dependencias en producción. `IncidentService` pasa de no tener dependencias (H001, solo `triage_incident`) a recibir `IncidentRepositoryPort` en el constructor; esto no rompe `triage_incident` (no toca el repositorio) y mantiene retrocompatibles las fixtures `api_client`/`cli_app_under_test` existentes de H001, que seguirán usando la fábrica por defecto (`DATABASE_URL` sin definir → `sqlite:///:memory:`).

**Alternativas consideradas**:
- *Mantener `cli.py` con un `Typer()` y `_service` a nivel de módulo, sin función fábrica*: rechazada — impediría inyectar un repositorio distinto por prueba sin recurrir a mocks que reemplacen el adaptador de salida, prohibido explícitamente por el skill `bdd-acceptance`.
- *Mockear el repositorio en las pruebas de paridad*: rechazada — el mismo skill prohíbe parchear el almacenamiento con mocks que reemplacen la lógica del adaptador de salida; se usa una instancia real en memoria.
