"""Casos de uso compartidos de triaje y resumen de incidentes activos (H001/H002).

Valida la forma de la solicitud de triaje una sola vez aquí (no en cada adaptador) y
delega la clasificación en el motor de dominio puro (`src.domain.triage_rules`). El
resumen de incidentes activos orquesta el puerto de salida (`IncidentRepositoryPort`)
y el calculador de SLA (`src.domain.sla_calculator`), sin reimplementar ninguna regla
de negocio: el repositorio solo persiste, el dominio solo calcula.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from src.application.ports import IncidentRepositoryPort
from src.domain.models import IncidentStatus, SeverityLevel, TriageResult
from src.domain.sla_calculator import evaluate_sla_status
from src.domain.triage_rules import classify_incident_report

MAX_INCIDENT_ID_LENGTH = 100
MAX_RAW_TEXT_LENGTH = 4000


class ValidationError(Exception):
    """Solicitud de triaje con campos vacíos o fuera de los límites permitidos."""


@dataclass(frozen=True)
class ActiveIncidentSummaryItem:
    """Detalle de un incidente activo dentro del resumen (data-model.md)."""

    incident_id: str
    title: str
    component: str
    severity: SeverityLevel
    status: IncidentStatus
    elapsed_minutes: int
    requires_escalation: bool


@dataclass(frozen=True)
class ActiveIncidentsSummary:
    """Resultado agregado del resumen de incidentes activos (data-model.md)."""

    total_active: int
    breached_count: int
    incidents: list[ActiveIncidentSummaryItem]


class IncidentService:
    """Casos de uso de triaje y resumen, reutilizables por cualquier adaptador de entrada."""

    def __init__(self, repository: IncidentRepositoryPort) -> None:
        self._repository = repository

    def check_health(self) -> bool:
        """Verifica la conectividad real con el repositorio inyectado (H004).

        Delega exactamente en `IncidentRepositoryPort.check_health()`; no añade ninguna
        regla de negocio ni transforma el resultado (data-model.md → `IncidentService.check_health()`).
        """
        return self._repository.check_health()

    def triage_incident(self, incident_id: str, raw_text: str) -> TriageResult:
        """Valida la solicitud y clasifica el reporte de incidente.

        Raises:
            ValidationError: si `incident_id` o `raw_text` están vacíos (tras
                `.strip()`) o exceden su longitud máxima permitida.
        """
        clean_incident_id = incident_id.strip()
        if not clean_incident_id:
            raise ValidationError("incident_id no puede estar vacío.")
        if len(clean_incident_id) > MAX_INCIDENT_ID_LENGTH:
            raise ValidationError(
                f"incident_id excede el máximo de {MAX_INCIDENT_ID_LENGTH} caracteres."
            )

        if not raw_text.strip():
            raise ValidationError("raw_text no puede estar vacío.")
        if len(raw_text) > MAX_RAW_TEXT_LENGTH:
            raise ValidationError(
                f"raw_text excede el máximo de {MAX_RAW_TEXT_LENGTH} caracteres."
            )

        return classify_incident_report(clean_incident_id, raw_text)

    def get_active_incidents_summary(
        self, component_filter: Optional[str], reference_time: datetime
    ) -> ActiveIncidentsSummary:
        """Calcula el resumen de incidentes activos (total, incumplimientos y detalle).

        `reference_time` es siempre un argumento obligatorio: este método nunca lee el
        reloj del sistema (Constitución 1.2 / Principio I). El valor por defecto
        "instante de la consulta" (FR-013) se resuelve en el adaptador de entrada, no
        aquí. No valida `component_filter`: cualquier cadena es un filtro legal, incluida
        una que no coincida con ningún incidente activo (FR-008).
        """
        incidents = self._repository.list_active_incidents(component_filter)

        items: list[ActiveIncidentSummaryItem] = []
        breached_count = 0
        for incident in incidents:
            evaluation = evaluate_sla_status(incident, reference_time=reference_time)
            if evaluation.is_breached:
                breached_count += 1
            items.append(
                ActiveIncidentSummaryItem(
                    incident_id=incident.incident_id,
                    title=incident.title,
                    component=incident.component,
                    severity=incident.severity,
                    status=incident.status,
                    elapsed_minutes=evaluation.elapsed_minutes,
                    requires_escalation=evaluation.requires_escalation,
                )
            )

        return ActiveIncidentsSummary(
            total_active=len(items),
            breached_count=breached_count,
            incidents=items,
        )
