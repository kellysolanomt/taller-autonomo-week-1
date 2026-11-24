# Especificación de Funcionalidad: Persistencia relacional dedicada y runtime en contenedores

**Rama de funcionalidad**: `004-postgres-container-runtime`

**Creada**: 2026-11-24

**Estado**: Borrador

**Entrada**: Descripción del usuario: "Especifica la Feature 004 (respaldada por ADR-004 y la Constitución) incluyendo requisitos funcionales y Requisitos No Funcionales (RNF) con al menos 4 escenarios BDD: (1) `GET /health` operativo y comando CLI `health` ejecutando un chequeo real de conectividad; (2) `GET /health` ante fallo de conectividad (503); (3) selección transparente SQLite/PostgreSQL vía `DATABASE_URL`; (4) orquestación reproducible en 2 contenedores (`api` + `db`) con Docker Compose."

> Corresponde al hito **H004 — Persistencia relacional dedicada y runtime en contenedores** de
> `docs/ROADMAP.md`, y materializa la decisión ya aprobada en **ADR-004** (persistencia dual
> SQLite/PostgreSQL sin ORM vía `psycopg[binary]`, selección por `DATABASE_URL`) y en la
> **Constitución v1.1.0** (Principio III).

## Escenarios de Usuario y Pruebas *(obligatorio)*

### Historia de Usuario 1 - Confirmar si el servicio está operativo contra su base de datos, por HTTP y CLI (Prioridad: P1)

Como persona de guardia o como orquestador automatizado (p. ej. Docker, un balanceador de carga),
quiero poder preguntarle al servicio si está realmente operativo contra su base de datos —no solo
si el proceso está vivo— para decidir si puede recibir tráfico o si debe reiniciarse.

**Por qué esta prioridad**: Sin un chequeo de salud real y verificable, ningún orquestador puede
tomar decisiones seguras de arranque, reinicio o enrutamiento de tráfico; es la base sobre la que
se apoyan las demás historias de este hito (la orquestación de contenedores de la Historia 3
depende de este chequeo).

**Prueba independiente**: Puede probarse por completo apuntando el servicio a una base de datos
disponible y verificando una respuesta exitosa por HTTP y por CLI, y luego repitiendo la prueba con
la base de datos inalcanzable, verificando que ambas interfaces reportan el mismo fallo.

**Escenarios de Aceptación**:

1. **Given** el motor de persistencia configurado está disponible, **When** se consulta
   `GET /health`, **Then** la respuesta es 200 OK con cuerpo `{"status": "ok", "database": "connected"}`,
   obtenido tras ejecutar una consulta real (`SELECT 1` o equivalente) contra esa base de datos, no
   una verificación simulada.
2. **Given** el motor de persistencia configurado está disponible, **When** se ejecuta el comando
   CLI `health`, **Then** el proceso termina con código de salida 0 e imprime en stdout el mismo
   cuerpo `{"status": "ok", "database": "connected"}` que la respuesta HTTP.
3. **Given** el adaptador de persistencia reporta que la conexión falló (`check_health()` devuelve
   `false`), **When** se consulta `GET /health`, **Then** la respuesta es 503 Service Unavailable
   con cuerpo `{"status": "error", "database": "unavailable"}`.
4. **Given** el adaptador de persistencia reporta que la conexión falló, **When** se ejecuta el
   comando CLI `health`, **Then** el proceso termina con código de salida 1 e imprime en stdout el
   mismo cuerpo `{"status": "error", "database": "unavailable"}` que la respuesta HTTP.
5. **Given** una consulta repetida de `GET /health` o del comando `health` sin ningún cambio en la
   disponibilidad de la base de datos, **When** se invoca varias veces seguidas, **Then** el
   resultado es el mismo en cada invocación (ninguna llamada deja efectos ni estado adicional).

---

### Historia de Usuario 2 - Elegir el motor de persistencia por entorno sin cambiar código (Prioridad: P2)

Como persona que despliega el servicio, quiero que el motor de persistencia (SQLite o PostgreSQL)
se determine únicamente por la configuración del entorno, para desarrollar y probar localmente de
forma ligera y, sin tocar una sola línea de código, operar en producción contra PostgreSQL.

**Por qué esta prioridad**: Depende de que el chequeo de salud (Historia 1) ya exista para poder
verificar cada motor, pero es independiente de la orquestación en contenedores (Historia 3): la
selección de motor debe funcionar igual con o sin Docker.

**Prueba independiente**: Puede probarse por completo configurando `DATABASE_URL` con cada uno de
los esquemas soportados y verificando que el servicio queda respaldado por el motor correspondiente,
con idéntico resultado de negocio en ambos casos.

