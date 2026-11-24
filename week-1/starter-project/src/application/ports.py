"""Puerto de salida de persistencia, consumido por `IncidentService` y la aplicación.

Define el contrato que cualquier adaptador de salida (SQLite hoy, una base relacional
dedicada en H004) debe cumplir. La aplicación y el dominio solo conocen este `Protocol`,
nunca una implementación concreta.
"""

from typing import Optional, Protocol, runtime_checkable

from src.domain.models import Incident


@runtime_checkable
class IncidentRepositoryPort(Protocol):
    """Puerto de salida de persistencia de incidentes."""

    def save_incident(self, incident: Incident) -> None:
        """Crea o reemplaza un incidente."""

    def get_incident(self, incident_id: str) -> Optional[Incident]:
        """Obtiene un incidente por su identificador, o `None` si no existe."""

    def find_open_duplicates(self, component: str, symptom_category: str) -> list[Incident]:
        """Incidentes activos que comparten `<component>:<symptom_category>` (preparación H003)."""

    def list_active_incidents(self, component_filter: Optional[str] = None) -> list[Incident]:
        """Incidentes en estado `OPEN` o `IN_PROGRESS`, opcionalmente acotados a un componente."""

    def check_health(self) -> bool:
        """Verifica la conectividad con el almacenamiento subyacente (preparación H004)."""
