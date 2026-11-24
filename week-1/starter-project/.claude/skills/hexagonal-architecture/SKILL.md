---
name: hexagonal-architecture
description: Reglas de frontera de la arquitectura hexagonal de IncidentOps (ADR-003) — qué puede importar cada capa de src/, paridad obligatoria entre adaptadores primarios (REST/CLI) y validación estática de esas fronteras con Ruff (TID251/TID252). Usar al crear o revisar código en src/domain/, src/application/ o src/adapters/.
---

# Arquitectura hexagonal de IncidentOps (ADR-003)

Referencia normativa: `docs/constitution.md` (Artículo 2) y `docs/adr/003-arquitectura-hexagonal.md`.
Estado: la frontera de capas en `src/domain/` y `src/application/` ya existe (primer corte H001); `src/adapters/outbound/` y la validación con Ruff descritas aquí son el diseño objetivo que aún no está implementado en código (ver `specs/001-triage-endpoint-manual.md`, sección de enmienda). Al tocar este código, acércalo a este objetivo en vez de alejarlo.

La dirección de dependencias es siempre hacia adentro: adaptadores → aplicación → dominio. El dominio no conoce a nadie.

## 1. Qué puede importar cada capa

### `src/domain/` (`models.py`, `triage_rules.py`, `sla_calculator.py`)
- Permitido: biblioteca estándar únicamente (`dataclasses`, `datetime`, `re`, `typing`, etc.).
- Prohibido: FastAPI, Typer, Pydantic, `sqlite3`, o cualquier módulo bajo `src.adapters`. No importa `src.application` tampoco (el dominio no conoce la capa que lo orquesta).
- Debe permanecer puro y determinista: nunca lee el reloj del sistema; toda fecha/hora de referencia se recibe como parámetro.

### `src/application/services.py`
- Permitido: biblioteca estándar y `src.domain.*`.
- Prohibido: FastAPI, Typer, Pydantic, `sqlite3`, y cualquier adaptador concreto (`src.adapters.inbound.*`, `src.adapters.outbound.*`).
- Define los puertos de entrada/salida con `typing.Protocol` y orquesta el caso de uso compartido (`IncidentService.triage_incident`). Es el único lugar donde se valida la forma de la solicitud (`ValidationError`); los adaptadores no reimplementan esa validación.

### `src/adapters/inbound/` (`api/app.py`, `api/schemas.py`, `cli.py`)
- Permitido: el framework propio del adaptador (FastAPI/Pydantic en `api/`, Typer en `cli.py`), `src.application.services` y, para resolver el repositorio concreto, `src.adapters.outbound.factory`.
- Prohibido: importar un driver de base de datos (`sqlite3`, etc.) o una clase de repositorio concreta (p. ej. `src.incident_repository.IncidentRepository`) directamente. La resolución de la implementación de salida pasa siempre por `src.adapters.outbound.factory`, nunca por un `import` directo del adaptador concreto.
- Todo adaptador de entrada delega la lógica de negocio en `IncidentService`; no reimplementa triaje, SLA ni validación de la solicitud.

### `src/adapters/outbound/` (futuro: repositorio SQLite actual, BD relacional de H004, chequeo de conectividad)
- Permitido: `src.domain.*`, `src.application.*` (para implementar el puerto de salida que esta capa expone), y el driver de persistencia concreto (`sqlite3`, u otro motor aprobado por ADR).
- Debe implementar `IncidentRepositoryPort` (el puerto de salida definido con `typing.Protocol` en `src.application`) sin filtrar detalles del motor de persistencia hacia el dominio o la aplicación.
- Todo valor de consulta viaja parametrizado (`?`); nunca se interpola entrada de usuario en SQL.

## 2. Paridad entre adaptadores primarios (REST y CLI)

- REST (`src/adapters/inbound/api/app.py`) y CLI (`src/adapters/inbound/cli.py`) deben invocar exactamente el mismo caso de uso: `IncidentService.triage_incident(...)`. Un futuro adaptador MCP se incorpora igual, reutilizando el servicio.
- Ningún adaptador primario duplica reglas de triaje, cálculo de SLA o validación de la solicitud; esa lógica vive una sola vez en `src/domain/` y `src/application/`.
- Diferencias aceptables entre adaptadores: solo el mapeo de transporte (JSON HTTP vs. argumentos de línea de comandos, códigos de salida vs. códigos de estado HTTP). El resultado de negocio (severidad, SLA, mensajes de error de validación) debe ser idéntico para la misma entrada.
- Al añadir o revisar un adaptador de entrada, verifica que exista cobertura BDD equivalente en `tests/test_spec_001_triage.py` para API (`TestClient`) y CLI (`CliRunner`) con el mismo escenario.

## 3. Validación estática de fronteras con Ruff

Objetivo de diseño (pendiente de incorporar en `pyproject.toml`, ver nota de estado arriba):

- `pyproject.toml` declara `select = ["E4", "E7", "E9", "F", "TID"]` en `[tool.ruff.lint]`, habilitando entre otras las reglas:
  - **TID251** (`banned-api`): prohíbe imports concretos (p. ej. `sqlite3`, FastAPI, Typer, Pydantic, o `src.incident_repository.IncidentRepository`) desde los módulos donde no corresponden según la sección 1.
  - **TID252** (`ban-relative-imports` con `banned-module-level-imports = "parents"`, es decir `relative-imports.ban-relative-imports = "parents"`): prohíbe imports relativos que suban a un paquete padre, forzando imports absolutos `from src....` consistentes con el resto del proyecto.
- Las reglas de `TID251` se afinan por capa mediante archivos `ruff.toml` jerárquicos (Ruff los combina con la configuración raíz, el más específico gana):
  - `src/domain/ruff.toml`: banea FastAPI, Typer, Pydantic, `sqlite3` y cualquier `src.adapters.*`.
  - `src/application/ruff.toml`: banea lo mismo que `domain`, y además cualquier `src.adapters.*` concreto (la aplicación solo conoce puertos, no implementaciones).
  - `src/adapters/inbound/ruff.toml`: banea `sqlite3` y cualquier import directo de una clase de repositorio concreta (p. ej. `src.incident_repository.IncidentRepository`); el acceso a persistencia pasa por `src.adapters.outbound.factory`.
- Ejecución: `uv run ruff check src/` desde `week-1/starter-project`. Un fallo de `TID251`/`TID252` en CI o en revisión local indica una violación de la frontera hexagonal descrita en la sección 1, no un falso positivo a silenciar con `# noqa` salvo justificación explícita en el PR.

## Checklist rápido al revisar un cambio

1. ¿El archivo importa algo prohibido para su capa según la sección 1? Si sí, corregir antes de continuar.
2. ¿Un adaptador de entrada reimplementa triaje/SLA/validación en vez de llamar a `IncidentService`? Si sí, mover la lógica a `src/application/` o `src/domain/`.
3. ¿REST y CLI producen el mismo resultado de negocio para el mismo input? Verificar con los escenarios BDD existentes o nuevos en `tests/`.
4. ¿`uv run ruff check src/` pasa sin señalar `TID251`/`TID252`? (Una vez incorporada la configuración de Ruff al proyecto.)
