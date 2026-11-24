# Bitácora de Desarrollo Guiado por Especificaciones — Semana 2 (`SDD_LOG.md`) 
**Estudiante(s)**: `Kelly Johana Solano Calderón`  
**Fecha**: `2026-11-24`  
**Modelos Utilizados en OpenCode (Plan/Razonamiento vs. Build/Implementación)**: `Modelo de razonamiento: Claude Sonnet 5.5 (High) /  Modelo rápido: Claude Haiku 5.5 (Medium)` 

#### *Nota aclaratoria: Por limitaciones en la capa gratuita de OpenCode, se opta por utilizar Claude Code bajo los modelos de la capa Pro (este es un servicio del cual ya se cuenta una suscripción).*
---
## 1. Elicitación con `/speckit.clarify` y Auditoría con `/speckit.analyze` 
### 1.1 Feature `003-incident-lifecycle-sla` 


*Evidencias*
![Prompt enviado 1](img\entrega2\paso1-1.png)
![Prompt enviado 2](img\entrega2\paso1-1-1.png)


- **Ambigüedades y casos borde detectados con `/speckit.clarify`**:  Luego de ejecutar `/speckit.clarify` se encontraron los siguientes casos borde:
1) La creación de los incidentes con un estatus explicito no especifica cuales valores puede aceptar. Se explica que cuando se crea un incidente como RESOLVED no se tiene tiempo de resolución (resolved_at) entonces el SLA no puede calcularse (incluso reportar una alerta en caso de que este duplicado). La recomendación que dio el análisis fue que para el caso de incidencias con el estatus de resuelto, se rechazaran con 422 y un exit code 1. Como corrección de opta por aceptar estos incidentes, pero colocando la fecha de resolved_at = created_at.   
2) No se sabe cual es el error que debería aparecer cuando alguien registra una incidencia con un id que ya existe. Es relevante porque la especificación dice que el registro debe recharse y mantener el registro existente, pero no se menciona cuál código debería aparecer. El análisis recomienda usar un 409, que es el estándar para errores relacionados con datos existentes. Se opta por esa correccion. 
3) Los siguientes casos borde, los menciona como errores en el código que tienen discrepancias con el spec:
```
Errores que el código actual no maneja como pide el spec

1. reference_time < created_at en un incidente RESOLVED no da 422. evaluate_sla_status compara end_time = resolved_at or reference_time (src/domain/sla_calculator.py:84). En un incidente resuelto se usa resolved_at y se ignora reference_time. Con la opción B (resolved_at = created_at), el dominio devuelve 0 minutos en vez de rechazar. El servicio tendrá que validar reference_time aparte.
2. Una fecha mal escrita en el CLI sale con código 2, no 1. El comando summary declara --reference-time como datetime de Typer (src/adapters/inbound/cli.py:40). Si la fecha está mal formada, Typer/Click sale con código 2. Si create/sla copian ese patrón, no se cumple "código de salida 1".
3. El cuerpo del 422 de la API sería distinto. No hay un manejador de RequestValidationError en app.py. Si falta title, el JSON es inválido o reference_time no es ISO 8601, FastAPI responde 422 con {"detail": [...]} en lugar de {"error": ...}. El código es correcto, pero el contrato no es el mismo.
4. Fechas con zona horaria. created_at o reference_time con Z o -05:00 lanzan ValueError en el dominio (regla de hora local naive). Hay que decidir si se rechazan con 422 o se convierten, y en qué capa. Hoy el manejador genérico de la API lo convertiría en 500.
Reglas de entrada sin definir
5. incident_id enviado vacío o solo con espacios. No está definido si se autogenera o se rechaza con 422. Tampoco si aplica el máximo de 100 caracteres de MAX_INCIDENT_ID_LENGTH, ni si se recortan espacios antes de comprobar si ya existe (" INC-1" frente a "INC-1").
6. Límites de longitud. El triaje ya limita raw_text a 4000 caracteres (MAX_RAW_TEXT_LENGTH). El spec no dice si create hereda ese límite, y title no tiene ningún máximo.
7. created_at en el futuro. Una auditoría sin reference_time usaría ahora, que sería anterior a created_at, y daría 422 en la consulta por defecto. Hay que decidir si se rechaza al registrar o se acepta.

Duplicados

8. La categoría other genera falsos positivos. Dos incidentes que no tienen nada que ver, pero que caen en symptom_category = "other" del mismo componente, comparten duplicate_group_key y se marcarían como duplicados.
9. Filas anteriores con symptom_category NULL. Esa columna admite NULL (las filas sembradas en H002 pueden no tenerla), así que esos incidentes nunca se detectarían como duplicados.
10. Orden de duplicated_of. Las pruebas de paridad API/CLI exigen el mismo resultado exacto, así que el orden tiene que ser determinista (p. ej. por created_at y luego por incident_id).
11. Colisión del id autogenerado. Si un INC-<HEX8> generado ya existe, lo correcto sería reintentar en lugar de devolverle un 409 al cliente. Además, para que las pruebas sean deterministas, el generador de ids debería inyectarse igual que el reloj.

Operación y SLA

12. El CLI con la base por defecto pierde los datos entre comandos. Con DATABASE_URL por defecto (sqlite:///:memory:), create y luego sla corren en procesos distintos, y el segundo siempre da "no existe". Para usar el CLI de verdad se necesita DATABASE_URL=sqlite:///<archivo>, y el quickstart debe decirlo.
13. reference_time == created_at debe dar 0 minutos y ser válido, porque el error es solo con <. Vale la pena un escenario explícito, porque es el límite exacto de la regla.
```
- **Hallazgos o validaciones de `/speckit.analyze` antes de implementar**: `[Resumen]` 
Luego de ejecutar el análisis, no se encontraron hallazgos criticos, o violaciones de la constitución definida. Se encontró que la cobertura de los requisitos es del 96% (24/25) y que todos los campos con restricción en el modelo de datos están citados correctamente, sin contradicciones. Sin embargo se mantienen 5 hallazgos, que aunque no restringen la implementación, es importante tenerlos en cuenta:
1) La auditoría del SLA no tiene una tarea que la pruebe (es decir, no tiene un test). La nombró con FR-014 con severidad alta.
2) Cuando hay conflicto en los incidentes, cuando hay duplicados, no se verifica que la evaluación del SLA del incidente no lo modifique. La nombró como FR-013 con severidad media.
3) No exite una prueba para validar el escenario de los incidentes duplicados. Tiene severidad media.
4) Los estados IN_PROGRESS y ESCALATION_REQUIRED cuentan como duplicado abierto pero no se utilizan en ninguna prueba. Tiene severidad media.
5) La convención de numeración de tareas tiene una inconsistencia con las tareas T013 y la TO025, porque estas tienen una dependencia.

