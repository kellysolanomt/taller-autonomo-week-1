"""Adaptador de entrada CLI (Typer): traduce la terminal al caso de uso compartido."""

import json
import sys
from dataclasses import asdict

import typer

from src.application.services import IncidentService, ValidationError

app = typer.Typer()
_service = IncidentService()


@app.callback()
def _main() -> None:
    """CLI de IncidentOps. Usa el subcomando `triage` para clasificar un reporte."""


@app.command()
def triage(
    incident_id: str = typer.Option(..., "--incident-id"),
    raw_text: str = typer.Option(..., "--raw-text"),
) -> None:
    """Clasifica un reporte de incidente e imprime el resultado en JSON."""
    try:
        result = _service.triage_incident(incident_id, raw_text)
    except ValidationError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise typer.Exit(code=1)

    print(json.dumps(asdict(result), ensure_ascii=False))


if __name__ == "__main__":
    app()
