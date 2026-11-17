# Bitácora de Ingeniería de Prompts y Contexto — Semana 1 (`CONTEXT_LOG.md`)

**Estudiante(s)**: `Kelly Johana Solano Calderón`  
**Fecha**: `2026-11-17`  
**Modelos / Asistentes Utilizados**: `Claude Haiku 5.5 (Medium), Claude Sonnet 5.5 (Medium), Claude Opus 5.5 (Medium), Claude Sonnet 5.5 (High)`

---

## 1. De Prompts Pobres a Técnicas Clásicas de *Prompt Engineering* (Reto 1: `src/triage_rules.py`)

### 1.1 Diagnóstico de un Prompt Pobre y Ambiguo
Analiza el siguiente prompt deficiente para el Reto 1:
> *"El archivo `triage_rules.py` funciona mal con algunos tickets del JSON. Agrégale el equipo recomendado y una clave para duplicados, y no pongas P0 cuando no sea urgente."*

![Auditoría del Triaje, versión inicial](img\paso1-1.png)

Documenta al menos **3 modos de fallo o ambigüedades** de este prompt (p. ej., ausencia de contexto de dominio, restricciones negativas difusas, falta de enumeración de equipos válidos o ausencia de ejemplos canónicos):
1. `Ausencia de contexto de dominio`: El prompt no aclara cuál es el criterio de clasificación de los tickets, cuáles son las categorias y por qué está funcionando mal. Esto provoca que el modelo entregue clasificaciones inventadas, criterios sin umbrales claros, formatos diversos y que todos los resultados dependan de su interpretación. 
2. `Restricciones negativas`: La restricción de "no pongas P0 cuando no sea urgente", no le define al modelo el nivel de urgencia, ya que esta puede ser por nivel de riesgo, tiempo transcurrido o cualquier otra interpretación. Además, pone la restricción únicamente para el nivel de P0, dejando por fuera los otros niveles y su niveles de urgencia individuales.
3. `Ambigüedad de valores válidos`: Relacionado con la solicitud de equipos recomendados y la generación de claves para duplicados, porque el prompt no define cuál sería el criterio que establece que un equipo es o no es recomendado según determinado ticket. Tampoco incluye la lista actual de equipos ni el propósito de atención de tickets de cada uno. En el caso de las claves para evitar los duplicados, tampoco se establece un formato (podría ser [numeral-incidente-fecha] o [incidente-origen-fecha], o cualquier otra combinación posible). El modelo nuevamente inferirá el resultado esperado. 

### 1.2 Uso de *Self-Consistency*, *Chain-of-Thought* y *Few-Shot Prompting*

![Reporte de incidente inicial](img\paso1-2.png)

- ¿Cómo utilizaste *Chain-of-Thought* (`<analysis>`) y *Self-Consistency* (múltiples consultas independientes) para definir las reglas de clasificación de los casos ambiguos (`INC-1002`, `INC-1007`, `INC-1009`) y la agrupación de duplicados (`INC-1001`/`INC-1006` e `INC-1003`/`INC-1008`)?

El prompt inicial utilizado para *Chain-of-Thought* fue:

```xml
Analiza y razona paso a paso, dentro <analysis>...</analysis>,  sobre el alcance, el riesgo y la agrupación de los duplicados de los tickets. Hazlo con duplicados como INC-1001/INC-1006, INC-1002, INC-1003/INC-1008, INC-1007 e INC-1009.
```

Se hicieron 4 pruebas con este prompt y los 10 incidentes, haciendo la comparación entre modos rápidos y de razonamiento, y cambios entre modelos:

*Prueba con Haiku 5.5 (Medium)*

![Prueba con Haiku 5.5 (Medium)](img\paso1-2-1.png)

*Prueba con Sonnet 5.5 (Medium)*

![Prueba con Sonnet 5.5 (Medium)](img\paso1-2-2.png)

*Prueba con Opus 5.5 (Medium)*

![Prueba con Opus 5.5 (Medium)](img\paso1-2-3.png)

*Prueba con Sonnet 5.5 (High)*

![Prueba con Sonnet 5.5 (High)](img\paso1-2-4.png)