El resumen generado por Claude fue:

```
Análisis de H003 (/speckit-analyze): 0 hallazgos CRITICAL, sin violaciones de la Constitución. Cobertura de requisitos: 96% (24/25 FR+SC con al menos una tarea). Todos los campos con restricción de data-model.md quedaron citados correctamente, sin contradicciones. No hay duplicaciones, ambigüedades ni placeholders sin resolver. Se encontraron 5 hallazgos: 1 HIGH — FR-014 (idempotencia/sin efectos de la auditoría de SLA) sin ninguna prueba. 3 MEDIUM — FR-013 cubierto solo a medias (falta probar que evaluate_incident_sla no modifica el incidente); el caso de múltiples duplicados simultáneos nunca se prueba; los estados IN_PROGRESS/ESCALATION_REQUIRED como duplicado abierto tampoco se prueban (solo OPEN). 1 LOW — T013 depende de una tarea numerada después (T025), ordenamiento documentado pero atípico. Ninguno bloquea /speckit-implement; son brechas de pruebas, no de diseño.
```
![Pruebas](img\entrega2\paso1-3.png)

### 1.2 Feature `004-postgres-container-runtime` 
- **Ambigüedades y RNF aclarados antes de diseñar PostgreSQL/Compose**: Al definir los requeirmientos funcionales para la parte de PostgreSQL, no se encontraron ambigüedades que fueran bloqueantes, dado que todas tenian valores por defecto razonales y que fueron considerados por el modelo como de "bajo riesgo". No obstante, los siguientes items se marcaron como supuesto:
1) Código de salida del comando CLI health ante fallo
2) Parámetros de healthcheck en docker-compose.yml (interval, timeout, retries,
start_period) para pg_isready y para GET /health
3) Tipo de volumen persistente de db (volumen nombrado de Docker vs. bind mount a una ruta
del host)
4) Momento en que se rechaza un esquema de DATABASE_URL no soportado (al arrancar vs. en el
primer request)
5) Si el chequeo de salud puede cachear o debounce su resultado (p. ej. para no golpear la
base en cada ping de un orquestador)
6) Migración de datos existentes de SQLite hacia PostgreSQL al adoptar el nuevo motor
Por qué era ambigua: Tu descripción no la menciona, pero es una duda natural al introducir un segundo motor en un proyecto que ya tenía datos en SQLite.
7) Autenticación/autorización sobre GET /health y el comando health
8) Comportamiento si la base de datos cae después de un arranque exitoso (no solo en el
arranque inicial)
9) Alcance de "aislamiento de la imagen" (.dockerignore) — qué se excluye exactamente.

Gran parte de estos supuestos fueron interpretados por el modelo, infiendo paridades o valores por defecto según la estructura y decisiones previas en el proyecto. Acá se puede mencionar que, a pesar de no especificar determinados comportamientos de las deciiones (por ejemplo, sobre los errores, su tratamiento, la inclusión o exclusión de ciertas características), el modelo ayuda a interpretar según la estructura global. No obstante, es importante SIEMPRE validar las decisiones que toma. 

Por ejemplo, para pasar a la implementación, el modelo mencionaba que:

```
Ningún hallazgo es CRITICAL, así que puedes proceder a /speckit-implement, pero recomiendo resolver G1 y G2 primero (son huecos reales de verificación sobre requisitos core, FR-006/RNF-003) añadiéndolos a tasks.md antes de implementar — son 2 tests pequeños, no cambian el diseño. I1/I2/I3 son correcciones de texto de 1 línea cada una.
```

Estas tareas eran las de la falta de verificación de paridad cruzda y el que no tenía test de transicion de estado. (las tasks T018, T006, T008, T009). Antes estas se autoriza la creación de una tarea adicional (la T030) para incluir esas pruebas específicas. 


---
## 2. Comparación Crítica: SDD Manual (Iteración 1) vs. GitHub Spec Kit (Iteración 2 y Retos) 

