"""Adaptador de entrada CLI (Typer): traduce la terminal a los casos de uso compartidos."""

import json
import sys
from dataclasses import asdict
from datetime import datetime
from typing import Optional

import typer

from src.adapters.outbound.factory import get_incident_repository
from src.application.services import IncidentService, ValidationError


def create_cli_app(service: IncidentService) -> typer.Typer:
    """Construye la app Typer con sus subcomandos, aislada del dominio."""
    app = typer.Typer()

    @app.callback()
    def _main() -> None:
        """CLI de IncidentOps. Usa `triage` para clasificar o `summary` para el resumen."""

    @app.command()
    def triage(
        incident_id: str = typer.Option(..., "--incident-id"),
        raw_text: str = typer.Option(..., "--raw-text"),
    ) -> None:
        """Clasifica un reporte de incidente e imprime el resultado en JSON."""
        try:
            result = service.triage_incident(incident_id, raw_text)
        except ValidationError as exc:
            print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
            raise typer.Exit(code=1)

        print(json.dumps(asdict(result), ensure_ascii=False))

    @app.command()
    def summary(
        component: Optional[str] = typer.Option(None, "--component"),
        reference_time: Optional[datetime] = typer.Option(None, "--reference-time"),
    ) -> None:
        """Imprime el resumen de incidentes activos en JSON."""
        # El reloj del sistema solo se lee aquí, en el borde (research.md, Decisión 3);
        # IncidentService.get_active_incidents_summary nunca lo lee internamente.
        effective_reference_time = reference_time or datetime.now()
        try:
            result = service.get_active_incidents_summary(component, effective_reference_time)
        except ValueError as exc:
            print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
            raise typer.Exit(code=1)

        body = {
            "total_active": result.total_active,
            "breached_count": result.breached_count,
            "incidents": [asdict(item) for item in result.incidents],
        }
        print(json.dumps(body, ensure_ascii=False))

    return app


app = create_cli_app(IncidentService(get_incident_repository()))

if __name__ == "__main__":
    app()
