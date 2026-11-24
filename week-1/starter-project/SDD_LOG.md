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
| **Separación *QUÉ* vs. *CÓMO* vs. *TAREAS*** |/sp | | 
| **Gestión de ambigüedades (`/speckit.clarify`)** | | | 
| **Consistencia contra la Constitución (`/speckit.analyze`)** | | | 
| **Riesgo de verbosidad / exceso de Markdown** | | | 


- **Análisis basado en MartinFowler.com (Birgitta Böckeler)**:
1. De los tres niveles descritos por Böckeler (**Spec-first**, **Spec-anchored**, 
**Spec-as-source**), ¿en cuál ubicas este proyecto de *IncidentOps* y por qué?



2. Böckeler advierte que los *toolkits* SDD pueden generar "montañas de Markdown" 
difíciles de revisar para un humano. ¿Qué técnicas aplicaste (concisión en 
`docs/ROADMAP.md`, curaduría en `clarify`/`plan`/`tasks` y pruebas deterministas en 
`pytest`) para evitar aprobar especificaciones verbosas a ciegas? 



---
## 3. *Commands* vs. *Agent Skills*, Arquitectura Hexagonal, ADRs y Uso de *Reasoning* 
- **Diferencia entre *Commands* (`/speckit.*`) y *Agent Skills* (`hexagonal-
architecture`, `bdd-acceptance`, `adr-writer`)**: Explica cómo OpenCode carga las 
*skills* bajo demanda y por qué fue necesario seguir el orden causal ADR $\rightarrow$ 
Constitución $\rightarrow$ Hito tanto en clase (`ADR-003` antes de 
`docs/constitution.md`) como en el Reto 2 (`ADR-004` y actualización de 
`.specify/memory/constitution.md` antes de especificar e implementar el Hito `004`).



- **Valor de la Arquitectura Hexagonal**: Explica cómo compartir `IncidentService` e 
`IncidentRepositoryPort` facilitó exponer FastAPI, Typer y el adaptador PostgreSQL sin 
tocar el dominio (y cómo prepara la incorporación de futuros adaptadores). 



- **Uso intencional de *Reasoning / Extended Thinking* en OpenCode**: ¿En qué comandos 
(`/speckit.clarify`, `/speckit.plan`, `/speckit.analyze`) aportó mayor valor el 
razonamiento extendido y en cuáles (`/speckit.implement`) resultó más eficiente un 
modelo rápido? 

Los comando en lo que se requieren tareas de exploración, análisis y propuesta de ejecución  fueron mucho más efectivas ejecutarlas con los modelos de razonamiento, dadas su capacidades de razonamiento frente al código, las decisiones arquitectónicas y el cumplimiento de requerimientos. Con ellos, se lograron identificar casos borde que e habían omitido en la versión de la semana 1, y que para los cambios de esta no se hab ían resuelto. Como los artefactos construidos fueron amplios y detallados, usar un modelo rápido fue más efectivo. Se aclara que esto también es desde el lado de tiempo y consumo de tokens, dado que en este caso se definieron al final 30 tareas, que so no se ubiera utilizado un modelo rápido, la duración de implementación hubiera sido mucho más tardada (>9min que le tomo a Sonnet, en comparación a Opus).

---
## 4. Evidencia de Verificación Determinista 
- **Análisis estático de fronteras hexagonales (`uv run ruff check src/`)**: 
```text 
[Pega aquí la salida de uv run ruff check src/ mostrando All checks passed!] 
``` 
- **Salida completa de `uv run pytest -v`**: 
```text 
[Pega aquí la salida completa de uv run pytest -v con el 100% de las pruebas en PASSED] 
``` 
- **Evidencia de CLI Typer y containerización (`docker compose config` / `docker compose 
up --build`)**: 
```text 
[Pega aquí la salida de al menos dos subcomandos CLI y de docker compose] 