| Dimensión Comparada | SDD Manual (Iteración 1: `001`) | GitHub Spec Kit (Iteración 2 y Retos: `002`–`004`) | 
| :--- | :--- | :--- | 
| **Separación *QUÉ* vs. *CÓMO* vs. *TAREAS*** | En el SDD no hubo una separación concreta a cada pregunta, porque todo va en un documento que mezcla el qué (dentro de un contrato, una definición de la solicitud y un formato de SLA) y el cómo bajo una sección de arquitectura. A nivel de tareas, se definen a través de un alcance, que no específica, por ejemplo las tecnologías que se van a usar. Algo que sucedió con este tipo de enfoque, fue que las correcciones o enmiendas no quedaron directamente definidas dentro del mismo archivo de arquitectura, sino fue necesario crear un archivo de especficación. | Usando esta estrategia, se tuvo una separación estructural, por lo que cada decisión, a nivel de especificaciones, plan y tareas, iba en un archivo aparte, con un formato concreto que podía ser escalable entre las iteraciones. | 
| **Gestión de ambigüedades (`/speckit.clarify`)** | Las consideraciones encontradas se registraban directamente en la construcción del documento, como revisiones a las decisiones tomadas. No hubo un proceso de clarificación antes del diseño, sino más bien, una modificación a lo implementado. | Cuando se usaba /speckit.clarify se logró construir una sección de Clarificaciones dentro del spec.md, con el razonamiento detras de cada una. Esto fue bueno, porque se lograron encontrar discrepancias que no se habían dejado por escrito dentro del código. | 
| **Consistencia contra la Constitución (`/speckit.analyze`)** | Los dos documentos que se crearon manualmente (el de constitution.md y el de arquitectura hexagonal) no lograron compararse mutuamente, porque uno se creo después que el otro. Nuevamente pasó lo de las enmiendas, que en un caso donde se quisiera comprobarl el cumplimiento, se tendría que confiar que todas las decisiones estuvieran en él, sin tener en cuenta severidades, o consideraciones relevantes. | Como las constituciones se toman como definiciones estrictas basadas en los documentos de spec, plan y tasks, todo debe cumplirse al ser crítico por definición, y si existieran discrepancia, sería necesario volver a considerar todo el flujo de la decisión. | 
| **Riesgo de verbosidad / exceso de Markdown** | Se creó un solo documento que mezcla qué, cómo y tareas, La arquitectura se complementó como una enmienda tardía. Las ambigüedades se resuelven después de implementar, sin rastro versionado, y no existe ningún documento no-negociable contra el cual verificarse. Es compacto, pero ese mismo tamaño reducido esconde omisiones que solo aparecen como bugs o parches posteriores. | Separó los documentos spec/plan/tasks con trazabilidad explícita, versionó las ambigüedades resueltas (Clarifications) y trató cualquier choque con la Constitución como CRITICAL automático. El costo es volumen y duplicación entre archivos, pero ese riesgo es gestionable con /speckit-clarify y /speckit-analyze. | 


- **Análisis basado en MartinFowler.com (Birgitta Böckeler)**:
1. De los tres niveles descritos por Böckeler (**Spec-first**, **Spec-anchored**, 
**Spec-as-source**), ¿en cuál ubicas este proyecto de *IncidentOps* y por qué?

Aunque durante la práctica se aplicó el Speckit, que sigue una definicion "spec-first", considero que el comportamiento que se tuvo, orienda más a un "spec-anchored". En sí, la práctica real orientó a que el código debe mantenerse, enmendarse según los requerimientos que vayan surgiendo y re-auditar las especificaciones después de implementar, lo cuál permite que conjuntamente, definiciones y código, puedan evolucionar a lo largo del ciclo de vida del software (de forma manual, con las correcciones y con Spec-kit, en las clarificaciones). Cada uno de los artefactos puede interpretarse como referencias vivas que cambian conforme el proyecto se refina, por lo tanto, no son desechables ni se pierden con el tiempo. 

2. Böckeler advierte que los *toolkits* SDD pueden generar "montañas de Markdown" 
difíciles de revisar para un humano. ¿Qué técnicas aplicaste (concisión en 
`docs/ROADMAP.md`, curaduría en `clarify`/`plan`/`tasks` y pruebas deterministas en 
`pytest`) para evitar aprobar especificaciones verbosas a ciegas? 

Algunas de las técnicas aplicadas fueron:
- A nivel de alcance, cada mención de límites se argumentó dentro del spec.md utilizando su referencia, lo cual evitaba que se tuviera que re-especficiar la decisión en este archivo.
- En la curaduría que se hacía con clarify/plan/tasks, se definió un limite de especificación, priorizando los elementos relacionados con alcance, seguridad, UX y detalle técnico. Se filtró y la mayoría se dejaron como supuestos en una sola línea (supuesto que no introducian riesgo).
- En el documento del plan.md, cuando no se tenian objetivos de rendimiento, simplemente se escribía que "no se definieron metas cuantitativas", para no inventar un presupuesto de rendimiento que no se había mencionado.
- En el análisis, se acota a máximo 50 hallazgos, únicamente de discrepancias entre los archivos. 
- En las pruebas deterministicas, se corrieron contra SQLiten en memoria, lo que no tenia dependencia a red o a un Postgres real. Cada elemento documentado que menciona, el número de funciones nuevas, o los resultados de los test, se comprobaron primero con los comandos, sin dejar simplemente parrafos en prosa. 

---
## 3. *Commands* vs. *Agent Skills*, Arquitectura Hexagonal, ADRs y Uso de *Reasoning* 
- **Diferencia entre *Commands* (`/speckit.*`) y *Agent Skills* (`hexagonal-
architecture`, `bdd-acceptance`, `adr-writer`)**: Explica cómo OpenCode carga las 
*skills* bajo demanda y por qué fue necesario seguir el orden causal ADR $\rightarrow$ 
Constitución $\rightarrow$ Hito tanto en clase (`ADR-003` antes de 
`docs/constitution.md`) como en el Reto 2 (`ADR-004` y actualización de 
`.specify/memory/constitution.md` antes de especificar e implementar el Hito `004`).

