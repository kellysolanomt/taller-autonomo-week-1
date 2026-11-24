# Especificación de Funcionalidad: Ciclo de vida de incidentes, duplicados y SLA

**Rama de funcionalidad**: `003-incident-lifecycle-duplicates-sla`

**Creada**: 2026-11-24

**Estado**: Borrador

**Entrada**: Descripción del usuario: "Necesitamos guardar los incidentes cuando llegan, avisar si ya había otro equivalente abierto, y consultar cómo va su SLA tanto por API como desde nuestra herramienta CLI."

> Corresponde al hito **H003 — Ciclo de vida, duplicados y SLA** de `docs/ROADMAP.md`.

## Clarifications

### Session 2026-11-24

- Q: ¿El registro de un incidente recibe el reporte en texto libre (como el triaje de H001) y el sistema deriva automáticamente severidad/componente/tipo de síntoma, o recibe esos campos ya clasificados? → A: Se recibe como en el triaje de H001 — reporte en texto libre (más un título e identificador), clasificado automáticamente por el mismo motor, y luego guardado.
- Q: Cuando se detecta un incidente equivalente ya abierto, ¿el nuevo incidente se guarda igual o se rechaza su registro? → A: Se guarda igual; la alerta de duplicado es puramente informativa, nunca bloquea el registro.
- Q: ¿Qué campos recibe el registro de un incidente (`POST /api/v1/incidents` y comando CLI `create`), cuáles son obligatorios, qué valores por defecto aplican y qué devuelve? → A: Obligatorios `title` y `raw_text`; vacíos o solo espacios se rechazan con 422 Unprocessable Entity en la API y código de salida 1 en el CLI. Opcionales: `incident_id` (si se omite se autogenera con formato `INC-<HEX8>`), `created_at` (si se omite, el instante actual) y `status` (por defecto `"OPEN"`). La respuesta exitosa es 201 Created en la API (JSON en stdout en el CLI) e incluye la clasificación completa del triaje, `is_duplicate` (bool) y `duplicate_of` (list[str]).
- Q: ¿Cuál es el criterio exacto para considerar que existe un duplicado abierto? → A: Coincidencia por `duplicate_group_key` únicamente contra incidentes en estado abierto (`OPEN`, `IN_PROGRESS`, `ESCALATION_REQUIRED`), excluyendo los `RESOLVED` y el propio identificador recién creado.
- Q: ¿Cómo se indica el instante de referencia en la auditoría de SLA (`GET /api/v1/incidents/{incident_id}/sla` y comando CLI `sla`) y qué errores devuelve? → A: Parámetro opcional `reference_time` (ISO 8601) para evaluaciones deterministas. Si el incidente no existe: 404 Not Found en la API y código de salida 1 en el CLI. Si `reference_time` es anterior a `created_at`: 422 Unprocessable Entity en la API y código de salida 1 en el CLI.
- Q: Al registrar un incidente con `status` explícito, ¿qué valores se aceptan? → A: Los cuatro (`OPEN`, `IN_PROGRESS`, `ESCALATION_REQUIRED`, `RESOLVED`); si es `RESOLVED`, se fija `resolved_at = created_at` (0 minutos transcurridos). Cualquier otro valor se rechaza con 422 en la API y código de salida 1 en el CLI.
- Q: ¿Qué error recibe quien registra un incidente con un `incident_id` que ya existe? → A: 409 Conflict en la API y código de salida 1 en el CLI, con cuerpo `{"error": ...}`; el incidente existente no se modifica.
- Q: ¿Cuál es el nombre definitivo del campo que lista los incidentes equivalentes abiertos? → A: `duplicate_of` (list[str]); reemplaza a `duplicated_of` en todo el contrato.
- Q: ¿La auditoría de SLA de un incidente ya `RESOLVED` también rechaza un `reference_time` anterior a su `created_at`, o se ignora porque ya no acumula minutos? → A: También se rechaza. La comparación `reference_time < created_at` se aplica siempre, sin importar el estado del incidente; un incidente resuelto nunca acumula minutos después de su resolución, pero eso no excusa un instante de referencia anterior a su apertura.
- Q: ¿Qué pasa cuando `reference_time` (CLI `sla`) o `created_at` (CLI `create`) llegan mal formados, por ejemplo con un formato que no es ISO 8601? → A: Se rechazan con código de salida 1 e imprimen `{"error": ...}` en stderr, igual que cualquier otro error de validación de esta funcionalidad; nunca con el código de salida propio del framework de línea de comandos (p. ej. 2).
- Q: ¿Qué cuerpo exacto devuelve un error 422/404/409 de esta funcionalidad en la API? → A: Siempre `{"error": <mensaje>}`, igual que el resto de la API (H001/H002); incluye tanto errores de reglas de negocio como errores de forma de la solicitud (campos faltantes, JSON inválido, valores fuera de los enumerados).
- Q: ¿Qué pasa si `created_at` o `reference_time` llegan con zona horaria (`tzinfo`), en vez de hora local naive? → A: Se rechazan como un error de validación más —422 en la API, código de salida 1 en el CLI, mismo cuerpo `{"error": ...}`—, nunca como un error interno (500) ni una traza no controlada; el sistema solo acepta fechas-hora naive, igual que el resto del dominio.