Luego de este análisis, se logró identificar que en 3 de las 4 pruebas hubo consenso entre los modelos: existen 8 problemas distintos, 2 repetidos y 6 individuales. En los duplicados, se relaciona a la caída de la pasarela de pagos (por el error 502) y a la lentitud del sistema por la cantidad de registros. En el caso del modelo rápido de Haiku 5.5 (Medium), la clasificación fue diferente y más ambigüa, dado que no tuvo un paso estructurado para el análisis. 

A partir de esa concordancia entre los resultados del Chain-of-Thought, con Self-Consitency, se estructuró el acuerdo entre los tres análisis, por ejemplo, a nivel de incidente detectado para cada nivel de severidad y el criterio para determinar si varios incidentes eran duplicados o no. Luego, condensé con mis palabras cada clasificación para construir el prompt estructurado, definiendo las reglas de dominio para severidad y para los equipos recomendados, creé dos ejemplos nuevos y su salida esperada, y especifiqué la tarea final. 

- Copia el prompt mejorado que empleaste aplicando las técnicas clásicas (`<role>`, `<domain_rules>` con justificación del *porqué*, `<examples>` *Few-Shot* y `<task>`):

```xml
<role>
Actúa como Ingeniero Principal de Confiabilidad (SRE) y Seguridad en IncidentOps.
</role>
<context> 
<lsp_context symbol="classify_incident_report">
  <!-- 1. Definiciones de Tipos y Políticas (LSP Hover / Type Definition) -->
# [LSP textDocument/hover type] src\models.py:12
class SLARule:
    """Define el acuerdo de nivel de servicio (SLA) para un nivel de severidad."""

    severity: SeverityLevel
    max_resolution_minutes: int
    operates_24x7: bool
    escalation_threshold_ratio: float = 0.75

# [LSP textDocument/hover type] src\models.py:22
class Incident:
    """Representa un incidente registrado en la plataforma IncidentOps."""

    incident_id: str
    title: str
    component: str
    severity: SeverityLevel
    status: IncidentStatus
    created_at: datetime
    resolved_at: Optional[datetime] = None

# [LSP textDocument/hover type] src\models.py:35
class SLAEvaluation:
    """Resultado determinista de la evaluación de SLA de un incidente."""

    incident_id: str
    severity: SeverityLevel
    elapsed_minutes: int
    allowed_minutes: int
    remaining_minutes: int
    is_breached: bool
    requires_escalation: bool

# [LSP textDocument/hover type] src\models.py:48
class TriageResult:
    """Resultado estructurado producido por el clasificador de triaje con IA."""

    incident_id: str
    severity: SeverityLevel
    component: str
    rationale: str
    consistency_ratio: float = 1.0

# [LSP textDocument/hover symbol] src\sla_calculator.py:17
SLA_POLICY_TABLE: Dict[SeverityLevel, SLARule] = {
    "P0": SLARule(severity="P0", max_resolution_minutes=60, operates_24x7=True),
    "P1": SLARule(severity="P1", max_resolution_minutes=240, operates_24x7=True),
    "P2": SLARule(severity="P2", max_resolution_minutes=480, operates_24x7=False),
    "P3": SLARule(severity="P3", max_resolution_minutes=1440, operates_24x7=False),
}

  <!-- 2. Definición Exacta del Símbolo (LSP GoToDefinition) -->
# [LSP textDocument/definition] src\triage_rules.py:27
def classify_incident_report(incident_id: str, raw_text: str) -> TriageResult:
    """Clasifica un reporte de incidente aplicando reglas heurísticas iniciales.

    DEUDA TÉCNICA INTENCIONAL:
    - Evalúa palabras sueltas ("hoy", "urgente") antes de analizar el impacto real
      (caída global vs. cuenta individual vs. entorno de staging).
    - No normaliza componentes ni identifica el equipo de guardia correspondiente.
    """
    text_lower = raw_text.lower()

    # Bug de diseño: si un usuario dice "necesito acceder hoy" por su cuenta bloqueada,
    # se dispara como P0 antes de verificar si es una caída global o un caso individual.
    if "urgente" in text_lower or "hoy" in text_lower or "502" in text_lower:
        severity: SeverityLevel = "P0"
    elif "94%" in text_lower or "timeout" in text_lower:
        severity = "P1"
    elif "lenta" in text_lower or "segundos" in text_lower:
        severity = "P2"
    else:
        severity = "P3"

    if "pago" in text_lower or "cobro" in text_lower or "tarjeta" in text_lower:
        component = "payments-gateway"
    elif "cuenta" in text_lower or "ingresar" in text_lower:
        component = "auth-identity"
    elif "postgresql" in text_lower or "conexiones" in text_lower:
        component = "database-cluster"
    elif "certificado" in text_lower or "tls" in text_lower:
        component = "infra-certificates"
    elif "botón" in text_lower or "color" in text_lower:
        component = "frontend-ui"
    else:
        component = "reporting-api"

    return TriageResult(
        incident_id=incident_id,
        severity=severity,
        component=component,
        rationale=f"Clasificación heurística legacy asignada a {component} ({severity}).",
    )

  <!-- 3. Referencias de Invocación en el Proyecto (LSP FindReferences) -->
# [LSP textDocument/references] src\triage_rules.py:77
  L76:     for item in incidents:
  L77:         result = classify_incident_report(item["id"], item["raw_text"])
  L78:         snippet = item["raw_text"][:45] + "..." if len(item["raw_text"]) > 45 else item["raw_text"]
</lsp_context>
</context> 
<domain_rules>
Se debe clasificar los tickets en los siguientes niveles de severidad:
- PO: Es crítico. Refiere incidentes donde algún componente este caído, no funcione, y no permitan completar las operaciones correctamente (Ej: Error 502). El problema abarca todos los comercios o transacciones. También son problemas de seguridad dentro de los tenant (Ej: exposiciones de datos). Su riesgo influye una pérdida directa de clientes o de operaciones para la plataforma, riesgo de privacidad. 
- P1: Es alto. Refiere incidentes relacionados con alertas de infraestructura, por ejemplo, sobre indicadores de sobrecarga de capacidad en componentes del sistema (Ej: alto porcentaje de conexiones). Es una degradación que puede llevar a una potencial caída. 
- P2: Es medio. Refiere a un incidente donde hay una degradación leve de algún componente, por las propias capacidades del sistema o limitaciones en el rendimiento, pero no una caída o suspensión de la capacidad (Ej: superación de intentos para el ingreso, o lentitud de procesamiento por alto volumen). 
- P3: Es bajo. Refiere a un incidente menor, que no relaciona a ningún inconveniente con la plataforma, sino a correcciones a nivel de interfaz UI, o actividades de mantenimiento periódicas de la plataforma. 

Sobre la asignación de equipos:
- Backend-Core: Problemas relacionados con servicios, integraciones, etc.
- Platform-SRE: Problemas de infraestructura, certificados, etc.
- Data-DBA: Problemas con la base de datos, la integridad de la información almacenada, etc.
- Security-IAM: Problemas de autenticación, privacidad, etc.
</domain_rules> 
<examples> 
<example>
Input: "Estaba revisando la URL de la pasarela de pagos y al cambiar el parámetro de company_id se pueden abrir las facturas pendiente por pagar de otras empresas"
<analysis>
1. Es un riesgo de seguridad grande, porque afecta la privacidad de los usuarios.
2. Potenciales implicaciones legales y regulatorias por la exposición de la información. 
</analysis>
<output>severity="P0", component="auth-identity", recommended_team="Security-IAM", duplicate_group_key="auth-identity:data_exposure"</output>
</example>
<example>
Input: "La descarga del reporte anual está tardando más de 20 s, lo necesito para hoy"
<analysis>
1. El alcance es individual e indica que el componente de reportería sigue funcionando, pero está lento. Existe entonces una degradación leve. 
2. Aunque el usuario indique "hoy", el alcance definido para las severidades indica que la prisa no es criterio para aumentar la severidad. 
</analysis>
<output>severity="P2", component="reporting-api", recommended_team="Backend-Core", duplicate_group_key="reporting-api:latency"</output>
</example>
</examples> 
<task> 
Refactoriza los archivos src/triage_rules.py y src/models.py, tomando como referencia los análisis y clasificaciones presentados. Ten en cuenta que estos archivos deben asignar correctamente la severidad (P0-P3), sugerir el recommended_team (Backend-Core, Platform-SRE, Data-DBA y Security-IAM) y definir para el caso de duplicados una duplicate_group_key, una clave normalizada con este formato:  (<component>:<symptom_category>). Esto, por cada uno de los incidentes. 
</task> 
```

