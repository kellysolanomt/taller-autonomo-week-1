# Especificación de Funcionalidad: Resumen de incidentes activos

**Rama de funcionalidad**: `002-active-incidents-summary`

**Creada**: 2026-11-23

**Estado**: Borrador

**Entrada**: Descripción del usuario: "Necesitamos consultar el resumen de incidentes actualmente activos (OPEN e IN_PROGRESS) tanto por API HTTP como por CLI, indicando el total activo, cuántos incumplieron su SLA y el detalle de cada incidente (título, componente, severidad, estado, minutos transcurridos y si requiere escalamiento), permitiendo filtrar opcionalmente por componente."

> Corresponde al hito **H002 — Resumen de incidentes activos** de `docs/ROADMAP.md`.

## Clarifications

### Session 2026-11-23

- Q: ¿Qué volumen máximo de incidentes activos simultáneos debe soportar el resumen sin degradar el tiempo de respuesta ni requerir paginación? → A: Hasta ~100 incidentes activos simultáneos (panel de guardia típico).
- Q: ¿Debe el resumen permitir indicar opcionalmente un instante de referencia distinto del momento de la consulta, para que la evaluación de SLA sea reproducible? → A: Sí; cuando no se indique, se usa el instante en que se realiza la consulta.
- Q: ¿El resumen global (sin filtro) debe excluir explícitamente los incidentes ya resueltos aunque coexistan con incidentes activos en el sistema? → A: Sí, confirmado; ya regido por FR-009 y ahora reflejado explícitamente en el escenario de aceptación correspondiente.

## Escenarios de Usuario y Pruebas *(obligatorio)*

### Historia de Usuario 1 - Consultar el resumen de incidentes activos por HTTP (Prioridad: P1)

Como persona de guardia, quiero consultar por HTTP el resumen de los incidentes actualmente activos (en estado OPEN o IN_PROGRESS), para saber de un vistazo cuántos hay, cuántos ya incumplieron su SLA y el detalle de cada uno, sin tener que revisar incidente por incidente.

**Por qué esta prioridad**: Es el valor central de la funcionalidad: sin esta consulta no existe el resumen. Es la interfaz que puede integrarse en un panel o herramienta externa de guardia.

**Prueba independiente**: Puede probarse por completo enviando la consulta de resumen al endpoint HTTP con un conjunto conocido de incidentes activos y verificando que el total, los incumplimientos y el detalle devueltos coinciden con ese conjunto.

**Escenarios de Aceptación**:

1. **Given** existen incidentes activos (OPEN o IN_PROGRESS) con distintas severidades —algunos con su SLA incumplido y otros no— y además existen incidentes ya resueltos en el mismo sistema, **When** se consulta el resumen de incidentes activos por HTTP sin filtro, **Then** la respuesta indica el total de incidentes activos, cuántos de ellos incumplieron su SLA, y el detalle de cada uno (título, componente, severidad, estado, minutos transcurridos y si requiere escalamiento), sin incluir ninguno de los incidentes ya resueltos.
2. **Given** no existe ningún incidente en estado OPEN o IN_PROGRESS, **When** se consulta el resumen por HTTP, **Then** la respuesta es válida con el total activo en cero, los incumplimientos en cero y el detalle vacío (no un error).
3. **Given** un incidente activo cuyo tiempo transcurrido ya superó el máximo permitido por su SLA, **When** se consulta el resumen por HTTP, **Then** ese incidente se cuenta dentro de los incumplimientos de SLA y su detalle lo refleja.

---

### Historia de Usuario 2 - Obtener el mismo resumen desde la línea de comandos (Prioridad: P2)

Como persona de guardia que trabaja desde la terminal o desde un script de automatización, quiero obtener el mismo resumen de incidentes activos por línea de comandos, para no depender de abrir el panel web durante una guardia o una revisión por script.

**Por qué esta prioridad**: Da paridad de acceso entre interfaces (consistente con H001) y habilita el uso en automatizaciones de guardia, pero depende de que el resumen ya exista como capacidad de negocio (Historia 1).

**Prueba independiente**: Puede probarse por completo ejecutando el comando de resumen de incidentes activos con el mismo conjunto de incidentes usado en la Historia 1 y verificando que el total, los incumplimientos y el detalle son idénticos a los obtenidos por HTTP.

**Escenarios de Aceptación**:

