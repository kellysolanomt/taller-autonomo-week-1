# Imagen reproducible del servicio api (H004, ADR-004).
FROM python:3.12-slim

# Copia el binario de uv desde la imagen oficial (sin instalar vía pip).
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Instala solo las dependencias de producción, de forma reproducible (uv.lock fijo).
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Copia el código fuente del servicio.
COPY src/ ./src/

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "src.adapters.inbound.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
