# Research: Persistencia relacional dedicada y runtime en contenedores

Decisiones técnicas para materializar `spec.md` (H004) dentro de los límites ya fijados
por ADR-004 y la Constitución v1.1.0. No hay `[NEEDS CLARIFICATION]` sin resolver en
`plan.md`; este documento registra las decisiones de diseño que esos límites todavía
dejaban abiertas.

## Decisión 1: Forma de fila y mapeo de `psycopg` → `Incident`

- **Decisión**: `PostgresIncidentRepository` abre su conexión con
  `psycopg.connect(dsn, row_factory=psycopg.rows.dict_row, autocommit=True)`. Cada fila
  llega como `dict[str, Any]`, mapeada a `Incident` con la misma lógica de
  `_row_to_incident` que ya usa `SQLiteIncidentRepository` (mismos nombres de columna),
  salvo que el acceso es por clave de diccionario (`row["incident_id"]`) en vez de
  `sqlite3.Row`.
- **Rationale**: `dict_row` da una interfaz de acceso por nombre de columna idéntica en
  espíritu a `sqlite3.Row`, permitiendo que `_row_to_incident` de ambos adaptadores
  compartan la misma forma de lectura y sean fáciles de comparar en revisión, sin acoplar
  el dominio a ningún tipo de fila específico de un driver (el dominio solo ve `Incident`).
  `autocommit=True` evita manejar transacciones explícitas para operaciones de una sola
  sentencia, igual que el `self.conn.commit()` manual de SQLite logra hoy.
- **Alternativas consideradas**:
  - `tuple_row` (por defecto de `psycopg`) con mapeo posicional: rechazada porque un
    cambio de orden de columnas en el `SELECT` rompería el mapeo silenciosamente; el
    acceso por nombre es más seguro y más parecido al patrón ya establecido.
  - `class_row(Incident)` de `psycopg.rows`: rechazada porque mapea directamente a la
    `dataclass` del dominio desde el driver externo, lo que acopla `src.domain.models`
    (indirectamente, por nombre de campo) a un detalle de `psycopg`; mantener el mapeo
    manual en el adaptador preserva la frontera de la Constitución (Principio II) de
    forma más explícita.

## Decisión 2: Parametrización y "upsert" en PostgreSQL

- **Decisión**: Todo valor viaja parametrizado con `%s` (placeholder nativo de
  `psycopg`/libpq), nunca interpolado. `save_incident` usa
  `INSERT INTO incidents (...) VALUES (%s, ...) ON CONFLICT (incident_id) DO UPDATE SET
  title = EXCLUDED.title, ...` (una columna por cada campo salvo `incident_id`, la clave
  del conflicto).