1. **Given** el mismo conjunto de incidentes activos usado en la consulta HTTP, **When** se ejecuta el comando de resumen de incidentes activos en la terminal sin filtro, **Then** el total activo, los incumplimientos de SLA y el detalle de cada incidente son los mismos que entrega la consulta HTTP para ese conjunto.
2. **Given** no existe ningún incidente activo, **When** se ejecuta el comando en la terminal, **Then** la salida indica el resumen vacío (total activo en cero) y el proceso termina de forma correcta, no con un error.

---

### Historia de Usuario 3 - Filtrar el resumen por componente (Prioridad: P3)

Como persona responsable de un componente específico (por ejemplo, la pasarela de pagos), quiero acotar el resumen de incidentes activos a mi componente, para enfocarme únicamente en lo que me corresponde atender sin revisar el resto del sistema.

**Por qué esta prioridad**: Es un refinamiento útil sobre el resumen general; aporta valor por sí mismo pero no es indispensable para que el resumen exista.

**Prueba independiente**: Puede probarse por completo consultando el resumen con el filtro de un componente conocido y verificando que el total, los incumplimientos y el detalle solo incluyen incidentes activos de ese componente.

**Escenarios de Aceptación**:

1. **Given** existen incidentes activos de varios componentes distintos, **When** se consulta el resumen filtrando por uno de esos componentes (por HTTP o por CLI), **Then** el total activo, los incumplimientos de SLA y el detalle devuelto incluyen únicamente los incidentes activos de ese componente.
2. **Given** un componente que no tiene ningún incidente activo en este momento, **When** se consulta el resumen filtrando por ese componente, **Then** la respuesta es válida con el total en cero y el detalle vacío (no un error), aunque ese componente sí tenga incidentes resueltos o inexistentes.
3. **Given** no se indica ningún componente en la consulta, **When** se consulta el resumen, **Then** se incluyen los incidentes activos de todos los componentes, igual que en la Historia 1.

---

### Casos Límite

- ¿Qué ocurre cuando no hay ningún incidente activo en todo el sistema? El resumen debe ser válido con el total en cero, sin error.
- ¿Qué ocurre cuando el componente indicado en el filtro no coincide con ningún incidente, ni activo ni resuelto (por ejemplo, un nombre de componente inexistente)? El resumen debe ser válido con el total en cero, sin error ni distinción respecto a un componente que sí existe pero no tiene incidentes activos.
- ¿Qué ocurre cuando todos los incidentes activos incumplieron su SLA? El conteo de incumplimientos debe ser igual al total activo.
- ¿Qué ocurre cuando ninguno de los incidentes activos incumplió su SLA? El conteo de incumplimientos debe ser cero, aunque el total activo sea mayor que cero.
- ¿Qué ocurre cuando un incidente activo está exactamente en el límite de minutos permitido por su SLA? Debe clasificarse de forma consistente con la regla de incumplimiento ya vigente en el sistema (sin un criterio distinto para esta consulta).
- ¿El resumen permite crear, cerrar o modificar un incidente? No; esta consulta es de solo lectura.

## Requisitos *(obligatorio)*

### Requisitos Funcionales

- **FR-001**: El sistema DEBE permitir consultar el resumen de incidentes activos (estado OPEN o IN_PROGRESS) tanto por una interfaz HTTP como por una interfaz de línea de comandos.
- **FR-002**: El sistema DEBE producir el mismo resultado de negocio (mismo total, mismos incumplimientos de SLA, mismo detalle) para la misma consulta sin importar si se accede por HTTP o por línea de comandos.
- **FR-003**: El resumen DEBE indicar el número total de incidentes activos que cumplen la consulta.
- **FR-004**: El resumen DEBE indicar cuántos de esos incidentes activos incumplieron su SLA, según la regla de incumplimiento de SLA ya vigente en el sistema.
- **FR-005**: El resumen DEBE incluir, por cada incidente activo, su título, componente, severidad, estado, minutos transcurridos desde su apertura, y si requiere escalamiento.
- **FR-006**: El sistema DEBE permitir indicar opcionalmente un componente para acotar el resumen; cuando se indica, el total, los incumplimientos y el detalle DEBEN limitarse a los incidentes activos de ese componente.
- **FR-007**: Cuando no se indique ningún componente, el resumen DEBE incluir los incidentes activos de todos los componentes.
- **FR-008**: Cuando el filtro de componente no coincida con ningún incidente activo, el sistema DEBE devolver un resumen válido con el total en cero y el detalle vacío, no un error.
- **FR-009**: Un incidente en un estado distinto de OPEN o IN_PROGRESS (por ejemplo, resuelto) NO DEBE contarse ni aparecer en el resumen de incidentes activos.
- **FR-010**: Los minutos transcurridos y la condición de incumplimiento de SLA de cada incidente DEBEN calcularse de forma consistente con las reglas de SLA ya vigentes en el sistema (no una regla nueva o distinta para este resumen).
- **FR-011**: La consulta del resumen NO DEBE crear, modificar, cerrar ni reclasificar ningún incidente; es una operación de solo lectura.
- **FR-012**: Una consulta repetida con los mismos criterios (mismo filtro, mismo conjunto de incidentes activos) DEBE producir el mismo resultado; la consulta en sí no deja efectos ni estado adicional.
- **FR-013**: El sistema DEBE permitir indicar opcionalmente un instante de referencia distinto para evaluar los minutos transcurridos y el incumplimiento de SLA de cada incidente activo; cuando no se indique, DEBE usarse el instante en que se realiza la consulta. Esto permite repetir una misma consulta de forma reproducible para un instante dado.

