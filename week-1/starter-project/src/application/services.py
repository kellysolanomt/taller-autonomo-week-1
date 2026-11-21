"""Caso de uso compartido de triaje, consumido por los adaptadores de entrada.

Valida la forma de la solicitud una sola vez aquí (no en cada adaptador) y delega
la clasificación en el motor de dominio puro (`src.domain.triage_rules`).
"""

from src.domain.models import TriageResult
from src.domain.triage_rules import classify_incident_report

MAX_INCIDENT_ID_LENGTH = 100
MAX_RAW_TEXT_LENGTH = 4000


class ValidationError(Exception):
    """Solicitud de triaje con campos vacíos o fuera de los límites permitidos."""


class IncidentService:
    """Caso de uso de triaje, reutilizable por cualquier adaptador de entrada."""

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
