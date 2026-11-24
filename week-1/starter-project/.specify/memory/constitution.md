<!--
Sync Impact Report
Version change: (plantilla sin ratificar) → 1.0.0
Ratificación: documento sin versión previa en .specify/memory/; se adopta como versión inicial
  formal, consolidando docs/constitution.md (Vigente, 2026-11-21) y ADR-003 (Propuesto, 2026-11-21).
Principios añadidos:
  - I. Núcleo Determinista Único
  - II. Arquitectura Hexagonal Estricta (ADR-003)
  - III. Gobernanza del Stack Tecnológico (ADR-001)
  - IV. Verificación Estática de Fronteras Hexagonales (Ruff)
  - V. Calidad mediante Pruebas BDD Obligatorias (pytest)
Secciones añadidas:
  - Restricciones de Dominio y Seguridad (triaje, SLA, escalamiento, equipos, estados, duplicados,
    seguridad SQL)
  - Cumplimiento Operativo y Jerarquía Normativa (jerarquía Constitución > ADR > código, relación
    con AGENTS.md, idioma, ADR obligatorio para cambios estructurales)
  - Governance (procedimiento de enmienda, versionado semántico, revisión de cumplimiento)
Secciones eliminadas: ninguna (placeholders de plantilla reemplazados en su totalidad).
Plantillas dependientes: no se modifican en este comando (alcance limitado a la Constitución);
  revisar en la próxima ejecución de /speckit-plan, /speckit-tasks y /speckit-checklist que no
  citen principios obsoletos.
Deferred TODOs: ninguno — ver sección "Next Actions" de la respuesta del agente para brechas de
  implementación detectadas (Ruff aún no configurado, `src/adapters/outbound/` y `ports.py`
  pendientes de creación, `DATABASE_URL` aún no existe).
-->

# IncidentOps Constitution

## Core Principles

### I. Núcleo Determinista Único
La única fuente de verdad del negocio vive en `src/domain/` (`models.py`, `triage_rules.py`,
`sla_calculator.py`). Ninguna regla de triaje, SLA, severidad, equipo, estado o duplicados
MUST NOT reimplementarse en `src/application/` ni en `src/adapters/`; esos módulos SOLO orquestan
o traducen, nunca redefinen la regla. El dominio MUST ser determinista: el tiempo de referencia
(`reference_time`) se inyecta desde el borde y el dominio MUST NOT leer el reloj del sistema. Los
datetimes MUST ser naive en hora local; cualquier `tzinfo` presente en `created_at`, `resolved_at`
o `reference_time` MUST lanzar `ValueError`.

Rationale: un único lugar de verdad para las reglas de negocio es lo que permite que REST, CLI y
futuros adaptadores (MCP) devuelvan exactamente la misma clasificación y el mismo cálculo de SLA;
duplicar la regla en un adaptador introduce divergencia silenciosa, y leer el reloj del sistema
rompe la reproducibilidad de las pruebas y de las auditorías de SLA.

### II. Arquitectura Hexagonal Estricta (ADR-003)
`src/domain/` MUST NOT importar FastAPI, Typer, `sqlite3`, Pydantic ni ningún adaptador. Los casos
de uso compartidos viven en `src/application/`, que MUST exponerse mediante `ports.py` (puertos de
entrada y de salida definidos con `typing.Protocol`) y `services.py` (`IncidentService`,
orquestando esos puertos sin reimplementar reglas de dominio). `src/adapters/inbound/` aloja los
adaptadores primarios — FastAPI y Typer hoy — traduciendo cada solicitud externa a una llamada al
mismo `IncidentService`; esta carpeta MUST quedar preparada para incorporar futuros adaptadores de
entrada (p. ej. MCP) reutilizando el servicio existente, sin duplicar lógica de traducción ni de
negocio. `src/adapters/outbound/` aloja los adaptadores secundarios (persistencia, chequeos de
conectividad); MUST ser intercambiable y seleccionarse en tiempo de ejecución a través de la
variable `DATABASE_URL`, sin que `src/domain/` ni `src/application/` conozcan el motor concreto. La
dirección de dependencias MUST apuntar siempre hacia adentro (adaptadores → aplicación → dominio);
el cableado concreto (composition root) y el mapeo DTO ↔ dominio ocurren en el borde, nunca en el
núcleo.