Los comandos de speckit son pasos específicos del flujo que relacionan momentos del ciclo de la funcionalidad. Esto corren en un script de setup y pueden leer/escribir artefactos versionados de la carpeta specs/. Por otro lado, las agent skills, no o son pasos de un pipeline, sino conocimiento de referencia que Claude va usando bajo demanda. En este caso, cada skill tiene su descripción, que es comparada con la tarea que le estamos solictando (editar el domain o crear un adr). Respecto al orden causal, fue fundamental porque la constitución define que cualquier decisión que contenga, debe estar derivada de los ADRs. Ahí es donde se argumentan las alternativas y los trade-offs. Además, la parte de plan y análisis toman este documento como una ley, por lo tanto, se deben seguir los pasos para poder obtener cada artefacto y que sea utilizado por el siguiente paso. 

- **Valor de la Arquitectura Hexagonal**: Explica cómo compartir `IncidentService` e 
`IncidentRepositoryPort` facilitó exponer FastAPI, Typer y el adaptador PostgreSQL sin 
tocar el dominio (y cómo prepara la incorporación de futuros adaptadores). 

El `IncidentService` y el `IncidentRepositoryPort` son el punto de contacto entre la lógica de negocio y la persistencia. A nivel de código, se definen de una manera, en la que, independientemente del repositorio que se tome, sea SQLLite o Postgres, siempre se use un esquema de DATABASE_URL, donde se implementan exactamente el protocolo IncidentRepositoryPort, con los mismos métodos. Por esta razón, cuando se incorporó Postgress, no hubo necesidad de modificar el domain, ni la lógica detrás, porque solo se agregaba el repositorio y se extendía. En el caso de FastAPI o Typer, tampoco cambiaron, porque seguían llamando los mismos métodos y servicios. Aunqeu a nivel de arquitectura existan más archivos, se facilita la integración de futuros adaptadores, como MCPs, u otro motor de persistencia. 

- **Uso intencional de *Reasoning / Extended Thinking* en OpenCode**: ¿En qué comandos 
(`/speckit.clarify`, `/speckit.plan`, `/speckit.analyze`) aportó mayor valor el 
razonamiento extendido y en cuáles (`/speckit.implement`) resultó más eficiente un 
modelo rápido? 

Los comando en lo que se requieren tareas de exploración, análisis y propuesta de ejecución  fueron mucho más efectivas ejecutarlas con los modelos de razonamiento, dadas su capacidades de razonamiento frente al código, las decisiones arquitectónicas y el cumplimiento de requerimientos. Con ellos, se lograron identificar casos borde que e habían omitido en la versión de la semana 1, y que para los cambios de esta no se hab ían resuelto. Como los artefactos construidos fueron amplios y detallados, usar un modelo rápido fue más efectivo. Se aclara que esto también es desde el lado de tiempo y consumo de tokens, dado que en este caso se definieron al final 30 tareas, que so no se ubiera utilizado un modelo rápido, la duración de implementación hubiera sido mucho más tardada (>9min que le tomo a Sonnet, en comparación a Opus).

---
## 4. Evidencia de Verificación Determinista 
- **Análisis estático de fronteras hexagonales (`uv run ruff check src/`)**: 
```text 
PS C:\Users\USUARIO\Documents\DIPLOMADO\MODULO 3\Taller autonomo\week-1\starter-project> uv run ruff check src/ 
All checks passed!
``` 
![Evidencia 1](img\entrega2\final-1.png)