## Escenarios de Usuario y Pruebas *(obligatorio)*

### Historia de Usuario 1 - Registrar un incidente entrante y ser alertado de duplicados abiertos, por HTTP (Prioridad: P1)

Como persona o sistema que reporta incidentes, quiero registrar un incidente entrante por HTTP y recibir de inmediato un aviso si ya existe otro incidente equivalente abierto, para no duplicar la atención de un mismo problema.

**Por qué esta prioridad**: Es el valor central de este hito: sin el registro persistente no hay nada que auditar después, y la alerta de duplicados es la razón de negocio principal para registrar en el momento de la llegada, no después.

**Prueba independiente**: Puede probarse por completo enviando un incidente nuevo por HTTP, verificando que queda guardado y disponible en una consulta posterior, y repitiendo el envío con el mismo componente y tipo de síntoma mientras el primero sigue abierto, verificando que la respuesta señala la existencia del duplicado.

**Escenarios de Aceptación**:

1. **Given** no existe ningún incidente abierto equivalente, **When** se registra un incidente nuevo por HTTP, **Then** la respuesta es 201 Created, el incidente queda guardado y disponible para consultas posteriores, y la respuesta indica `is_duplicate: false` y `duplicate_of: []`.
2. **Given** ya existe un incidente abierto que afecta el mismo componente y presenta el mismo tipo de síntoma, **When** se registra un incidente nuevo por HTTP con esas mismas características, **Then** el nuevo incidente también queda guardado (201 Created), y la respuesta indica `is_duplicate: true` y lista en `duplicate_of` los identificadores de los incidentes equivalentes que ya estaban abiertos (sin incluir el propio identificador recién creado).
3. **Given** un incidente equivalente existe pero ya fue resuelto, **When** se registra un incidente nuevo por HTTP con las mismas características, **Then** la respuesta indica `is_duplicate: false` y `duplicate_of: []`, porque el incidente anterior ya no está abierto.
4. **Given** un identificador de incidente que ya fue registrado previamente, **When** se intenta registrar otro incidente por HTTP con ese mismo identificador, **Then** el registro se rechaza con 409 Conflict (cuerpo `{"error": ...}`) y el incidente ya existente no se modifica.
5. **Given** una solicitud de registro cuyo `title` o `raw_text` está vacío o contiene solo espacios, **When** se envía por HTTP, **Then** se rechaza con 422 Unprocessable Entity y no se guarda ningún incidente.
6. **Given** una solicitud de registro válida que omite `incident_id`, `created_at` y `status`, **When** se envía por HTTP, **Then** la respuesta es 201 Created con un `incident_id` autogenerado de formato `INC-<HEX8>`, `status` `"OPEN"` y `created_at` igual al instante del registro.
7. **Given** una solicitud de registro válida con `status` `"RESOLVED"`, **When** se envía por HTTP, **Then** la respuesta es 201 Created, el incidente queda guardado con su instante de resolución igual a su `created_at`, y su auditoría de SLA posterior reporta 0 minutos transcurridos para cualquier instante de referencia válido.

