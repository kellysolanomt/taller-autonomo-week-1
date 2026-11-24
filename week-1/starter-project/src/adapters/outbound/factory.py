"""Fábrica del repositorio de salida: selecciona la implementación vía `DATABASE_URL`.

Cableado concreto de borde (Constitución, Artículo 2.5 / Principio II): el dominio y la
aplicación nunca conocen qué motor concreto hay detrás de `IncidentRepositoryPort`.
"""

import os

from src.adapters.outbound.postgres_repository import PostgresIncidentRepository
from src.adapters.outbound.sqlite_repository import SQLiteIncidentRepository
from src.application.ports import IncidentRepositoryPort

_SQLITE_SCHEME = "sqlite:///"
_POSTGRESQL_SCHEME = "postgresql://"
_DEFAULT_DATABASE_URL = "sqlite:///:memory:"


def create_repository(database_url: str) -> IncidentRepositoryPort:
    """Construye el repositorio de incidentes a partir de un `database_url` explícito.

    Selecciona el adaptador exclusivamente por el esquema de la URL (H004, ADR-004):
    `postgresql://` → PostgreSQL vía `psycopg`; `sqlite:///` → SQLite de la biblioteca
    estándar. Cualquier otro esquema se rechaza de forma explícita, identificándolo (FR-007).
    """
    if database_url.startswith(_POSTGRESQL_SCHEME):
        return PostgresIncidentRepository(dsn=database_url)
    if database_url.startswith(_SQLITE_SCHEME):
        db_path = database_url[len(_SQLITE_SCHEME):]
        return SQLiteIncidentRepository(db_path=db_path)
    raise ValueError(
        f"Esquema de DATABASE_URL no soportado: {database_url!r}. "
        f"Solo se soportan '{_SQLITE_SCHEME}' y '{_POSTGRESQL_SCHEME}' en este corte (H004)."
    )


def get_incident_repository() -> IncidentRepositoryPort:
    """Construye el repositorio de incidentes a partir de la variable de entorno `DATABASE_URL`.

    Punto único que los adaptadores de entrada invocan; delega toda la lógica de
    selección en `create_repository` (Constitución, Principio II).
    """
    database_url = os.environ.get("DATABASE_URL", _DEFAULT_DATABASE_URL)
    return create_repository(database_url)