- **Salida completa de `uv run pytest -v`**: 
```text 
PS C:\Users\USUARIO\Documents\DIPLOMADO\MODULO 3\Taller autonomo\week-1\starter-project> uv run pytest -v 
============================================= test session starts ==============================================
platform win32 -- Python 3.14.3, pytest-9.2.0, pluggy-1.7.0 -- C:\Users\USUARIO\Documents\DIPLOMADO\MODULO 3\Taller autonomo\week-1\starter-project\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\USUARIO\Documents\DIPLOMADO\MODULO 3\Taller autonomo\week-1\starter-project
configfile: pyproject.toml
testpaths: tests
plugins: anyio-4.16.0
collected 30 items                                                                                              

tests/test_spec_001_triage.py::test_caida_critica_http_502_en_pasarela_de_pagos PASSED                    [  3%]
tests/test_spec_001_triage.py::test_cuenta_individual_bloqueada_mencionando_hoy PASSED                    [  6%]
tests/test_spec_001_triage.py::test_entradas_vacias_o_con_solo_espacios PASSED                            [ 10%]
tests/test_spec_001_triage.py::test_paridad_en_cli PASSED                                                 [ 13%]
tests/test_spec_002_summary.py::test_bdd_resumen_http_incluye_incumplimientos_y_excluye_resueltos PASSED  [ 16%]
tests/test_spec_002_summary.py::test_bdd_resumen_http_vacio_sin_incidentes_activos PASSED                 [ 20%]
tests/test_spec_002_summary.py::test_bdd_incidente_vencido_se_cuenta_como_incumplimiento_http PASSED      [ 23%]
tests/test_spec_002_summary.py::test_bdd_paridad_resumen_http_cli_mismo_conjunto PASSED                   [ 26%]
tests/test_spec_002_summary.py::test_bdd_resumen_cli_vacio_sin_incidentes_activos PASSED                  [ 30%]
tests/test_spec_002_summary.py::test_bdd_filtro_por_componente_limita_resumen PASSED                      [ 33%]
tests/test_spec_002_summary.py::test_bdd_filtro_componente_sin_incidentes_activos PASSED                  [ 36%]
tests/test_spec_002_summary.py::test_bdd_sin_filtro_incluye_todos_los_componentes PASSED                  [ 40%]
tests/test_spec_002_summary.py::test_bdd_sqlite_incident_repository_cumple_el_puerto PASSED               [ 43%]
tests/test_spec_002_summary.py::test_bdd_resumen_es_solo_lectura_sin_efectos_secundarios PASSED           [ 46%]
tests/test_spec_002_summary.py::test_bdd_resumen_responde_en_menos_de_dos_segundos_con_cien_incidentes PASSED [ 50%]
tests/test_spec_004_runtime_health.py::test_bdd_health_http_200_conectado PASSED                          [ 53%]
tests/test_spec_004_runtime_health.py::test_bdd_health_http_503_doble_de_prueba PASSED                    [ 56%]
tests/test_spec_004_runtime_health.py::test_bdd_health_cli_exit0_conectado PASSED                         [ 60%]
tests/test_spec_004_runtime_health.py::test_bdd_health_cli_exit1_no_disponible PASSED                     [ 63%]
tests/test_spec_004_runtime_health.py::test_bdd_health_http_idempotente_repetible PASSED                  [ 66%]
tests/test_spec_004_runtime_health.py::test_bdd_health_http_refleja_cambio_de_estado_sin_cache PASSED     [ 70%]
tests/test_spec_004_runtime_health.py::test_sqlite_repository_cumple_incident_repository_port PASSED      [ 73%]
tests/test_spec_004_runtime_health.py::test_postgres_repository_cumple_incident_repository_port_estructural PASSED [ 76%]
tests/test_spec_004_runtime_health.py::test_create_repository_esquema_sqlite PASSED                       [ 80%]
tests/test_spec_004_runtime_health.py::test_get_incident_repository_sin_database_url_usa_sqlite_memoria PASSED [ 83%]
tests/test_spec_004_runtime_health.py::test_create_repository_esquema_postgresql_selecciona_adaptador PASSED [ 86%]
tests/test_spec_004_runtime_health.py::test_create_repository_esquema_no_soportado_lanza_valueerror PASSED [ 90%]
tests/test_spec_004_runtime_health.py::test_dockerfile_usa_python312_slim_y_uv PASSED                     [ 93%]
tests/test_spec_004_runtime_health.py::test_dockerignore_excluye_entornos_virtuales_y_artefactos_de_prueba PASSED [ 96%]
tests/test_spec_004_runtime_health.py::test_docker_compose_declara_api_y_db_con_healthchecks_y_depends_on PASSED [100%]

=============================================== warnings summary ===============================================
.venv\Lib\site-packages\fastapi\testclient.py:1
  C:\Users\USUARIO\Documents\DIPLOMADO\MODULO 3\Taller autonomo\week-1\starter-project\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================================== 30 passed, 1 warning in 0.22s =========================================
``` 

![Evidencia 2](img\entrega2\final-2.png)


```
PS C:\Users\USUARIO\Documents\DIPLOMADO\MODULO 3\Taller autonomo\week-1\starter-project> uv run python -m src.adapters.inbound.cli health 
{"status": "ok", "database": "connected"}
```

![Evidencia 3](img\entrega2\final-3.png)

- **Evidencia de CLI Typer y containerización (`docker compose config` / `docker compose 
up --build`)**: 
```text
PS C:\Users\USUARIO\Documents\DIPLOMADO\MODULO 3\Taller autonomo\week-1\starter-project> docker compose config -q; if ($?) { echo "Compose OK" }
Compose OK 
```

**Intento de `docker compose up --build` (2026-11-24)**: al ejecutar el comando real para
levantar el stack, Docker Desktop no tenía el daemon en ejecución en esta máquina:

```text
PS C:\Users\USUARIO\Documents\DIPLOMADO\MODULO 3\Taller autonomo\week-1\starter-project> docker compose up --build
failed to connect to the docker API at npipe:////./pipe/dockerDesktopLinuxEngine; check if the path is correct and
if the daemon is running: open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file specified.
```

Esto **no es un defecto de `docker-compose.yml`**: es un problema de entorno (Docker
Desktop instalado pero no iniciado/el servicio del daemon no está corriendo), no del
contenido del archivo. Como evidencia de que la definición del stack es válida en sí
misma —`docker compose config` solo parsea y resuelve el archivo, no requiere que el
daemon esté activo—, se vuelve a ejecutar con la salida completa:

```text
PS C:\Users\USUARIO\Documents\DIPLOMADO\MODULO 3\Taller autonomo\week-1\starter-project> docker compose config
name: starter-project
services:
  api:
    build:
      context: C:\Users\USUARIO\Documents\DIPLOMADO\MODULO 3\Taller autonomo\week-1\starter-project
      dockerfile: Dockerfile
    depends_on:
      db:
        condition: service_healthy
        required: true
    environment:
      DATABASE_URL: postgresql://incidentops:incidentops@db:5432/incidentops
    healthcheck:
      test:
        - CMD
        - python
        - -c
        - import urllib.request; urllib.request.urlopen('http://localhost:8000/health')
      timeout: 5s
      interval: 5s
      retries: 5
      start_period: 5s
    networks:
      default: null
    ports:
      - mode: ingress
        target: 8000
        published: "8000"
        protocol: tcp
  db:
    environment:
      POSTGRES_DB: incidentops
      POSTGRES_PASSWORD: incidentops
      POSTGRES_USER: incidentops
    healthcheck:
      test:
        - CMD-SHELL
        - pg_isready -U incidentops -d incidentops
      timeout: 5s
      interval: 5s
      retries: 5
      start_period: 5s
    image: postgres:16-alpine
    networks:
      default: null
    volumes:
      - type: volume
        source: pgdata
        target: /var/lib/postgresql/data
        volume: {}
networks:
  default:
    name: starter-project_default
volumes:
  pgdata:
    name: starter-project_pgdata
```

