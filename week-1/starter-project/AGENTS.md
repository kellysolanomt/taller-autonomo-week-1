# AGENTS.md

## Scope and layout
- Git root is this directory, but all real code lives in `week-1/starter-project/`. Run every command from there.
- There is no CI, no linter/formatter/typecheck config. Do not assume `npm` or `make` script entries exist. `pytest` **is** configured (see Commands/Verification below).
- `src/__init__.py` is empty and `pyproject.toml` sets `package = false`; this is a collection of runnable modules, not an installable package.
- Arquitectura hexagonal (H001 + H002):
  - `src/domain/`: núcleo puro (`models.py`, `triage_rules.py`, `sla_calculator.py`). No importa FastAPI, Typer, `sqlite3` ni Pydantic. `ruff.toml` local hace cumplir esa frontera (TID251/TID252).
  - `src/application/ports.py`: puerto de salida `IncidentRepositoryPort` (`typing.Protocol`, `@runtime_checkable`) con `save_incident`, `get_incident`, `find_open_duplicates`, `list_active_incidents` y `check_health`.
  - `src/application/services.py`: casos de uso compartidos `IncidentService.triage_incident(...)` (con `ValidationError` para solicitudes vacías o fuera de límite — único lugar donde se valida la forma de esa solicitud) e `IncidentService.get_active_incidents_summary(component_filter, reference_time)` (orquesta `IncidentRepositoryPort` + `src/domain/sla_calculator.py`; nunca evalúa SLA fuera de ahí). `IncidentService` recibe el repositorio en el constructor. `ruff.toml` local prohíbe importar adaptadores concretos.
  - `src/adapters/inbound/api/`: adaptador REST (FastAPI). `app.py` expone `create_app(service=None)` y `app`, con `POST /api/v1/incidents/triage` y `GET /api/v1/incidents/summary`; `schemas.py` tiene los modelos Pydantic de entrada/salida de ambos.
  - `src/adapters/inbound/cli.py`: adaptador CLI (Typer); `create_cli_app(service)` registra los subcomandos `triage` y `summary`; `app` es la instancia por defecto.
  - `src/adapters/inbound/ruff.toml`: prohíbe `sqlite3` y el import directo de un repositorio concreto; la resolución pasa siempre por `src/adapters/outbound/factory.py`.
  - `src/adapters/outbound/`: adaptador de salida. `sqlite_repository.py` implementa `SQLiteIncidentRepository(IncidentRepositoryPort)` (índice compuesto `(component, status)` de ADR-001, sin evaluar SLA); `factory.py` expone `get_incident_repository()` según `DATABASE_URL` (por defecto `sqlite:///:memory:`; solo soporta el esquema `sqlite:///` en este corte).
  - `src/incident_repository.py` (benchmark pedagógico de Semana 1, N+1 vs. consulta optimizada — ver Gotchas) y `src/context_audit.py` siguen en `src/` tal como estaban; `src/incident_repository.py` no es el adaptador de salida de producción, es un módulo de benchmark independiente.

## Setup
- Python >= 3.10, managed with `uv`. Local `.venv/` is gitignored.
- `uv sync` from `week-1/starter-project`.
- `tiktoken` only exists inside the uv venv. Running with bare `python` makes `src/context_audit.py` fall back to an approximate tokenizer and print that fact.

## Commands (from `week-1/starter-project`)
- `uv run python -m src.context_audit --symbol <name>`: token audit, brute-force `glob`+`read` vs `grep`+`read` vs LSP-style AST extraction.
- `uv run python -m src.context_audit --compare-formats`: token cost of JSON pretty/compact vs YAML vs CSV.
- `uv run python -m src.incident_repository [--records N] [--iterations N]`: seeds in-memory SQLite (default 10,000) and benchmarks.
- `uv run python -m src.domain.triage_rules`: audits triage over `data/sample_incidents.json`.
- `uv run python -m src.domain.sla_calculator`: SLA demo plus hand-checked edge cases; exits 1 if any fail.
- `uv run uvicorn src.adapters.inbound.api.app:app --reload`: runs the REST API (`POST /api/v1/incidents/triage`, `GET /api/v1/incidents/summary`).
- `uv run python -m src.adapters.inbound.cli triage --incident-id <id> --raw-text "<text>"`: runs the triage CLI; prints JSON to stdout and exits 0, or prints `{"error": ...}` to stderr and exits 1 on validation failure.
- `uv run python -m src.adapters.inbound.cli summary [--component <name>] [--reference-time <ISO8601>]`: runs the active-incidents-summary CLI; prints JSON (`total_active`, `breached_count`, `incidents`) to stdout and exits 0, including the empty-summary case.
- `uv run pytest -v`: runs the BDD acceptance suite in `tests/` (see Verification).
- `uv run ruff check src/`: validates hexagonal boundary rules (TID251/TID252) across `src/domain/`, `src/application/`, `src/adapters/inbound/`.
- `DATABASE_URL=sqlite:///<path>`: set before any of the above to point the API/CLI at a shared SQLite file instead of the default `sqlite:///:memory:` (only the `sqlite:///` scheme is supported; see `src/adapters/outbound/factory.py`).
- Always use `python -m src.<module>` from the project root. Modules import `from src.domain.models ...` / `from src.application... ` with absolute paths, so `python src/foo.py` fails.