---

### Historia de Usuario 2 - Auditar por HTTP el estado de SLA de un incidente registrado, para cualquier instante de referencia (Prioridad: P2)

Como persona de guardia o de cumplimiento, quiero consultar por HTTP el estado de SLA de un incidente ya registrado para un instante de referencia determinado, para auditar si estuvo (o está) incumplido en cualquier momento de su ciclo de vida, no solo en el instante actual.

**Por qué esta prioridad**: Aporta el valor de auditoría explícito de este hito, pero solo tiene sentido una vez que los incidentes quedan registrados de forma persistente (Historia 1); es independiente de la alerta de duplicados.

**Prueba independiente**: Puede probarse por completo registrando un incidente con una fecha de apertura conocida y consultando su estado de SLA por HTTP para distintos instantes de referencia, verificando que el resultado (minutos transcurridos, incumplimiento, necesidad de escalamiento) es consistente con las reglas de SLA ya vigentes en el sistema para cada instante indicado.

**Escenarios de Aceptación**:

1. **Given** un incidente ya registrado y abierto, **When** se consulta por HTTP su estado de SLA indicando un instante de referencia posterior a su apertura, **Then** la respuesta indica los minutos transcurridos hasta ese instante, si el SLA está incumplido, y si requiere escalamiento, calculados para ese instante.
2. **Given** un incidente ya registrado y ya resuelto, **When** se consulta por HTTP su estado de SLA, **Then** la respuesta refleja el estado final de SLA alcanzado hasta su resolución, sin seguir acumulando minutos después de resuelto.
3. **Given** un identificador de incidente que no corresponde a ningún incidente registrado, **When** se consulta por HTTP su estado de SLA, **Then** la respuesta es 404 Not Found e indica con claridad que el incidente no existe, en vez de un resultado de SLA.
4. **Given** no se indica ningún instante de referencia en la consulta, **When** se consulta por HTTP el estado de SLA de un incidente registrado, **Then** se usa el instante en que se realiza la consulta, igual que el comportamiento ya vigente para el resumen de incidentes activos (H002).
5. **Given** un instante de referencia anterior al momento de apertura del incidente, **When** se consulta por HTTP su estado de SLA con ese instante, **Then** la consulta se rechaza con 422 Unprocessable Entity, en vez de devolver un resultado de SLA inválido.
6. **Given** un incidente P2 (horario hábil) registrado el viernes `2026-11-06T17:00:00` y aún abierto, **When** se consulta por HTTP su estado de SLA con instante de referencia el lunes `2026-11-09T09:00:00`, **Then** la respuesta es 200 OK con `elapsed_minutes=120` (1 hora hábil del viernes más 1 hora hábil del lunes; el fin de semana no consume SLA), `allowed_minutes=480`, `remaining_minutes=360`, `is_breached=false` y `requires_escalation=false`.

---

### Historia de Usuario 3 - Obtener el mismo registro, alerta de duplicados y auditoría de SLA desde el CLI (Prioridad: P3)

Como persona de soporte o de guardia que trabaja desde la terminal o integra un script de automatización, quiero registrar incidentes y auditar su SLA desde la línea de comandos con el mismo resultado que por HTTP, para no depender de la interfaz web al automatizar la recepción de reportes o una revisión de cumplimiento.

**Por qué esta prioridad**: Da paridad de acceso entre interfaces (consistente con H001 y H002), pero depende de que el registro, la alerta de duplicados y la auditoría de SLA ya existan como capacidades de negocio (Historias 1 y 2).

**Prueba independiente**: Puede probarse por completo ejecutando los comandos de registro y de auditoría de SLA con los mismos incidentes e instantes de referencia usados en las Historias 1 y 2, verificando que cada resultado es idéntico al obtenido por HTTP.