- **Rationale**: `%s` es el equivalente directo del `?` de SQLite para este propósito
  (Constitución, Principio III: "todo valor de consulta SQL MUST viajar mediante
  placeholders parametrizados"). `ON CONFLICT ... DO UPDATE` es el equivalente funcional
  exacto de `INSERT OR REPLACE` de SQLite: mismo comportamiento observable
  (crear-o-reemplazar por `incident_id`), expresado con la sintaxis nativa de cada motor,
  sin introducir una capa de abstracción SQL compartida (que violaría "SQL nativo, sin
  ORM" de ADR-001/ADR-004).
- **Alternativas consideradas**:
  - `INSERT ... ON CONFLICT (incident_id) DO NOTHING` + `UPDATE` separado: rechazada por
    requerir dos sentencias y una decisión adicional de control de flujo que SQLite no
    necesita; rompe la paridad de comportamiento exigida por FR-006 al introducir una
    ventana de carrera distinta entre motores.
  - Mapeo genérico de placeholders (una capa que traduzca `?` a `%s` en tiempo de
    ejecución): rechazada por ser una abstracción SQL no solicitada por ningún ADR y que
    oscurecería qué sentencia exacta se ejecuta contra cada motor.

## Decisión 3: Esquema e índices de PostgreSQL

- **Decisión**: La tabla `incidents` en PostgreSQL replica exactamente las columnas de
  SQLite (`incident_id TEXT PRIMARY KEY, title TEXT NOT NULL, component TEXT NOT NULL,
  severity TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL, resolved_at
  TEXT, symptom_category TEXT`), con el mismo índice compuesto
  `(component, status)` (ADR-001) creado con `CREATE INDEX IF NOT EXISTS`. `created_at` y
  `resolved_at` son `TEXT` (ISO 8601), no `TIMESTAMP`/`TIMESTAMPTZ` nativos de PostgreSQL.
- **Rationale**: ADR-004, Decisión 3, exige timestamps como texto ISO 8601 en ambos
  motores para garantizar paridad exacta de comparación; usar `TIMESTAMP` en PostgreSQL y
  `TEXT` en SQLite introduciría una divergencia de formato que FR-006 (resultado de
  negocio idéntico) prohíbe. El mismo índice en ambos motores mantiene vigente la
  optimización de ADR-001 sin importar el motor activo.
- **Alternativas consideradas**:
  - `TIMESTAMP` nativo en PostgreSQL con conversión en el adaptador: rechazada; añade
    lógica de conversión por motor y riesgo de desfase de zona horaria/precisión que la
    Constitución (Principio I: datetimes siempre naive) ya busca evitar por completo.
  - Tabla `sla_policies` también en PostgreSQL (como en SQLite): se mantiene por
    simetría estructural con `SQLiteIncidentRepository`, aunque hoy ningún método del
    puerto la consulta directamente desde el adaptador (`evaluate_sla_status` vive en
    `src/domain/`); se conserva para no introducir una asimetría de esquema entre
    motores sin necesidad.

## Decisión 4: Verificar conformidad con `IncidentRepositoryPort` sin un PostgreSQL real en `pytest`

- **Decisión**: `IncidentRepositoryPort` es un `Protocol` `@runtime_checkable` que solo
  declara métodos (ningún atributo de datos). Para un Protocol así, Python permite
  `issubclass(PostgresIncidentRepository, IncidentRepositoryPort)` a nivel de **clase**,
  sin instanciar el adaptador ni abrir una conexión real. La prueba de conformidad usa
  `issubclass(...)` para `PostgresIncidentRepository` y, adicionalmente,
  `isinstance(...)` sobre una instancia real de `SQLiteIncidentRepository` (gratis, en
  memoria). La rama de selección de `create_repository("postgresql://...")` se prueba
  con un doble de prueba: se sustituye (`monkeypatch`) la referencia a
  `PostgresIncidentRepository` dentro de `factory.py` por una clase de prueba mínima que
  cumple el puerto sin red, y se verifica que la fábrica la selecciona y le pasa el DSN
  correcto para ese esquema.
- **Rationale**: El objetivo de `tests/test_spec_004_runtime_health.py` (`uv run pytest
  -v`) es determinista y debe ejecutarse sin Docker ni un servidor PostgreSQL disponible
  (Constitución, Principio V: pruebas BDD deterministas). Verificar la conformidad
  estructural del puerto y la lógica de selección de la fábrica cubre exactamente lo que
  pide la especificación ("`create_repository` verificando que tanto SQLite como
  PostgreSQL cumplen `IncidentRepositoryPort`") sin convertir la prueba en una prueba de
  integración frágil dependiente de infraestructura externa.
- **Alternativas consideradas**:
  - Levantar un contenedor PostgreSQL real durante `pytest` (p. ej. via `testcontainers`):
    rechazada para este corte; añade una dependencia de desarrollo nueva y un
    requisito de Docker para simplemente ejecutar `uv run pytest -v`, lo que contradice
    FR-008 (el sistema debe poder probarse localmente sin contenedores). La verificación
    de extremo a extremo contra un PostgreSQL real queda cubierta manualmente por
    `quickstart.md` (Docker Compose), no por la suite automatizada.
  - Omitir la prueba de PostgreSQL con `pytest.mark.skipif` si no hay servidor disponible:
    rechazada; produce una prueba que nunca corre en el entorno normal de desarrollo
    (sin Docker), lo que equivale a no probar la conformidad del adaptador en absoluto.

## Decisión 5: `factory.create_repository(database_url)` vs. `get_incident_repository()`

- **Decisión**: Se agrega `create_repository(database_url: str) -> IncidentRepositoryPort`
  como función pura (recibe la URL explícitamente, sin leer `os.environ`), que contiene
  toda la lógica de selección por esquema (`sqlite:///` → `SQLiteIncidentRepository`,
  `postgresql://` → `PostgresIncidentRepository`, cualquier otro esquema → `ValueError`
  explícito). `get_incident_repository()` se conserva como función delgada que lee
  `DATABASE_URL` del entorno (con el mismo valor por defecto `sqlite:///:memory:` de hoy)
  y delega en `create_repository(...)`.
- **Rationale**: Separar la lectura del entorno de la lógica de selección hace
  `create_repository` trivialmente probable con URLs explícitas (sin `monkeypatch` de
  variables de entorno) y no rompe la firma que ya consumen `api/app.py` y `cli.py`
  (`get_incident_repository()`, sin argumentos), evitando un cambio de contrato en los
  adaptadores de entrada ya existentes.
- **Alternativas consideradas**:
  - Reemplazar `get_incident_repository()` por `create_repository()` en todos los
    llamadores: rechazada; obligaría a que cada adaptador de entrada leyera
    `os.environ["DATABASE_URL"]` por su cuenta, duplicando esa responsabilidad fuera de
    la fábrica (Constitución, Principio II: la resolución de la implementación de salida
    pasa siempre por `src.adapters.outbound.factory`, como una sola responsabilidad).

## Decisión 6: Imagen de contenedor del servicio `api`

- **Decisión**: `Dockerfile` basado en `python:3.12-slim`, instala `uv` (copiando el
  binario desde la imagen oficial `ghcr.io/astral-sh/uv`), ejecuta
  `uv sync --frozen --no-dev` para instalar solo dependencias de producción, copia el
  código fuente, y arranca con `uv run uvicorn src.adapters.inbound.api.app:app --host
  0.0.0.0 --port 8000`. El `HEALTHCHECK` de Docker Compose para `api` invoca `GET /health`
  con un script Python de una línea (`python -c "import urllib.request;
  urllib.request.urlopen('http://localhost:8000/health')"`), no `curl`.
- **Rationale**: `python:3.12-slim` no incluye `curl` por defecto; instalarlo solo para el
  healthcheck aumentaría el tamaño de la imagen sin necesidad (RNF-004: imagen acotada a
  lo necesario), cuando el propio runtime de Python ya puede hacer la petición HTTP.
  `--no-dev` excluye `pytest`/`ruff`/`httpx` de la imagen de producción, que no los
  necesita para ejecutarse.
- **Alternativas consideradas**:
  - Instalar `curl` en la imagen para el healthcheck: rechazada por el costo de tamaño
    de imagen sin beneficio funcional adicional.
  - Imagen multi-stage (build en una etapa, runtime en otra, sin `uv` en la imagen
    final): se difiere; el proyecto es un starter educativo de Semana 1 y una sola etapa
    con `uv sync --frozen --no-dev` ya cumple RNF-001 (reproducibilidad) y RNF-004
    (aislamiento) sin la complejidad adicional de un build multi-etapa.

## Decisión 7: Credenciales de PostgreSQL en `docker-compose.yml`

- **Decisión**: El servicio `db` fija `POSTGRES_USER`, `POSTGRES_PASSWORD` y
  `POSTGRES_DB` con valores de desarrollo fijos y no sensibles (p. ej.
  `incidentops`/`incidentops`/`incidentops`), declarados directamente en
  `docker-compose.yml` con un comentario explícito de que son credenciales de desarrollo
  local, no aptas para un entorno de producción real. `api` recibe `DATABASE_URL`
  apuntando a `db` con esas mismas credenciales.
- **Rationale**: Este es un proyecto semilla educativo (ver `pyproject.toml`,
  `description`); introducir gestión de secretos (Docker secrets, un `.env` ignorado,
  un gestor externo) está fuera del alcance de H004 (`docs/ROADMAP.md` excluye
  "monitoreo avanzado" y no incluye gestión de secretos entre sus resultados esperados).
  Fijar valores de desarrollo directamente en `docker-compose.yml` mantiene RNF-001
  (reproducibilidad con un solo comando) sin pasos manuales de configuración de secretos.
- **Alternativas consideradas**:
  - Variables de entorno externas vía un archivo `.env` no versionado: rechazada para
    este corte porque reintroduce un paso manual de configuración antes de poder levantar
    el stack (contradice RNF-001), sin un requisito de seguridad en el alcance de H004
    que lo justifique.
