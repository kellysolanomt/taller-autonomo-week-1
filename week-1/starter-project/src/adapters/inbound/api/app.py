"""Adaptador de entrada REST (FastAPI): traduce HTTP al caso de uso compartido."""

from dataclasses import asdict

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from src.adapters.inbound.api.schemas import TriageRequestSchema, TriageResponseSchema
from src.application.services import IncidentService, ValidationError


def create_app() -> FastAPI:
    """Construye la aplicación FastAPI con sus rutas, aisladas del dominio."""
    app = FastAPI(title="IncidentOps - Triaje de Incidentes")
    service = IncidentService()

    @app.exception_handler(Exception)
    def handle_unexpected_error(_request, exc: Exception) -> JSONResponse:
        return JSONResponse(status_code=500, content={"error": str(exc)})

    @app.post("/api/v1/incidents/triage", response_model=TriageResponseSchema)
    def triage(request: TriageRequestSchema) -> TriageResponseSchema:
        try:
            result = service.triage_incident(request.incident_id, request.raw_text)
        except ValidationError as exc:
            return JSONResponse(status_code=422, content={"error": str(exc)})
        return TriageResponseSchema(**asdict(result))

    return app


app = create_app()