Esto confirma que `depends_on: db: condition: service_healthy` (FR-011), el healthcheck
de `db` con `pg_isready` (FR-010), el volumen nombrado `pgdata` (RNF-006) y el
`DATABASE_URL` de `api` apuntando a `db:5432` (FR-005) quedan resueltos exactamente como
describe `specs/004-postgres-container-runtime/data-model.md`. 

- **Salida de `uv run pytest -v` tras el intento de `docker compose up --build`**: se
repite la ejecución completa para confirmar que el fallo del daemon de Docker no afecta
en nada la suite determinista (no depende de contenedores):

```text
PS C:\Users\USUARIO\Documents\DIPLOMADO\MODULO 3\Taller autonomo\week-1\starter-project> uv run pytest -v
============================= test session starts =============================
platform win32 -- Python 3.14.3, pytest-9.2.0, pluggy-1.7.0 -- C:\Users\USUARIO\Documents\DIPLOMADO\MODULO 3\Taller autonomo\week-1\starter-project\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\USUARIO\Documents\DIPLOMADO\MODULO 3\Taller autonomo\week-1\starter-project
configfile: pyproject.toml
testpaths: tests
plugins: anyio-4.16.0
collecting ... collected 30 items

tests/test_spec_001_triage.py::test_caida_critica_http_502_en_pasarela_de_pagos PASSED [  3%]
tests/test_spec_001_triage.py::test_cuenta_individual_bloqueada_mencionando_hoy PASSED [  6%]
tests/test_spec_001_triage.py::test_entradas_vacias_o_con_solo_espacios PASSED [ 10%]
tests/test_spec_001_triage.py::test_paridad_en_cli PASSED                [ 13%]
tests/test_spec_002_summary.py::test_bdd_resumen_http_incluye_incumplimientos_y_excluye_resueltos PASSED [ 16%]
tests/test_spec_002_summary.py::test_bdd_resumen_http_vacio_sin_incidentes_activos PASSED [ 20%]
tests/test_spec_002_summary.py::test_bdd_incidente_vencido_se_cuenta_como_incumplimiento_http PASSED [ 23%]
tests/test_spec_002_summary.py::test_bdd_paridad_resumen_http_cli_mismo_conjunto PASSED [ 26%]
tests/test_spec_002_summary.py::test_bdd_resumen_cli_vacio_sin_incidentes_activos PASSED [ 30%]
tests/test_spec_002_summary.py::test_bdd_filtro_por_componente_limita_resumen PASSED [ 33%]
tests/test_spec_002_summary.py::test_bdd_filtro_componente_sin_incidentes_activos PASSED [ 36%]
tests/test_spec_002_summary.py::test_bdd_sin_filtro_incluye_todos_los_componentes PASSED [ 40%]
tests/test_spec_002_summary.py::test_bdd_sqlite_incident_repository_cumple_el_puerto PASSED [ 43%]
tests/test_spec_002_summary.py::test_bdd_resumen_es_solo_lectura_sin_efectos_secundarios PASSED [ 46%]
tests/test_spec_002_summary.py::test_bdd_resumen_responde_en_menos_de_dos_segundos_con_cien_incidentes PASSED [ 50%]
tests/test_spec_004_runtime_health.py::test_bdd_health_http_200_conectado PASSED [ 53%]
tests/test_spec_004_runtime_health.py::test_bdd_health_http_503_doble_de_prueba PASSED [ 56%]
tests/test_spec_004_runtime_health.py::test_bdd_health_cli_exit0_conectado PASSED [ 60%]
tests/test_spec_004_runtime_health.py::test_bdd_health_cli_exit1_no_disponible PASSED [ 63%]
tests/test_spec_004_runtime_health.py::test_bdd_health_http_idempotente_repetible PASSED [ 66%]
tests/test_spec_004_runtime_health.py::test_bdd_health_http_refleja_cambio_de_estado_sin_cache PASSED [ 70%]
tests/test_spec_004_runtime_health.py::test_sqlite_repository_cumple_incident_repository_port PASSED [ 73%]
tests/test_spec_004_runtime_health.py::test_postgres_repository_cumple_incident_repository_port_estructural PASSED [ 76%]
tests/test_spec_004_runtime_health.py::test_create_repository_esquema_sqlite PASSED [ 80%]
tests/test_spec_004_runtime_health.py::test_get_incident_repository_sin_database_url_usa_sqlite_memoria PASSED [ 83%]
tests/test_spec_004_runtime_health.py::test_create_repository_esquema_postgresql_selecciona_adaptador PASSED [ 86%]
tests/test_spec_004_runtime_health.py::test_create_repository_esquema_no_soportado_lanza_valueerror PASSED [ 90%]
tests/test_spec_004_runtime_health.py::test_dockerfile_usa_python312_slim_y_uv PASSED [ 93%]
tests/test_spec_004_runtime_health.py::test_dockerignore_excluye_entornos_virtuales_y_artefactos_de_prueba PASSED [ 96%]
tests/test_spec_004_runtime_health.py::test_docker_compose_declara_api_y_db_con_healthchecks_y_depends_on PASSED [100%]

============================== warnings summary ===============================
.venv\Lib\site-packages\fastapi\testclient.py:1
  C:\Users\USUARIO\Documents\DIPLOMADO\MODULO 3\Taller autonomo\week-1\starter-project\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
======================== 30 passed, 1 warning in 0.17s =========================
```