**Escenarios de Aceptación**:

1. **Given** el mismo incidente con un duplicado abierto existente usado en la Historia 1, **When** se ejecuta el comando `create` en la terminal, **Then** el proceso termina con código de salida 0, el incidente queda guardado y la salida JSON indica `is_duplicate: true` y el mismo `duplicate_of` que la respuesta HTTP para ese caso.
2. **Given** el mismo incidente P2 e instante de referencia del escenario 6 de la Historia 2, **When** se ejecuta el comando `sla` en la terminal con `--reference-time 2026-11-09T09:00:00`, **Then** el proceso termina con código de salida 0 y la salida JSON contiene los mismos valores que la consulta HTTP: `elapsed_minutes=120`, `allowed_minutes=480`, `remaining_minutes=360`, `is_breached=false` y `requires_escalation=false`.
3. **Given** un identificador de incidente que no corresponde a ningún incidente registrado, **When** se ejecuta el comando de auditoría de SLA en la terminal, **Then** la salida indica con claridad que el incidente no existe y el proceso termina con código de salida 1, no con un resultado de SLA.
4. **Given** un `title` o `raw_text` vacío o solo con espacios, **When** se ejecuta el comando de registro en la terminal, **Then** el proceso termina con código de salida 1 y no se guarda ningún incidente.
5. **Given** un `incident_id` ya registrado, **When** se ejecuta el comando de registro en la terminal con ese mismo identificador, **Then** el proceso termina con código de salida 1, imprime `{"error": ...}` y el incidente ya existente no se modifica.
6. **Given** un `reference_time` anterior al `created_at` del incidente, **When** se ejecuta el comando de auditoría de SLA en la terminal, **Then** el proceso termina con código de salida 1, no con un resultado de SLA.

### Casos Límite

- ¿Qué ocurre si se intenta registrar un incidente con un `incident_id` que ya existe en el sistema? Se rechaza con 409 Conflict en la API y código de salida 1 en el CLI; el incidente ya registrado no se modifica (no hay edición del historial en este corte).
- ¿Qué ocurre si existen varios incidentes equivalentes abiertos simultáneamente al registrar uno nuevo? `duplicate_of` debe listar todos los incidentes equivalentes encontrados, no solo el primero, y nunca el propio identificador recién creado.
- ¿Qué ocurre si `title` o `raw_text` llegan vacíos o solo con espacios? Se rechaza el registro (422 en la API, código de salida 1 en el CLI) y no se guarda nada.
- ¿Un incidente en estado `ESCALATION_REQUIRED` cuenta como duplicado abierto? Sí; solo `RESOLVED` queda excluido.
- ¿Qué ocurre si se registra un incidente directamente con `status` `"RESOLVED"`? Se acepta; su instante de resolución se fija igual a su `created_at`, por lo que su auditoría de SLA reporta 0 minutos transcurridos. No se señala a sí mismo ni a otros como duplicado abierto por estar resuelto, pero su propia respuesta sí calcula `is_duplicate`/`duplicate_of` contra los abiertos existentes.
- ¿Qué ocurre si `status` trae un valor fuera de `OPEN`, `IN_PROGRESS`, `ESCALATION_REQUIRED`, `RESOLVED`? Se rechaza con 422 en la API y código de salida 1 en el CLI.
- ¿Qué ocurre si el instante de referencia de la auditoría de SLA es anterior a la apertura del incidente consultado? La consulta se rechaza con 422 Unprocessable Entity en la API y código de salida 1 en el CLI.
- ¿Qué ocurre al auditar el SLA de un incidente ya resuelto? Se refleja su estado final alcanzado hasta la resolución, sin seguir acumulando minutos después de resuelto.
- ¿El registro o la auditoría de SLA permiten modificar, cerrar o reclasificar un incidente? No; el registro únicamente crea incidentes nuevos, y la auditoría de SLA es una operación de solo lectura.
- ¿Qué ocurre al auditar el SLA de un incidente ya `RESOLVED` con un `reference_time` anterior a su `created_at`? Se rechaza igual que para un incidente abierto (422 en la API, código de salida 1 en el CLI); que ya esté resuelto no excusa un instante de referencia inválido.
- ¿Qué ocurre si `reference_time` (CLI `sla`) o `created_at` (CLI `create`) llegan con un formato que no es ISO 8601 válido? Se rechaza con código de salida 1 y `{"error": ...}` en stderr; nunca con el código de salida propio del framework de CLI (p. ej. 2 de Typer/Click).
- ¿Qué forma tiene el cuerpo de un error 422/404/409 de esta funcionalidad en la API? Siempre `{"error": <mensaje>}`, sin importar si el error es de regla de negocio o de forma de la solicitud (cuerpo/parámetros malformados).
- ¿Qué ocurre si `created_at` o `reference_time` llegan con zona horaria (`tzinfo`)? Se rechaza como error de validación (422 en la API, código de salida 1 en el CLI, cuerpo `{"error": ...}`); nunca con un error interno (500) ni una excepción no controlada.