Rationale: fijar estas fronteras es la decisión estructural más difícil de revertir del proyecto
(ADR-003); es lo que permite sustituir el motor de persistencia en H004, añadir un adaptador MCP
sin tocar reglas de negocio, y probar el dominio determinista sin levantar infraestructura.

### III. Gobernanza del Stack Tecnológico (ADR-001)
El runtime MUST ser Python >= 3.10 gestionado con `uv`; todos los comandos se ejecutan desde
`week-1/starter-project/`. El stack adoptado es FastAPI + Pydantic v2 para REST (la validación y
serialización ocurren solo en el adaptador), Typer para CLI, y `sqlite3` de la biblioteca estándar
sin ORMs ni dependencias externas de persistencia, conforme a ADR-001. Ningún motor de base de
datos ni ORM distinto se adopta sin un ADR específico, aprobado previamente, que enmiende esta
Constitución. Todo valor de consulta SQL MUST viajar mediante placeholders `?`; ninguna entrada de
usuario se interpola jamás en una sentencia SQL.

Rationale: el stack ya resuelve los requisitos de H001–H004 sin ORM pesado; cambiarlo sin ADR
reabriría decisiones ya evaluadas (ADR-001) y podría reintroducir el patrón N+1 o el riesgo de
inyección SQL que ADR-001 cerró explícitamente.

### IV. Verificación Estática de Fronteras Hexagonales (Ruff)
`uv run ruff check src/` MUST ejecutarse y pasar en verde antes de integrar cualquier cambio en
`src/`. Esta verificación MUST incluir la detección de imports prohibidos en `src/domain/`
(FastAPI, Typer, `sqlite3`, Pydantic o cualquier adaptador) para que una violación del Principio II
falle en CI/revisión y no dependa solo de la revisión humana.

Rationale: la arquitectura hexagonal es tan fuerte como su verificación; sin un chequeo estático
automatizado, la frontera dominio/adaptador se erosiona con el tiempo sin que nadie lo note hasta
que aparece un acoplamiento costoso de revertir.

### V. Calidad mediante Pruebas BDD Obligatorias (pytest)
Toda funcionalidad observable desde un adaptador de entrada (REST, CLI) MUST estar cubierta por
escenarios BDD en formato Given/When/Then, ejecutados con `uv run pytest -v`, y ese comando MUST
pasar en verde antes de integrar cualquier cambio. Las pruebas MUST ser deterministas — sin reloj
de pared, con `reference_time` fijo — y MUST cubrir los bordes de SLA ya fijados en ADR-002. Antes
de refactorizar código existente se escriben pruebas de caracterización que capturen el
comportamiento vigente.

Rationale: el dominio es puro y determinista precisamente para que sea exhaustivamente verificable;
las pruebas BDD son el contrato ejecutable entre la especificación funcional (`specs/`) y el código,
y son la única defensa contra regresiones silenciosas en el cálculo de SLA o en el triaje.

## Restricciones de Dominio y Seguridad

- **Triaje**: el texto de entrada se normaliza a minúsculas y sin tildes (`_normalize`) antes de
  evaluarse; la severidad se decide por síntoma + alcance, nunca por palabras de urgencia como
  "urgente" u "hoy". Precedencia de síntoma: `data_exposure` > `outage` > `cert_expiry`/`capacity`
  > `access_blocked` > `latency` > `ui_cosmetic` > `other`. `data_exposure` es siempre P0; los
  alcances `individual`/`staging` topan en P2 para el resto de síntomas.