## Verification
- `uv run pytest -v` runs the BDD acceptance suite: 4 scenarios for triage (`tests/test_spec_001_triage.py`) and 11 for the active-incidents summary (`tests/test_spec_002_summary.py`, API via `TestClient`, CLI via `CliRunner`, each test on its own in-memory `SQLiteIncidentRepository`) — this is the primary check for both features.
- `uv run python -m src.domain.sla_calculator` additionally asserts deterministic SLA edge cases and exits nonzero on failure.
- `uv run ruff check src/` must pass with no `TID251`/`TID252` violations before integrating a change under `src/`.
- Changes must stay deterministic: never read the system clock in `src/domain/` or `src/application/`; `reference_time` is injected. The only place allowed to call `datetime.now()` is the inbound adapter (FastAPI route / Typer command), to resolve the default "query instant" when the caller doesn't pass one. SLA edge cases use fixed 2026 dates.

## Domain rules that are easy to break
- Datetimes must be naive local time. Any `tzinfo` raises `ValueError` in `evaluate_sla_status`.
- P0/P1 (`operates_24x7=True`) count wall-clock minutes. P2/P3 count only business minutes: Mon-Fri 08:00-18:00 (max 600/day), weekends contribute zero.
- `requires_escalation` is `status != "RESOLVED"` and elapsed >= 75% of allowed minutes; it is independent of `is_breached`.
- Triage severity comes from symptom + impact scope, never urgency words like "urgente"/"hoy". Text is lowercased and accent-stripped (`_normalize`) before regex matching.

## Docs and deliverables
- `.specify/memory/constitution.md` (v1.0.0, ratificada) es la fuente normativa vigente para reglas de dominio, arquitectura hexagonal y gobernanza del stack; consolida `docs/constitution.md` y ADR-003 y es la que leen los comandos `/speckit.*`. `docs/constitution.md` sigue siendo un documento de referencia válido pero queda subordinado a `.specify/memory/constitution.md` ante cualquier conflicto textual (p. ej., el flag exacto de `pytest`). `AGENTS.md` es solo la guía operativa; este archivo defiere a la constitución ratificada ante cualquier conflicto.
- `docs/adr/001`, `002` and `003` are course design records marked "Propuesto". New ADRs follow `docs/adr/000-template.md` and must include a Mermaid diagram.
- `specs/001-triage-endpoint-manual.md` defines the H001 triage feature scope (BDD scenarios, HTTP/CLI contracts). It carries an "Enmienda" note recording that domain migration to `src/domain/` was brought forward from a later milestone.
- `specs/002-active-incidents-summary/` (Spec Kit layout: `spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`, `tasks.md`) defines the H002 active-incidents-summary feature scope and its implementation plan.
- `CONTEXT_LOG.md` is the graded student bitácora (template: `CONTEXT_LOG_TEMPLATE.md`; screenshots in `img/`). Preserve student-specific content; do not replace it with generated prose.
- Code comments, docs, and user-facing output are Spanish. Keep new content in Spanish.
- Commit messages in history follow `(Feat): ...` / `(Fix): ...` with Spanish text.

## Gotchas
- `src/incident_repository.py`'s module docstring and the README "Fase 2" section still describe the old N+1 / full-table-scan bug. The method is already refactored per ADR-001 (single filtered query + `(component, status)` index). Trust the code and ADR over that prose.
- SQL values always go through `?` placeholders; `_ACTIVE_STATUSES` is a fixed internal constant. Never interpolate user input into SQL.
- `data/sample_incidents.json` is a fixed 10-record fixture; triage duplicate pairs and ambiguous cases are referenced by ID in `CONTEXT_LOG.md`.
- `SQLiteIncidentRepository` opens its connection with `check_same_thread=False`: FastAPI runs sync route handlers in a worker thread, different from the thread that built the singleton repository at `create_app()`/CLI startup. Without that flag, the summary endpoint raises a "created in a thread" `sqlite3` error on the first real request.