## Requisitos *(obligatorio)*

### Requisitos Funcionales

- **FR-001**: El sistema DEBE permitir registrar un incidente entrante tanto por una interfaz HTTP como por una interfaz de línea de comandos, con el mismo resultado de negocio en ambas.
- **FR-002**: El registro de un incidente DEBE recibir obligatoriamente un `title` y el reporte en texto libre `raw_text`, y opcionalmente `incident_id` (si se omite, el sistema lo autogenera con formato `INC-<HEX8>`, 8 caracteres hexadecimales), `created_at` (si se omite, el instante del registro) y `status` (uno de `OPEN`, `IN_PROGRESS`, `ESCALATION_REQUIRED` o `RESOLVED`; por defecto `"OPEN"`; cualquier otro valor se rechaza con 422 en la API y código de salida 1 en el CLI; si es `RESOLVED`, el instante de resolución se fija igual a `created_at`); el sistema DEBE derivar automáticamente su severidad, componente y tipo de síntoma a partir de ese texto —igual que en el triaje de H001— y dejar el incidente resultante disponible de forma persistente para consultas posteriores.
- **FR-003**: Al registrar un incidente, el sistema DEBE buscar incidentes con el mismo `duplicate_group_key` (mismo componente y mismo tipo de síntoma) cuyo estado sea `OPEN`, `IN_PROGRESS` o `ESCALATION_REQUIRED`, excluyendo el propio identificador recién creado; la respuesta DEBE indicar `is_duplicate` (`true` si hay al menos uno) y `duplicate_of` con los identificadores de todos los encontrados (lista vacía si no hay ninguno).
- **FR-004**: Cuando se detecta un incidente equivalente ya abierto, el sistema DEBE guardar igualmente el nuevo incidente; la alerta de duplicado es puramente informativa y nunca impide ni condiciona su registro.
- **FR-005**: Un incidente en estado `RESOLVED` NO DEBE considerarse como equivalente abierto para efectos de la alerta de duplicados, sin importar que comparta componente y tipo de síntoma con el nuevo incidente.
- **FR-006**: El sistema NO DEBE permitir registrar dos veces un incidente con el mismo identificador; un identificador ya existente DEBE rechazarse con 409 Conflict en la API y código de salida 1 en el CLI (cuerpo `{"error": ...}`), sin modificar el incidente ya registrado.
- **FR-007**: El sistema DEBE permitir consultar, tanto por HTTP (`GET /api/v1/incidents/{incident_id}/sla`) como por CLI (comando `sla`), el estado de SLA de un incidente ya registrado (`elapsed_minutes`, `allowed_minutes`, `remaining_minutes`, `is_breached` y `requires_escalation`) para un instante de referencia indicado en el parámetro opcional `reference_time` (ISO 8601), con el mismo resultado de negocio en ambas interfaces.
- **FR-008**: Cuando no se indique un instante de referencia en la consulta de SLA, el sistema DEBE usar el instante en que se realiza la consulta, igual que el comportamiento ya vigente para el resumen de incidentes activos (H002).
- **FR-009**: Si el instante de referencia indicado es anterior al momento de apertura del incidente consultado, el sistema DEBE rechazar la consulta con 422 Unprocessable Entity en la API y código de salida 1 en el CLI, en vez de devolver un resultado de SLA inválido; esta validación se aplica sin importar el estado del incidente, incluyendo uno ya `RESOLVED`.
- **FR-010**: Si el identificador de incidente indicado en la consulta de SLA no corresponde a ningún incidente registrado, el sistema DEBE indicarlo con claridad —404 Not Found en la API y código de salida 1 en el CLI— en vez de devolver un resultado de SLA.
- **FR-011**: La evaluación de SLA de un incidente DEBE calcularse de forma consistente con las reglas de SLA ya vigentes en el sistema (horario hábil para severidades P2/P3, minutos de pared para P0/P1), sin una regla nueva o distinta para esta auditoría.
- **FR-012**: Un incidente ya resuelto DEBE reflejar en la auditoría de SLA su estado final alcanzado hasta su resolución, sin seguir acumulando minutos transcurridos después de resuelto.
- **FR-013**: Ni el registro de un incidente ni la auditoría de su SLA DEBEN permitir modificar, cerrar o reclasificar un incidente existente; son operaciones de creación y de solo lectura, respectivamente.
- **FR-014**: Una consulta repetida de auditoría de SLA con los mismos criterios (mismo incidente, mismo instante de referencia) DEBE producir el mismo resultado; la consulta en sí no deja efectos ni estado adicional.
- **FR-015**: El sistema DEBE rechazar el registro cuando `title` o `raw_text` estén vacíos o contengan solo espacios, con 422 Unprocessable Entity en la API y código de salida 1 en el CLI, sin guardar ningún incidente.
- **FR-016**: Un registro exitoso DEBE responder 201 Created en la API (JSON en stdout y código de salida 0 en el CLI), incluyendo el `incident_id` (provisto o autogenerado), `title`, `status`, `created_at`, la clasificación completa del triaje de H001 (`severity`, `component`, `rationale`, `recommended_team`, `duplicate_group_key`, `symptom_category`, `impact_scope`, `consistency_ratio`), `is_duplicate` (bool) y `duplicate_of` (list[str]).
- **FR-017**: Un `reference_time` anterior al `created_at` del incidente consultado DEBE rechazarse (FR-009) sin importar el estado de ese incidente; un incidente `RESOLVED` no está exento de esta validación.
- **FR-018**: Un valor de fecha-hora (`created_at` al registrar, `reference_time` al auditar SLA) que no sea un ISO 8601 válido DEBE rechazarse como error de validación de esta funcionalidad —422 en la API, código de salida 1 en el CLI, cuerpo/mensaje `{"error": ...}`—, nunca con el código de salida o el mensaje propios del framework de CLI subyacente.
- **FR-019**: Toda respuesta de error 409, 422 o 404 producida por el registro de incidentes o la auditoría de SLA DEBE tener cuerpo `{"error": <mensaje>}` en la API, igual que el resto de la API (H001/H002); esto aplica tanto a errores de regla de negocio (duplicado de identificador, instante de referencia inválido, incidente inexistente) como a errores de forma de la solicitud (campos obligatorios ausentes, JSON malformado, valores fuera de los enumerados).
- **FR-020**: Un `created_at` o `reference_time` que incluya zona horaria (`tzinfo`) DEBE rechazarse como error de validación —422 en la API, código de salida 1 en el CLI, cuerpo `{"error": ...}`—, nunca como un error interno (500) ni una excepción no controlada; el sistema solo acepta fechas-hora naive en hora local, igual que el resto del dominio (`src/domain/`).