**Escenarios de Aceptación**:

1. **Given** `DATABASE_URL` tiene el esquema `postgresql://...`, **When** el servicio construye su
   repositorio de incidentes, **Then** queda respaldado por el adaptador de PostgreSQL.
2. **Given** `DATABASE_URL` tiene el esquema `sqlite:///...`, **When** el servicio construye su
   repositorio de incidentes, **Then** queda respaldado por el adaptador de SQLite, sin requerir
   PostgreSQL ni contenedores en ejecución.
3. **Given** `DATABASE_URL` no está definida, **When** el servicio construye su repositorio de
   incidentes, **Then** queda respaldado por el adaptador de SQLite en memoria (`sqlite:///:memory:`),
   permitiendo desarrollo y pruebas rápidas sin contenedores.
4. **Given** el mismo incidente de ejemplo registrado una vez contra SQLite y otra vez contra
   PostgreSQL, **When** se consulta su triaje, su estado de SLA o el resumen de incidentes activos,
   **Then** el resultado de negocio es idéntico en ambos motores.
5. **Given** un valor de `DATABASE_URL` con un esquema distinto de `sqlite:///` o `postgresql://`,
   **When** el servicio intenta construir su repositorio de incidentes, **Then** la construcción se
   rechaza de forma explícita, identificando el esquema no soportado, en vez de arrancar en un
   estado ambiguo.

---

### Historia de Usuario 3 - Levantar el servicio de forma reproducible en contenedores (Prioridad: P3)

Como persona que despliega el servicio, quiero levantar la API y su base de datos dedicada con una
sola orquestación reproducible, para que cualquier entorno (una máquina nueva, un pipeline de CI)
arranque el mismo stack sin pasos manuales adicionales ni fallos por orden de arranque.

**Por qué esta prioridad**: Depende de que el chequeo de salud (Historia 1) y la selección de motor
(Historia 2) ya existan, porque la orquestación los usa para decidir cuándo cada servicio está listo.

**Prueba independiente**: Puede probarse por completo levantando el stack desde cero en una máquina
con Docker instalado y verificando que ambos servicios llegan a un estado saludable sin
intervención manual, incluso si `api` arranca antes de que `db` esté lista.

**Escenarios de Aceptación**:

1. **Given** una máquina con Docker y Docker Compose instalados y el repositorio del proyecto,
   **When** se levanta el stack definido en `docker-compose.yml`, **Then** se crean dos servicios —
   `api` y `db` (imagen `postgres:16-alpine`) — y ambos alcanzan un estado saludable sin pasos
   manuales adicionales.
2. **Given** el servicio `db` aún no ha terminado de iniciar, **When** se levanta el stack completo,
   **Then** el servicio `api` espera a que `db` reporte un estado saludable (`depends_on` con
   `condition: service_healthy`) antes de iniciar su propio proceso, en vez de fallar por una base
   de datos todavía no disponible.
3. **Given** el servicio `db` en ejecución, **When** se reinicia o recrea su contenedor, **Then**
   los datos previamente almacenados siguen disponibles después del reinicio, gracias a su volumen
   persistente.
4. **Given** el stack en ejecución, **When** un orquestador externo consulta el chequeo de salud de
   cada servicio (`pg_isready` para `db`, `GET /health` para `api`), **Then** cada chequeo refleja
   el estado real de ese servicio de forma independiente.
5. **Given** el código fuente del servicio `api`, **When** se construye su imagen de contenedor a
   partir del Dockerfile del proyecto (`python:3.12-slim`, dependencias instaladas con `uv`), **Then**
   la imagen resultante no incluye archivos ajenos a la ejecución del servicio (historial de control
   de versiones, entornos virtuales locales, artefactos de prueba), gracias a un `.dockerignore`
   explícito.

### Casos Límite

- ¿Qué ocurre si `DATABASE_URL` apunta a un esquema no soportado (ni `sqlite:///` ni
  `postgresql://`)? El servicio rechaza la construcción del repositorio de forma explícita e
  identificable, en vez de arrancar en un estado ambiguo o fallar más adelante de forma confusa.
- ¿Qué ocurre si la base de datos deja de estar disponible después de que el servicio ya inició
  correctamente? El siguiente chequeo de salud (HTTP o CLI) refleja el fallo real de inmediato; no
  se sigue reportando un estado saludable obtenido antes del fallo.
- ¿Qué ocurre si el contenedor `api` se reinicia mientras `db` ya está saludable? `api` reconstruye
  su conexión contra `db` sin requerir ninguna acción manual adicional.