Docker compose

```
PS C:\Users\USUARIO\Documents\DIPLOMADO\MODULO 3\Taller autonomo\week-1\starter-project> docker compose up --build 
[+] up 13/13
 ✔ Image postgres:16-alpine Pulled                                                      7.9s
[+] Building 9.6s (15/15) FINISHED
 => [internal] load local bake definitions                                             0.0s
 => => reading from stdin 641B                                                         0.0s
 => [internal] load build definition from Dockerfile                                   0.0s
 => => transferring dockerfile: 592B                                                   0.0s
 => [internal] load metadata for ghcr.io/astral-sh/uv:latest                           1.5s
 => [internal] load metadata for docker.io/library/python:3.12-slim                    1.3s
 => [internal] load .dockerignore                                                      0.0s
 => => transferring context: 160B                                                      0.0s 
 => FROM ghcr.io/astral-sh/uv:latest@sha256:d3b601f0c7b118bc1753febf7c41cc80981df6784  1.7s 
 => => resolve ghcr.io/astral-sh/uv:latest@sha256:d3b601f0c7b118bc1753febf7c41cc80981  0.0s 
 => => sha256:6194b0176b3040f6b7ddcb49a3eb00c776bd1c508e0012f743d1d 19.60MB / 19.60MB  1.3s 
 => => sha256:738af053281ffefe1f1e338797802de818be2055e29d46d982b10d1605f2e 98B / 98B  0.4s 
 => => extracting sha256:6194b0176b3040f6b7ddcb49a3eb00c776bd1c508e0012f743d1d9dc2611  0.3s 
 => => extracting sha256:738af053281ffefe1f1e338797802de818be2055e29d46d982b10d1605f2  0.0s 
 => [internal] load build context                                                      0.1s
 => => transferring context: 455.39kB                                                  0.0s
 => [stage-0 1/6] FROM docker.io/library/python:3.12-slim@sha256:191083cdf6c7bda8c761  3.4s 
 => => resolve docker.io/library/python:3.12-slim@sha256:191083cdf6c7bda8c76158983163  0.0s 
 => => sha256:286d8c291daa64125703b22c3d009462bcae0b630eaa16ad5b934502c49 248B / 248B  0.1s 
 => => sha256:e3e428093f5e80791498526d73a46eabf0e69575dc10897cf47aa 12.12MB / 12.12MB  1.0s 
 => => sha256:30cf67d7101c07c55eef20970bc403fbde5f8600c2c4c38b4881a2d 1.29MB / 1.29MB  0.6s
 => => sha256:40748add9f4f6f944f334cbfc286590d6e93f60fb06f6ee7ffa1b 29.84MB / 29.84MB  1.8s
 => => extracting sha256:40748add9f4f6f944f334cbfc286590d6e93f60fb06f6ee7ffa1b894080a  0.9s
 => => extracting sha256:30cf67d7101c07c55eef20970bc403fbde5f8600c2c4c38b4881a2da4fff  0.1s
 => => extracting sha256:e3e428093f5e80791498526d73a46eabf0e69575dc10897cf47aa99120e4  0.5s 
 => => extracting sha256:286d8c291daa64125703b22c3d009462bcae0b630eaa16ad5b934502c491  0.0s 
 => [stage-0 2/6] COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv        0.5s 
 => [stage-0 3/6] WORKDIR /app                                                         0.0s 
 => [stage-0 4/6] COPY pyproject.toml uv.lock ./                                       0.0s 
 => [stage-0 5/6] RUN uv sync --frozen --no-dev                                        1.1s 
 => [stage-0 6/6] COPY src/ ./src/                                                     0.1s 
 => exporting to image                                                                 2.5s 
 => => exporting layers                                                                1.5s
 => => exporting manifest sha256:bf25848a2d53fc215fa14f82979943e732ebaabf8617d14a4eb7  0.0s 
 => => exporting config sha256:52b50f82b960c630ab400c8d2247644a2c0adc706be51d7f82171b  0.0s 
 => => exporting attestation manifest sha256:3640324d5819192828be3e3eb5dfcebc8157d609  0.0s 
 => => exporting manifest list sha256:f1275db5f5ea8a362b52a19b2c5732160bfeb86facfea16  0.0s 
 => => naming to docker.io/library/starter-project-api:latest                          0.0s 
[+] up 18/18king to docker.io/library/starter-project-api:latest                       0.9s 
 ✔ Image postgres:16-alpine        Pulled                                               7.9s
 ✔ Image starter-project-api       Built                                                9.9s
 ✔ Network starter-project_default Created                                              0.0s
 ✔ Volume starter-project_pgdata   Created                                              0.0s
 ✔ Container starter-project-db-1  Created                                              0.1s
 ✔ Container starter-project-api-1 Created                                              0.1s
Attaching to api-1, db-1
Container starter-project-db-1 Waiting 
db-1  | The files belonging to this database system will be owned by user "postgres".       
db-1  | This user must also own the server process.
db-1  | 
db-1  | The database cluster will be initialized with locale "en_US.utf8".                  
db-1  | The default database encoding has accordingly been set to "UTF8".                   
db-1  | The default text search configuration will be set to "english".
db-1  |                                                                                     
db-1  | Data page checksums are disabled.                                                   
db-1  | 
db-1  | fixing permissions on existing directory /var/lib/postgresql/data ... ok            
db-1  | creating subdirectories ... ok                                                      
db-1  | selecting dynamic shared memory implementation ... posix                            
db-1  | selecting default max_connections ... 100
db-1  | selecting default shared_buffers ... 128MB                                          
db-1  | selecting default time zone ... UTC                                                 
db-1  | creating configuration files ... ok
db-1  | running bootstrap script ... ok                                                     
db-1  | sh: locale: not found
db-1  | 2026-11-24 21:04:33.904 UTC [35] WARNING:  no usable system locales were found
db-1  | performing post-bootstrap initialization ... ok                                     
db-1  | initdb: warning: enabling "trust" authentication for local connections
db-1  | initdb: hint: You can change this by editing pg_hba.conf or using the option -A, or --auth-local and --auth-host, the next time you run initdb.                                 
db-1  | syncing data to disk ... ok
db-1  |                                                                                     
db-1  |                                                                                     
db-1  | Success. You can now start the database server using:                               
db-1  |                                                                                     
db-1  |     pg_ctl -D /var/lib/postgresql/data -l logfile start                             
db-1  |                                                                                     
db-1  | waiting for server to start....2026-11-24 21:04:34.525 UTC [41] LOG:  starting PostgreSQL 16.16 on x86_64-pc-linux-musl, compiled by gcc (Alpine 15.2.0) 15.2.0, 64-bit
db-1  | 2026-11-24 21:04:34.527 UTC [41] LOG:  listening on Unix socket "/run/postgresql/.s.PGSQL.5432"                                                                                 
db-1  | 2026-11-24 21:04:34.533 UTC [44] LOG:  database system was shut down at 2026-11-24 21:04:34 UTC                                                                                 
db-1  | 2026-11-24 21:04:34.537 UTC [41] LOG:  database system is ready to accept connections                                                                                           
db-1  |  done
db-1  | server started
db-1  | CREATE DATABASE                                                                     
db-1  | 
db-1  |                                                                                     
db-1  | /usr/local/bin/docker-entrypoint.sh: ignoring /docker-entrypoint-initdb.d/*         
db-1  | 
db-1  | waiting for server to shut down....2026-11-24 21:04:34.666 UTC [41] LOG:  received fast shutdown request                                                                        
db-1  | 2026-11-24 21:04:34.668 UTC [41] LOG:  aborting any active transactions
db-1  | 2026-11-24 21:04:34.670 UTC [41] LOG:  background worker "logical replication launcher" (PID 47) exited with exit code 1                                                        
db-1  | 2026-11-24 21:04:34.670 UTC [42] LOG:  shutting down
db-1  | 2026-11-24 21:04:34.672 UTC [42] LOG:  checkpoint starting: shutdown immediate      
db-1  | 2026-11-24 21:04:34.746 UTC [42] LOG:  checkpoint complete: wrote 935 buffers (5.7%); 0 WAL file(s) added, 0 removed, 0 recycled; write=0.024 s, sync=0.045 s, total=0.076 s; sync files=301, longest=0.007 s, average=0.001 s; distance=4355 kB, estimate=4355 kB; lsn=0/1949CE0, redo lsn=0/1949CE0
db-1  | 2026-11-24 21:04:34.753 UTC [41] LOG:  database system is shut down
db-1  |  done                                                                               
db-1  | server stopped
db-1  |                                                                                     
db-1  | PostgreSQL init process complete; ready for start up.                               
db-1  |                                                                                     
db-1  | 2026-11-24 21:04:34.795 UTC [1] LOG:  starting PostgreSQL 16.16 on x86_64-pc-linux-musl, compiled by gcc (Alpine 15.2.0) 15.2.0, 64-bit
db-1  | 2026-11-24 21:04:34.795 UTC [1] LOG:  listening on IPv4 address "0.0.0.0", port 5432
db-1  | 2026-11-24 21:04:34.795 UTC [1] LOG:  listening on IPv6 address "::", port 5432
db-1  | 2026-11-24 21:04:34.799 UTC [1] LOG:  listening on Unix socket "/run/postgresql/.s.PGSQL.5432"                                                                                  
db-1  | 2026-11-24 21:04:34.803 UTC [57] LOG:  database system was shut down at 2026-11-24 21:04:34 UTC                                                                                 
db-1  | 2026-11-24 21:04:34.808 UTC [1] LOG:  database system is ready to accept connections
Container starter-project-db-1 Healthy                                                      
api-1  | Downloading ruff (10.2MiB)
api-1  |  Downloaded ruff
api-1  | Installed 7 packages in 17ms
api-1  | INFO:     Started server process [33]
api-1  | INFO:     Waiting for application startup.
api-1  | INFO:     Application startup complete.                                            
api-1  | INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)            
api-1  | INFO:     127.0.0.1:34164 - "GET /health HTTP/1.1" 200 OK                          
api-1  | INFO:     127.0.0.1:34178 - "GET /health HTTP/1.1" 200 OK
api-1  | INFO:     127.0.0.1:35042 - "GET /health HTTP/1.1" 200 OK
api-1  | INFO:     127.0.0.1:35056 - "GET /health HTTP/1.1" 200 OK
```

![Evidencia 4](img\entrega2\final-4.png)