### Entidades Clave

- **Incidente registrado**: un incidente que queda guardado de forma persistente al llegar, identificado por su `incident_id`, con un título, el componente, la severidad y el tipo de síntoma derivados automáticamente de su reporte en texto libre (igual que en el triaje de H001), estado (`OPEN`, `IN_PROGRESS`, `ESCALATION_REQUIRED` o `RESOLVED`; por defecto `OPEN`), instante de apertura (`created_at`; por defecto el instante del registro) e instante de resolución (`resolved_at`; solo presente si el estado es `RESOLVED`, y al registrarse directamente como resuelto es igual a `created_at`); disponible para consultas posteriores de duplicados y de SLA.
- **Alerta de duplicados**: el resultado de comparar un incidente recién registrado contra los incidentes ya abiertos del mismo componente y tipo de síntoma; se expresa como `is_duplicate` (bool) y `duplicate_of` (list[str]), con cero o más incidentes equivalentes abiertos (`OPEN`, `IN_PROGRESS`, `ESCALATION_REQUIRED`) en el momento del registro, nunca el propio incidente recién creado.
- **Auditoría de SLA**: el resultado de evaluar un incidente registrado para un instante de referencia dado — minutos transcurridos, minutos permitidos, minutos restantes, si incumplió su SLA y si requiere escalamiento — calculado con las reglas de SLA ya vigentes en el sistema.