- ¿El chequeo de salud modifica o crea algún dato? No; es una operación de solo lectura, igual que
  la auditoría de SLA (H003) y el resumen de incidentes activos (H002).
- ¿Qué ocurre si se recrea el contenedor `db` sin su volumen persistente (p. ej. se elimina
  explícitamente)? Los datos previamente almacenados se pierden; esto es un caso de administración
  explícita y deliberada, fuera del comportamiento normal de reinicio cubierto por esta
  especificación.

## Requisitos *(obligatorio)*

### Requisitos Funcionales

- **FR-001**: El sistema DEBE exponer un endpoint HTTP `GET /health` y un comando CLI `health`, ambos
  invocando el mismo caso de uso de chequeo de conectividad; ninguno de los dos adaptadores
  reimplementa la lógica de verificación por su cuenta.
- **FR-002**: El chequeo de salud DEBE ejecutar una operación de lectura real (equivalente a
  `SELECT 1`) contra la base de datos configurada por `DATABASE_URL`, nunca una verificación
  simulada o basada únicamente en la existencia de una conexión abierta sin consultar.
- **FR-003**: Cuando el chequeo de conectividad sea exitoso, `GET /health` DEBE responder 200 OK con
  cuerpo `{"status": "ok", "database": "connected"}`, y el comando CLI `health` DEBE imprimir el
  mismo cuerpo en stdout y terminar con código de salida 0.
- **FR-004**: Cuando el chequeo de conectividad falle, `GET /health` DEBE responder 503 Service
  Unavailable con cuerpo `{"status": "error", "database": "unavailable"}`, y el comando CLI `health`
  DEBE imprimir el mismo cuerpo y terminar con código de salida 1.
- **FR-005**: El sistema DEBE seleccionar el adaptador de persistencia exclusivamente a partir del
  esquema de `DATABASE_URL`: `postgresql://...` selecciona el adaptador de PostgreSQL;
  `sqlite:///...`, o la ausencia de la variable (por defecto `sqlite:///:memory:`), selecciona el
  adaptador de SQLite.
- **FR-006**: La selección de motor DEBE ser transparente para el dominio y la aplicación: el
  resultado de negocio de triaje, duplicados, SLA y chequeo de salud DEBE ser idéntico sin importar
  cuál de los dos motores esté activo, para la misma entrada.
- **FR-007**: Un valor de `DATABASE_URL` con un esquema distinto de `sqlite:///` o `postgresql://`
  DEBE rechazarse de forma explícita al momento de construir el repositorio, identificando el
  esquema no soportado, en vez de permitir que el servicio arranque en un estado ambiguo.
- **FR-008**: El sistema DEBE poder ejecutarse localmente sin contenedores contra
  `sqlite:///:memory:` o un archivo SQLite, para desarrollo y pruebas rápidas, sin requerir
  PostgreSQL ni Docker.
- **FR-009**: El sistema DEBE poder orquestarse de forma reproducible mediante dos servicios en
  contenedores —`api` y `db`—, donde `db` ejecuta PostgreSQL (imagen `postgres:16-alpine`) con un
  volumen persistente que conserva los datos entre reinicios o recreaciones del contenedor.
- **FR-010**: El servicio `db` DEBE exponer un chequeo de salud propio (basado en `pg_isready` o
  equivalente) que indique cuándo PostgreSQL está listo para aceptar conexiones.
- **FR-011**: El servicio `api` DEBE esperar a que el servicio `db` reporte un estado saludable
  (`depends_on` con `condition: service_healthy`) antes de iniciar su propio proceso, para evitar
  fallos de arranque por una base de datos todavía no disponible.
- **FR-012**: El servicio `api` DEBE exponer su propio chequeo de salud basado en `GET /health`, de
  modo que un orquestador externo pueda determinar si la API está operativa, incluyendo su
  conectividad con la base de datos.
- **FR-013**: La imagen de contenedor del servicio `api` DEBE construirse mediante un Dockerfile
  reproducible (`python:3.12-slim`) que instale las dependencias del proyecto con `uv`, y DEBE
  excluir mediante un `.dockerignore` explícito cualquier archivo ajeno a la ejecución del servicio.

### Requisitos No Funcionales

- **RNF-001 (Reproducibilidad)**: Levantar el stack completo (`api` + `db`) desde cero DEBE producir
  el mismo comportamiento observable en cualquier máquina con Docker instalado, sin pasos manuales
  de configuración adicionales a los ya declarados en `docker-compose.yml`.
