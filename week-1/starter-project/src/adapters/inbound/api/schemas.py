"""Esquemas Pydantic del adaptador REST: solo forma de entrada/salida, sin reglas de negocio."""

from pydantic import BaseModel

from src.domain.models import (
    ImpactScope,
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