## Criterios de Éxito *(obligatorio)*

### Resultados Medibles

- **SC-001**: Toda persona o sistema que registra un incidente nuevo recibe, en la misma respuesta, confirmación de que quedó guardado y si existe algún incidente equivalente ya abierto, sin tener que hacer una consulta adicional.
- **SC-002**: Para el mismo incidente registrado y el mismo instante de referencia, la auditoría de SLA obtenida por HTTP y la obtenida por CLI son idénticas en contenido de negocio.
- **SC-003**: El 100% de los incidentes equivalentes abiertos existentes al momento del registro aparece señalado en la alerta de duplicados; ningún incidente resuelto aparece señalado como duplicado abierto.
- **SC-004**: Una persona de guardia o de cumplimiento puede auditar el estado de SLA de cualquier incidente registrado para un instante de referencia distinto al actual, sin depender de que ese instante coincida con el momento de la consulta.
- **SC-005**: Un identificador de incidente inexistente en una consulta de SLA nunca produce un resultado de SLA simulado o engañoso; siempre se informa con claridad que el incidente no existe.

## Supuestos

- El reporte en texto libre y la clasificación automática (severidad, componente, tipo de síntoma) son las mismas que ya usa el triaje de H001; este registro añade la persistencia y la verificación de duplicados que H001 dejaba explícitamente fuera de alcance, sin reimplementar ni modificar las reglas de clasificación.
- Dos incidentes se consideran "equivalentes" cuando afectan el mismo componente y presentan el mismo tipo de síntoma, igual criterio que ya usa el triaje de H001 (`duplicate_group_key`).
- Para la alerta de duplicados, "abierto" significa estado `OPEN`, `IN_PROGRESS` o `ESCALATION_REQUIRED`; un incidente `RESOLVED` nunca se considera un duplicado abierto. Este criterio es propio de H003 y no modifica el conjunto de estados activos del resumen de H002.
- El estado inicial de un incidente recién registrado es `OPEN` y su `created_at` es el instante en que se recibe el registro, salvo que la solicitud indique explícitamente otros valores (ver FR-002).
- Esta funcionalidad no incluye fusión automática de duplicados, escalamiento o reasignación automática, edición del historial de incidentes, ni políticas de retención o archivado — quedan fuera de alcance según `docs/ROADMAP.md` (H003).
- No se requiere autenticación ni autorización para estas consultas y registros en este corte, consistente con el alcance ya definido para H001 y H002.
- La persistencia subyacente reutiliza el mismo almacenamiento ya preparado en H002 (puerto de repositorio de incidentes, con capacidad de guardar, buscar duplicados abiertos y recuperar un incidente por identificador); esta especificación no define el motor de almacenamiento, solo el comportamiento de negocio esperado.