### Entidades Clave

- **Incidente activo**: un incidente cuyo estado actual es OPEN o IN_PROGRESS; para efectos de este resumen se describe por su título, componente, severidad, estado, minutos transcurridos desde su apertura y si requiere escalamiento.
- **Resumen de incidentes activos**: el resultado de la consulta; agrupa el total de incidentes activos, la cantidad de ellos que incumplió su SLA y el detalle individual de cada incidente activo considerado.
- **Filtro por componente**: criterio opcional de la consulta que, cuando se indica, limita el total, los incumplimientos y el detalle del resumen a los incidentes activos de ese componente únicamente.

## Criterios de Éxito *(obligatorio)*

### Resultados Medibles

- **SC-001**: Una persona de guardia obtiene el total de incidentes activos y la cantidad de incumplimientos de SLA en una sola consulta, sin tener que revisar los incidentes uno por uno.
- **SC-002**: Para la misma consulta (con o sin filtro de componente), el resumen obtenido por HTTP y el obtenido por línea de comandos son idénticos en contenido de negocio (mismo total, mismos incumplimientos, mismo detalle).
- **SC-003**: Al filtrar por un componente, el 100% de los incidentes del detalle devuelto pertenece a ese componente, y ningún incidente activo de ese componente queda fuera del resultado.
- **SC-004**: Cuando no hay incidentes activos que cumplan la consulta (en general o por el filtro aplicado), la persona que consulta recibe un resumen vacío válido, nunca un mensaje de error.
- **SC-005**: A partir del detalle de un incidente activo, una persona de guardia puede decidir si requiere escalamiento inmediato sin tener que consultar ninguna otra fuente de información.
- **SC-006**: Con hasta 100 incidentes activos simultáneos (con o sin filtro de componente), el resumen completo (total, incumplimientos y detalle) está disponible en menos de 2 segundos, sin necesidad de paginar los resultados.

## Supuestos

- El filtro por componente admite indicar como máximo un componente por consulta; no se requiere combinar varios componentes en una misma consulta.
- La coincidencia del filtro de componente es exacta sobre el identificador de componente ya usado en el resto del sistema (por ejemplo, "payments-gateway"), sin búsqueda parcial ni insensibilidad a mayúsculas/minúsculas.
- El detalle de incidentes activos no requiere un orden de presentación específico garantizado por esta especificación; cualquier orden estable es aceptable mientras incluya todos los incidentes activos que correspondan.
- No se requiere autenticación ni autorización para esta consulta en este corte, consistente con el alcance ya definido para H001.
- Esta funcionalidad no incluye paginación, exportación de reportes ni notificaciones automáticas por incumplimiento; estos quedan fuera de alcance según `docs/ROADMAP.md` (H002). La ausencia de paginación es válida mientras el volumen de incidentes activos simultáneos se mantenga en el orden de ~100 (ver SC-006); un volumen mayor requeriría revisar este supuesto.
- El instante de referencia usado para calcular minutos transcurridos e incumplimientos de SLA es, por defecto, el momento en que se realiza la consulta; el caso en que se indique un instante distinto queda cubierto como capacidad explícita en FR-013, preservando el principio de determinismo ya vigente en el sistema para las reglas de SLA.