- **RNF-002 (Portabilidad y transparencia de motor)**: Cambiar de SQLite a PostgreSQL, o viceversa,
  DEBE requerir únicamente cambiar el valor de `DATABASE_URL`, sin modificar código de dominio, de
  aplicación ni de los adaptadores de entrada.
- **RNF-003 (Fiabilidad del chequeo de salud)**: El estado de salud reportado (`GET /health` y
  comando `health`) DEBE reflejar en todo momento el resultado real de la última verificación de
  conectividad; NUNCA DEBE devolver un valor cacheado u optimista que oculte una base de datos
  inalcanzable.
- **RNF-004 (Aislamiento de la imagen)**: La imagen de contenedor del servicio `api` DEBE excluir,
  mediante `.dockerignore`, los entornos virtuales locales, cachés, el historial de control de
  versiones y los artefactos de prueba, manteniendo la imagen reproducible y acotada a lo necesario
  para ejecutar el servicio.
- **RNF-005 (Resiliencia de arranque)**: Una base de datos temporalmente no disponible al iniciar el
  stack NUNCA DEBE provocar que el servicio `api` reporte un estado de salud falso; DEBE esperar a
  que `db` esté saludable para iniciar, y DEBE reportar su propio chequeo de salud como no operativo
  mientras la conectividad no se haya restablecido.
- **RNF-006 (Persistencia de datos)**: Los datos almacenados en PostgreSQL DEBEN sobrevivir a un
  reinicio o recreación del contenedor `db`, gracias al volumen persistente declarado en
  `docker-compose.yml`.

### Entidades Clave

- **Resultado de chequeo de salud**: resultado observable de verificar la conectividad real con el
  motor de persistencia configurado; se expresa como `status` (`"ok"` o `"error"`) y `database`
  (`"connected"` o `"unavailable"`).
- **Configuración de motor de persistencia**: el valor de `DATABASE_URL` vigente en el entorno, que
  determina de forma transparente cuál adaptador concreto (SQLite o PostgreSQL) atiende las
  operaciones de persistencia, sin alterar el resultado de negocio observable.
- **Stack de contenedores**: el conjunto reproducible de servicios (`api`, `db`) que conforma el
  entorno de ejecución en contenedores, junto con sus chequeos de salud y el orden de disponibilidad
  entre ellos.

## Criterios de Éxito *(obligatorio)*

### Resultados Medibles

- **SC-001**: Cualquier persona u orquestador externo puede determinar, en una sola llamada (HTTP o
  CLI), si el servicio está operativo contra su base de datos, sin inspeccionar logs ni el estado
  interno del proceso.
- **SC-002**: El resultado del chequeo de salud y el comportamiento de negocio (triaje, duplicados,
  SLA) son idénticos sin importar si el entorno usa SQLite o PostgreSQL, para la misma entrada.
- **SC-003**: Levantar el stack completo en un entorno nuevo con Docker instalado no requiere más de
  un comando y no produce fallos de arranque por orden de disponibilidad entre `api` y `db`.
- **SC-004**: Un fallo real de conectividad con la base de datos se refleja en el chequeo de salud en
  la siguiente consulta posterior al fallo, sin falsos positivos de servicio saludable.
- **SC-005**: Los datos almacenados en el entorno de contenedores permanecen disponibles después de
  reiniciar o recrear el contenedor de base de datos, sin intervención manual.

## Supuestos

- El comando CLI `health` sigue el mismo patrón de salida ya vigente en el resto de la CLI
  (`triage`, `summary`, `create`, `sla`): imprime JSON en stdout y usa el código de salida para
  señalar éxito (0) o un resultado no operativo (1); no se introduce un código de salida distinto
  de los ya usados por esta CLI.
- Los parámetros de intervalo, tiempo de espera y reintentos de los chequeos de salud de
  `docker-compose.yml` (`pg_isready` para `db`, `GET /health` para `api`) usan valores por defecto
  razonables, salvo que una fase de implementación posterior requiera ajustarlos.
- Esta funcionalidad no incluye una migración automática de datos existentes en SQLite hacia
  PostgreSQL; cada entorno elige su motor mediante `DATABASE_URL` de forma independiente, sin
  migración de datos entre motores.
- El volumen persistente de PostgreSQL es gestionado por Docker (volumen nombrado) y no requiere
  configuración adicional de infraestructura externa en este corte.
- No se requiere autenticación ni autorización para `GET /health` ni para el comando CLI `health`,
  consistente con el alcance ya definido para el resto de interfaces del sistema (H001-H003).
- Alta disponibilidad, replicación o respaldo automatizado de PostgreSQL, orquestación multi-entorno
  y monitoreo avanzado quedan fuera de alcance, según `docs/ROADMAP.md` (H004).
