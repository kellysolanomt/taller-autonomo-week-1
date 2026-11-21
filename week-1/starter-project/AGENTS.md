# AGENTS.md

## Scope and layout
- Git root is this directory, but all real code lives in `week-1/starter-project/`. Run every command from there.
- There is no CI, no linter/formatter/typecheck config. Do not assume `npm` or `make` script entries exist. `pytest` **is** configured (see Commands/Verification below).
- `src/__init__.py` is empty and `pyproject.toml` sets `package = false`; this is a collection of runnable modules, not an installable package.
- Arquitectura hexagonal (primer corte, H001):
  - `src/domain/`: núcleo puro (`models.py`, `triage_rules.py`, `sla_calculator.py`). No importa FastAPI, Typer, `sqlite3` ni Pydantic.
  - `src/application/services.py`: caso de uso compartido `IncidentService.triage_incident(...)`, con `ValidationError` para solicitudes vacías o fuera de límite. Único lugar donde se valida la forma de la solicitud; los adaptadores no reimplementan esa validación.
  - `src/adapters/inbound/api/`: adaptador REST (FastAPI). `app.py` expone `create_app()` y `app`; `schemas.py` tiene los modelos Pydantic de entrada/salida.
  - `src/adapters/inbound/cli.py`: adaptador CLI (Typer), subcomando `triage`.
  - `src/incident_repository.py` (adaptador de salida SQLite) y `src/context_audit.py` siguen en `src/` tal como estaban.

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
- `uv run uvicorn src.adapters.inbound.api.app:app --reload`: runs the triage REST API (`POST /api/v1/incidents/triage`).
- `uv run python -m src.adapters.inbound.cli triage --incident-id <id> --raw-text "<text>"`: runs the triage CLI; prints JSON to stdout and exits 0, or prints `{"error": ...}` to stderr and exits 1 on validation failure.
- `uv run pytest -q`: runs the BDD acceptance suite in `tests/` (see Verification).
- Always use `python -m src.<module>` from the project root. Modules import `from src.domain.models ...` / `from src.application... ` with absolute paths, so `python src/foo.py` fails.

## Verification
- `uv run pytest -q` runs the 4 BDD acceptance scenarios in `tests/test_spec_001_triage.py` (API via `TestClient`, CLI via `CliRunner`) — this is the primary check for the triage feature.
- `uv run python -m src.domain.sla_calculator` additionally asserts deterministic SLA edge cases and exits nonzero on failure.
- Changes must stay deterministic: never read the system clock; `reference_time` is injected. SLA edge cases use fixed 2026 dates.

## Domain rules that are easy to break
- Datetimes must be naive local time. Any `tzinfo` raises `ValueError` in `evaluate_sla_status`.
- P0/P1 (`operates_24x7=True`) count wall-clock minutes. P2/P3 count only business minutes: Mon-Fri 08:00-18:00 (max 600/day), weekends contribute zero.
- `requires_escalation` is `status != "RESOLVED"` and elapsed >= 75% of allowed minutes; it is independent of `is_breached`.
- Triage severity comes from symptom + impact scope, never urgency words like "urgente"/"hoy". Text is lowercased and accent-stripped (`_normalize`) before regex matching.

## Docs and deliverables
- `docs/constitution.md` is the normative source for domain rules, hexagonal architecture, and the technical stack. `AGENTS.md` is only the operational guide; this file defers to the constitution on any conflict.
- `docs/adr/001`, `002` and `003` are course design records marked "Propuesto". New ADRs follow `docs/adr/000-template.md` and must include a Mermaid diagram.
- `specs/001-triage-endpoint-manual.md` defines the H001 triage feature scope (BDD scenarios, HTTP/CLI contracts). It carries an "Enmienda" note recording that domain migration to `src/domain/` was brought forward from a later milestone.
- `CONTEXT_LOG.md` is the graded student bitácora (template: `CONTEXT_LOG_TEMPLATE.md`; screenshots in `img/`). Preserve student-specific content; do not replace it with generated prose.
- Code comments, docs, and user-facing output are Spanish. Keep new content in Spanish.
- Commit messages in history follow `(Feat): ...` / `(Fix): ...` with Spanish text.

## Gotchas
- `src/incident_repository.py`'s module docstring and the README "Fase 2" section still describe the old N+1 / full-table-scan bug. The method is already refactored per ADR-001 (single filtered query + `(component, status)` index). Trust the code and ADR over that prose.
- SQL values always go through `?` placeholders; `_ACTIVE_STATUSES` is a fixed internal constant. Never interpolate user input into SQL.
- `data/sample_incidents.json` is a fixed 10-record fixture; triage duplicate pairs and ambiguous cases are referenced by ID in `CONTEXT_LOG.md`.