*Resultado en terminal*

Auditoría del motor de Triaje (Actualizada)

![Auditoría del motor de Triaje (Actualizada)](img\paso1-4.png)

---

## 2. Flujo Explorar $\rightarrow$ Destilar $\rightarrow$ Ejecutar en Contexto Limpio (Reto 2: Cálculo de SLA en Horario Hábil y ADR-002)

### 2.1 Exploración de Diseño (Sin Generar Código Aún) y Destilación
- **Objetivo explorado**: Diseño del algoritmo de cálculo de SLA en horario hábil (`P2`/`P3`, Lunes–Viernes 08:00–18:00) vs. 24/7 (`P0`/`P1`) y regla de escalamiento preventivo al 75%.
- **Síntesis de tu exploración de alternativas y resumen destilado (máx. 10 líneas)**:

El prompt utilizado fue:
  > `<lsp_context>...</lsp_context> Estoy revisando la función `evaluate_sla_status` en `sla_calculator.py` que evalúa si un incidente ha incumplido su SLA o requiere escalamiento. Estoy notando que el modelo esta omitiendo casos borde críticos, como los tickets que se crean los fines de semana, los que se crean un viernes a las 18:30 y quedan fuera de ventana, o los tickets donde requieres_escalation se apaga erróneamente cuando se vence el SLA. No escribas código todavía: analicemos los casos borde, en torno a ¿Qué pasa si un incidente se crea el viernes fuera de horario y se evalúa el lunes a las 8:30?, ¿Qué pasa si se crea un sábado o se cruza múltiples fines de semana?, ¿Cómo se podría mantener el algoritmo simple, legible y O(D), donde la D es el número de días entre la creación y la evaluación, sin librerías externas pesadas?, ¿Cuáles son los SLAs definidos para los incidentes y que está causando que la escalación se apague?, ¿Cómo se están respondiendo a los casos que quedan en espera en el fin de semana (se encolan, se asigan, se escalan, ...)? `
  
