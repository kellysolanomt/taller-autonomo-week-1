"""Fábrica del repositorio de salida: selecciona la implementación vía `DATABASE_URL`.

Cableado concreto de borde (Constitución, Artículo 2.5 / Principio II): el dominio y la
aplicación nunca conocen qué motor concreto hay detrás de `IncidentRepositoryPort`.
"""

import os

from src.adapters.outbound.sqlite_repository import SQLiteIncidentRepository
from src.application.ports import IncidentRepositoryPort

_SQLITE_SCHEME = "sqlite:///"
_DEFAULT_DATABASE_URL = "sqlite:///:memory:"


def get_incident_repository() -> IncidentRepositoryPort:
    """Construye el repositorio de incidentes a partir de `DATABASE_URL`.

    Solo se soporta el esquema `sqlite:///` en este corte (H002); cualquier otro esquema
    queda fuera de alcance y se difiere a H004 (Constitución 3.2: cambiar de motor exige
    un ADR aprobado previamente).
    """
    database_url = os.environ.get("DATABASE_URL", _DEFAULT_DATABASE_URL)
    if not database_url.startswith(_SQLITE_SCHEME):
        raise ValueError(
            f"Esquema de DATABASE_URL no soportado: {database_url!r}. "
            f"Solo se soporta '{_SQLITE_SCHEME}' en este corte (H002)."
        )
    db_path = database_url[len(_SQLITE_SCHEME):]
    return SQLiteIncidentRepository(db_path=db_path)
