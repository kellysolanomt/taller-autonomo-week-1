"""Entidades de dominio y tipos de datos para IncidentOps."""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Optional

SeverityLevel = Literal["P0", "P1", "P2", "P3"]
IncidentStatus = Literal["OPEN", "IN_PROGRESS", "ESCALATION_REQUIRED", "RESOLVED"]

# Equipos de guardia a los que se puede enrutar un incidente.
TeamName = Literal["Backend-Core", "Platform-SRE", "Data-DBA", "Security-IAM"]

# Categoría de síntoma normalizada: segunda mitad de `duplicate_group_key`.
SymptomCategory = Literal[
    "data_exposure",   # fuga/exposición de datos entre tenants (privacidad)
    "outage",          # componente caído o que no completa operaciones
    "capacity",        # alerta de sobrecarga (p. ej. 94% de conexiones)
    "access_blocked",  # bloqueo de ingreso / intentos superados
    "latency",         # lentitud sin caída
    "cert_expiry",     # certificado por vencer (mantenimiento periódico)
    "ui_cosmetic",     # ajuste visual de interfaz
    "other",
]

# Alcance del impacto; es lo que realmente decide la severidad, no la urgencia
# que exprese quien reporta.
ImpactScope = Literal["global", "individual", "staging"]


@dataclass(frozen=True)
class SLARule:
    """Define el acuerdo de nivel de servicio (SLA) para un nivel de severidad."""

    severity: SeverityLevel
    max_resolution_minutes: int
    operates_24x7: bool
    escalation_threshold_ratio: float = 0.75


@dataclass
class Incident:
    """Representa un incidente registrado en la plataforma IncidentOps."""

    incident_id: str
    title: str
    component: str
    severity: SeverityLevel
    status: IncidentStatus
    created_at: datetime
    resolved_at: Optional[datetime] = None
    symptom_category: Optional[SymptomCategory] = None


@dataclass(frozen=True)
class SLAEvaluation:
    """Resultado determinista de la evaluación de SLA de un incidente."""

    incident_id: str
    severity: SeverityLevel
    elapsed_minutes: int
    allowed_minutes: int
    remaining_minutes: int
    is_breached: bool
    requires_escalation: bool


@dataclass(frozen=True)
class TriageResult:
    """Resultado estructurado producido por el clasificador de triaje.

    `duplicate_group_key` sigue el formato `<component>:<symptom_category>`; dos
    incidentes con la misma clave se consideran candidatos a duplicado.
    """

    incident_id: str
    severity: SeverityLevel
    component: str
    rationale: str
    recommended_team: TeamName
    duplicate_group_key: str
    symptom_category: SymptomCategory = "other"
    impact_scope: ImpactScope = "global"
    consistency_ratio: float = 1.0