Las dudas que explore fueron:
- Comportamiento de los tickets que llegaban fuera de horarios (por jemeplo, en los fines de semana).
- Comportamiento de los cruces de fines de semana. Acá es importante aclarar que el asistente ayudó a identificar, como que en los tickets que eran marcados como resueltos, seguía corriendo su reloj de resolución.
- Cómo mantener el algoritmo simple, donde el asistente sugirió crear una función auxiliar para calcular los minutos (dentro de la franaj laboral) que son los que debería mirar `evaluate_sla_stauts`. 
- También se consultó sobre el problema con los SLAs, que hacian que la escalación se apagara. Frente a esto se encontró que la condición de escalación era una ventana cerrada y no un umbral. Esto significa que casos como que un ticket estuviera abierto, pero su SLA se hubiera vencido, quedan por fuera del rango. Así mismo, la principal hipotésis fue que la bandera de escalamiento preventivo estaba omitiendo estos casos de tickets vencidos pero pendientes. 

Adicional a estos escenarios borde, se encontraron estos adicionales:
- Hay un problema en la evaluación historia, porque si `resolved_at` es posterior a `reference_time`, se ignora el último.
- Hay datetime con zona y otros si zona, por lo que las comparaciones podrían saltar error de tipo. 

Aceptando algunas sugerencias y descartando otras, se obtuvo el siguiente bloque destilado:

