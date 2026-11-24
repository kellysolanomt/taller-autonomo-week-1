"""Adaptador de entrada REST (FastAPI): traduce HTTP a los casos de uso compartidos."""

from dataclasses import asdict
from datetime import datetime
from typing import Optional

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from src.adapters.inbound.api.schemas import (
    ActiveIncidentsSummaryResponseSchema,
    HealthResponseSchema,
    TriageRequestSchema,
    TriageResponseSchema,
)
from src.adapters.outbound.factory import get_incident_repository
from src.application.services import IncidentService, ValidationError


def create_app(service: Optional[IncidentService] = None) -> FastAPI:
    """Construye la aplicación FastAPI con sus rutas, aisladas del dominio."""
    app = FastAPI(title="IncidentOps - Triaje y Resumen de Incidentes")
    service = service or IncidentService(get_incident_repository())

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

    @app.get("/health")
    def health() -> JSONResponse:
        if service.check_health():
            return JSONResponse(
                status_code=200,
                content=HealthResponseSchema(status="ok", database="connected").model_dump(),
            )
        return JSONResponse(
            status_code=503,
            content=HealthResponseSchema(status="error", database="unavailable").model_dump(),
        )

    @app.get(
        "/api/v1/incidents/summary",
        response_model=ActiveIncidentsSummaryResponseSchema,
    )
    def summary(
        component: Optional[str] = None,
        reference_time: Optional[datetime] = None,
    ) -> ActiveIncidentsSummaryResponseSchema:
        # El reloj del sistema solo se lee aquí, en el borde (research.md, Decisión 3);
        # IncidentService.get_active_incidents_summary nunca lo lee internamente.
        effective_reference_time = reference_time or datetime.now()
        try:
            result = service.get_active_incidents_summary(component, effective_reference_time)
        except ValueError as exc:
            return JSONResponse(status_code=422, content={"error": str(exc)})
        return ActiveIncidentsSummaryResponseSchema(
            total_active=result.total_active,
            breached_count=result.breached_count,
            incidents=[asdict(item) for item in result.incidents],
        )

    return app


app = create_app()
