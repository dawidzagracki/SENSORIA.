# syntax=docker/dockerfile:1
FROM ghcr.io/astral-sh/uv:0.12.23 AS uv-bin

FROM python:3.12-slim AS base
COPY --from=uv-bin /uv /uvx /bin/
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

FROM base AS production-dependencies
COPY apps/api/pyproject.toml apps/api/uv.lock ./
COPY apps/api/src ./src
COPY apps/api/alembic.ini ./alembic.ini
COPY apps/api/alembic ./alembic
RUN uv sync --locked --no-dev

FROM base AS development-dependencies
COPY apps/api/pyproject.toml apps/api/uv.lock ./
COPY apps/api/src ./src
COPY apps/api/alembic.ini ./alembic.ini
COPY apps/api/alembic ./alembic
RUN uv sync --locked

FROM python:3.12-slim AS runtime
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
RUN groupadd --system --gid 10001 sensoria \
    && useradd --system --uid 10001 --gid sensoria --home-dir /home/sensoria --create-home sensoria \
    && mkdir -p /app/uploads \
    && chmod 0700 /app/uploads \
    && chown -R sensoria:sensoria /app /home/sensoria
COPY --from=production-dependencies --chown=sensoria:sensoria /opt/venv /opt/venv
COPY --from=production-dependencies --chown=sensoria:sensoria /app /app
USER 10001:10001
EXPOSE 8000
ENTRYPOINT ["python", "-m", "uvicorn"]
CMD ["sensoria.main:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "info", "--no-access-log"]

FROM development-dependencies AS development
RUN groupadd --system --gid 10001 sensoria \
    && useradd --system --uid 10001 --gid sensoria --home-dir /home/sensoria --create-home sensoria \
    && mkdir -p /app/uploads \
    && chmod 0700 /app/uploads \
    && chown -R sensoria:sensoria /app /home/sensoria /opt/venv
USER 10001:10001
EXPOSE 8000
ENTRYPOINT ["/opt/venv/bin/python", "-m", "uvicorn"]
CMD ["sensoria.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--log-level", "debug", "--no-access-log"]