```xml
**Opciones descartadas**
    - Mantener minutos de pared para P2 y P3. Es la causa de los falsos vencidos en fines de semana.
    - Una regla especial de "mover el inicio al próximo día hábil". Contar solo la intersección con las ventanas hábiles ya lo resuelve.
    - Modelar "en espera de fin de semana" como estado almacenado. Se deriva del tiempo.
    - Mantener `not is_breached` en la escalación, o separar dos flags. Se descarta porque los vencidos abiertos también deben escalar.
    - Seguir midiendo hasta `reference_time` cuando está `RESOLVED` sin `resolved_at`.

**Decisión final**
    - P0 y P1 miden minutos de pared. P2 y P3 miden minutos hábiles (lunes a viernes, 08:00–18:00) con una función auxiliar pura, O(D), día a día, que suma el solape con cada ventana.
    - `requires_escalation` es verdadera si el incidente no está `RESOLVED` y `elapsed >= escalation_limit`.
    - Todo `RESOLVED` lleva `resolved_at`, y eso detiene el reloj.

**Restricciones técnicas**
    - Solo librería estándar (`datetime` y `timedelta`).
    - Datetimes naive en hora local de operación, sin zonas horarias.
    - Sumar segundos y truncar a minutos una sola vez al final.
    - La invariante de `resolved_at` la debe garantizar quien cambia el estado, no el calculador.
    - Pendiente de decidir:
    - La evaluación histórica (propongo `min(resolved_at, reference_time)`).
    - Si se rechaza un `tzinfo` presente.
    - Cómo maneja el repositorio los datos inválidos.
```

### 2.2 Ejecución con Contexto Curado en Nuevo Chat Limpio (*Context Engineering*)
Copia el prompt estructurado con etiquetas XML que utilizaste en un nuevo chat limpio para generar el **ADR (`docs/adr/002-calculo-sla-horario-habil.md`)** y la refactorización de `src/sla_calculator.py`:

```xml
<!-- Pega aquí tu prompt estructurado con <context>, <decision_summary>, <constraints>, <task> -->
```

---

## 3. Tipos de Modelos y Matriz de Decisión Arquitectónica

### 3.1 Comparación de Tipos de Modelos
Compara el comportamiento que observaste al interactuar con:
1. **Modelo Rápido / Estándar (ej. Flash, Mini, Haiku o modo estándar)**:
2. **Modelo de Razonamiento Extendido (*Thinking Model*)**:
- ¿En cuál de las tareas de la semana fue indispensable el modelo de razonamiento y en cuál bastó el modelo rápido?

### 3.2 Matriz de Decisión Arquitectónica
Para la plataforma *IncidentOps* y su evolución futura, justifica qué paradigma es el adecuado en cada escenario:

| Escenario / Requerimiento | Paradigma Elegido (Código Determinista / ML Clásico / Asistente GenAI en Chat / LLM en Tiempo de Ejecución) | Justificación Técnica (Determinismo, Costo, Latencia, Riesgo de Alucinación) |
| :--- | :--- | :--- |
| 1. Contabilizar minutos hábiles transcurridos y verificar si un ticket superó el 75% de su SLA | | |
| 2. Explorar casos borde y redactar un ADR antes de modificar la arquitectura de consultas SQL | | |
| 3. Detectar anomalías numéricas en millones de métricas de CPU/RAM por minuto | | |
| 4. Clasificar reportes de incidentes redactados en lenguaje natural abierto cuando las reglas deterministas no cubren nuevos patrones | | |

---

## 4. Economía de Tokens y Curaduría de Contexto con `tiktoken` (LSP vs. `grep`/`read` vs. `glob`/`read`)

### 4.1 Medición Empírica en *IncidentOps*
Completa la tabla con los resultados obtenidos al auditar los símbolos con `uv run python -m src.context_audit --symbol evaluate_sla_status` (y `classify_incident_report`):

| Estrategia de Recolección de Contexto | Alcance (Archivos / Nodos) | Caracteres Totales | Tokens (`tiktoken o200k_base`) | % de Reducción vs. Fuerza Bruta |
| :--- | :--- | :---: | :---: | :---: |
| **1. Fuerza Bruta (`glob` + `read` todo)** | Todos los archivos del proyecto | | | 0% (Línea base) |
| **2. Búsqueda Textual (`grep` + `read` `.py`)** | Archivos `.py` donde aparece el símbolo | | | |
| **3. Semántica vía LSP (`definition` + `references` + `hover`)** | Solo definición, tipos asociados y líneas de invocación | | | |

### 4.2 Comparación de Formatos de Serialización (`--compare-formats`)
Registra los tokens medidos con `tiktoken` para los 10 incidentes en JSON indentado, JSON compacto, YAML y CSV, y explica qué formato elegirías al inyectar datos tabulares o logs largos en la ventana de contexto.
