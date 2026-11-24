"""Esquemas Pydantic del adaptador REST: solo forma de entrada/salida, sin reglas de negocio."""

from pydantic import BaseModel

from src.domain.models import (
    ImpactScope,
    IncidentStatus,
    SeverityLevel,
    SymptomCategory,
    TeamName,
)


class TriageRequestSchema(BaseModel):
    """Cuerpo de la solicitud `POST /api/v1/incidents/triage`."""

    incident_id: str
    raw_text: str


class TriageResponseSchema(BaseModel):
    """Respuesta exitosa, en snake_case, con los campos de `TriageResult`."""

    incident_id: str
    severity: SeverityLevel
    component: str
    rationale: str
    recommended_team: TeamName
    duplicate_group_key: str
    symptom_category: SymptomCategory
    impact_scope: ImpactScope
    consistency_ratio: float


class ActiveIncidentItemSchema(BaseModel):
    """Un incidente activo dentro del detalle de `GET /api/v1/incidents/summary`."""

    incident_id: str
    title: str
    component: str
    severity: SeverityLevel
    status: IncidentStatus
    elapsed_minutes: int
    requires_escalation: bool


class ActiveIncidentsSummaryResponseSchema(BaseModel):
    """Respuesta de `GET /api/v1/incidents/summary`."""

    total_active: int
    breached_count: int
    incidents: list[ActiveIncidentItemSchema]
