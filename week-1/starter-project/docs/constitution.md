# Constitución del Proyecto — IncidentOps

- **Estado**: Vigente
- **Fecha**: 2026-11-21
- **Ámbito**: `week-1/starter-project/`
- **Jerarquía normativa**: esta Constitución > ADRs > código. Un ADR que la contradiga debe enmendarla explícitamente.
- **Rol frente a `AGENTS.md`**: `AGENTS.md` es la guía operativa (comandos, layout, gotchas); este documento fija las reglas no negociables del producto.

## Artículo 1 — Dominio determinista único

1.1. La única fuente de verdad del negocio vive en `src/domain/`. Ninguna regla de triaje, SLA, severidad, equipo, estado o duplicados puede reimplementarse en `src/application/` ni en `src/adapters/`.

1.2. **Determinismo**: el tiempo de referencia se inyecta (`reference_time`); nunca se lee el reloj del sistema. Los datetimes son naive en hora local; cualquier `tzinfo` en `created_at`, `resolved_at` o `reference_time` lanza `ValueError`.

1.3. **Triaje** (síntoma + alcance, nunca palabras de urgencia como "urgente"/"hoy"):

- El texto se normaliza a minúsculas y sin tildes antes de evaluar.
- Precedencia de síntoma: `data_exposure` > `outage` > `cert_expiry`/`capacity` > `access_blocked` > `latency` > `ui_cosmetic` > `other`.
- Severidad base por síntoma, ajustada por alcance: `data_exposure` es siempre P0 (criterio conservador de privacidad); `individual`/`staging` topan en P2 para el resto.

1.4. **SLA por severidad** (ADR-002):

| Severidad | Máximo | Ventana |
|---|---|---|
| P0 | 60 min | 24/7 (minutos de pared) |
| P1 | 240 min | 24/7 (minutos de pared) |
| P2 | 480 min | hábil (minutos hábiles) |
| P3 | 1440 min | hábil (minutos hábiles) |

- Horario hábil: lunes a viernes, 08:00–18:00, máximo 600 min/día; sábados y domingos aportan cero. Los festivos no se modelan y se tratan como hábiles.
- Se suman segundos y se truncan a minutos una sola vez al final.

1.5. **Escalamiento**: `requires_escalation = (status != "RESOLVED") and (elapsed_minutes >= int(allowed_minutes * 0.75))`. Es independiente de `is_breached` (que es `elapsed_minutes > allowed_minutes`). Un incidente abierto y ya vencido sigue escalando.

1.6. **Equipos válidos**: `Backend-Core`, `Platform-SRE`, `Data-DBA`, `Security-IAM`.

1.7. **Estados**: `OPEN`, `IN_PROGRESS`, `ESCALATION_REQUIRED`, `RESOLVED`. Activos = `OPEN` e `IN_PROGRESS`. Todo `RESOLVED` lleva `resolved_at`, que detiene el reloj; la invariante la garantiza quien cambia el estado.

1.8. **Duplicados**: clave `<component>:<symptom_category>`; solo se reportan grupos con 2+ incidentes. La fusión automática queda fuera de alcance (H003).

## Artículo 2 — Arquitectura Hexagonal (ADR-003)

2.1. **`src/domain/`**: entidades y reglas puras. Prohibido importar FastAPI, Typer, `sqlite3`, Pydantic o cualquier adaptador.

2.2. **`src/application/`**: casos de uso compartidos y puertos definidos con `typing.Protocol` (entrada y salida), orquestados por `IncidentService`.

2.3. **`src/adapters/inbound/`**: adaptadores primarios REST y CLI que traducen solicitudes externas a los mismos casos de uso. Un futuro adaptador MCP se incorpora aquí reutilizando el servicio, sin duplicar lógica.

2.4. **`src/adapters/outbound/`**: adaptadores secundarios intercambiables (SQLite actual, BD relacional dedicada de H004, chequeo de conectividad) que implementan los puertos de salida.

2.5. **Dirección de dependencias**: siempre hacia adentro (adaptadores → aplicación → dominio). El cableado concreto (composition root) se hace en el borde. El mapeo DTO ↔ dominio ocurre en los adaptadores, no en el núcleo.

## Artículo 3 — Gobernanza técnica y calidad

3.1. **Runtime**: Python >= 3.10 gestionado con `uv`; todos los comandos se ejecutan desde `week-1/starter-project/`.

3.2. **Stack adoptado**: FastAPI + Pydantic v2 para REST (validación/serialización solo en el adaptador), Typer para CLI, y `sqlite3` de la biblioteca estándar sin ORMs pesados. **Cualquier cambio de motor de base de datos exige un ADR aprobado previamente.**

3.3. **Seguridad SQL**: todos los valores viajan con placeholders `?`; nunca se interpola entrada de usuario.

3.4. **Calidad**: especificación BDD en formato `Given / When / Then` y pruebas de aceptación automatizadas con `pytest`. Las pruebas deben ser deterministas (sin reloj de pared) y cubrir los bordes de SLA ya fijados en ADR-002; antes de refactorizar se escriben pruebas de caracterización.

3.5. **Cláusula transitoria**: el repositorio actual aún no incorpora FastAPI, Typer ni `pytest`. Mientras dure la migración a la arquitectura hexagonal, los módulos existentes siguen siendo válidos, pero **todo código nuevo** cumple esta Constitución.

## Artículo 4 — Cumplimiento y enmiendas

4.1. Un cambio estructural (regla de dominio, puerto, motor de BD, nuevo adaptador) requiere ADR con diagrama Mermaid.

4.2. Toda enmienda a esta Constitución se registra vía ADR y actualiza este documento en el mismo cambio.