- **SLA por severidad** (ADR-002): P0 = 60 min y P1 = 240 min, ambos 24/7 en minutos de pared; P2 =
  480 min y P3 = 1440 min, ambos solo en minutos hábiles (lunes a viernes, 08:00–18:00, máximo
  600 min/día; sábados y domingos aportan cero; los festivos no se modelan y se tratan como
  hábiles). Los segundos se suman y se truncan a minutos una sola vez al final.
- **Escalamiento**: `requires_escalation = (status != "RESOLVED") and (elapsed_minutes >=
  int(allowed_minutes * 0.75))`; es independiente de `is_breached` (`elapsed_minutes >
  allowed_minutes`). Un incidente abierto y ya vencido sigue escalando.
- **Equipos válidos**: `Backend-Core`, `Platform-SRE`, `Data-DBA`, `Security-IAM`.
- **Estados**: `OPEN`, `IN_PROGRESS`, `ESCALATION_REQUIRED`, `RESOLVED`. Activos = `OPEN` e
  `IN_PROGRESS`. Todo `RESOLVED` lleva `resolved_at`, que detiene el reloj; quien cambia el estado
  garantiza esa invariante.
- **Duplicados**: clave `<component>:<symptom_category>`; solo se reportan grupos con 2 o más
  incidentes. La fusión automática queda fuera de alcance (H003).
- **Seguridad SQL**: todos los valores viajan con placeholders `?`; `_ACTIVE_STATUSES` es una
  constante interna fija; nunca se interpola entrada de usuario en una consulta.

## Cumplimiento Operativo y Jerarquía Normativa

- **Jerarquía normativa**: esta Constitución > ADRs > código. Un ADR que la contradiga MUST
  enmendarla explícitamente en el mismo cambio.
- **Relación con `AGENTS.md`**: `AGENTS.md` es la guía operativa (comandos, layout, gotchas); esta
  Constitución fija las reglas no negociables del producto y de la arquitectura. Ante un conflicto,
  esta Constitución prevalece y `AGENTS.md` se actualiza para reflejarla.
- **Cambios estructurales**: toda regla de dominio nueva, puerto, motor de base de datos o nuevo
  adaptador MUST acompañarse de un ADR con diagrama Mermaid, siguiendo `docs/adr/000-template.md`.
- **Idioma**: comentarios de código, documentación y salida orientada a usuario MUST permanecer en
  español; los mensajes de commit siguen el formato `(Feat): ...` / `(Fix): ...` en español.
- **`CONTEXT_LOG.md`**: es la bitácora de estudiante y no se reemplaza por prosa generada; el
  contenido específico del estudiante se preserva en cualquier cambio.

## Governance

Esta Constitución tiene precedencia sobre `AGENTS.md`, los ADRs existentes y cualquier práctica de
código no documentada. Toda enmienda MUST registrarse mediante un ADR (con diagrama Mermaid cuando
el cambio sea estructural) y MUST actualizar este documento en el mismo cambio; no se aceptan
enmiendas verbales ni cambios de regla sin su ADR correspondiente.

**Versionado semántico** de esta Constitución:
- MAJOR: eliminación o redefinición incompatible de un principio o de una frontera arquitectónica.
- MINOR: incorporación de un principio nuevo o ampliación material de una guía existente.
- PATCH: aclaraciones, correcciones de redacción o refinamientos no semánticos.

**Revisión de cumplimiento**: toda PR o revisión MUST verificar que `uv run ruff check src/` y
`uv run pytest -v` pasan en verde antes de integrarse; toda complejidad arquitectónica añadida
(un nuevo puerto, un nuevo adaptador) MUST justificarse contra los principios aquí fijados. Use
`AGENTS.md` como guía operativa de desarrollo en el día a día.

**Version**: 1.0.0 | **Ratified**: 2026-11-21 | **Last Amended**: 2026-11-22
