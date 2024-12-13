# Stage 1: Base image with security hardening
FROM python:3.8-slim AS base
LABEL maintainer="DevOps Team"
LABEL version="1.0"
LABEL description="Production Flask REST API backend for Specification Management System"

# Set working directory
WORKDIR /app

# Configure Python environment
ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    POETRY_VERSION=1.0.0 \
    POETRY_HOME=/opt/poetry \
    POETRY_VIRTUALENVS_CREATE=false

# Security updates and system dependencies
RUN apt-get update \
    && apt-get upgrade -y \
    && apt-get install -y --no-install-recommends \
        curl \
        gcc \
        libc6-dev \
    && rm -rf /var/lib/apt/lists/* \
    && curl -sSL https://install.python-poetry.org | python3 - \
    && ln -s /opt/poetry/bin/poetry /usr/local/bin/poetry

# Stage 2: Install dependencies
FROM base AS dependencies

# Copy dependency files
COPY pyproject.toml poetry.lock ./

# Install production dependencies only
RUN poetry config virtualenvs.create false \
    && poetry install --no-dev --no-interaction --no-ansi \
    && pip uninstall poetry -y \
    && apt-get purge -y --auto-remove gcc libc6-dev \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /root/.cache/pip/*

# Stage 3: Final production image
FROM python:3.8-slim AS production

# Set working directory and environment variables
WORKDIR /app
ENV PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    GUNICORN_CMD_ARGS="--workers=2 --threads=4 --timeout=0 --worker-class=gthread"

# Create non-root user
RUN groupadd -g 10001 nonroot && \
    useradd -u 10001 -g nonroot -s /bin/bash -m nonroot

# Copy dependencies from previous stage
COPY --from=dependencies /usr/local/lib/python3.8/site-packages /usr/local/lib/python3.8/site-packages
COPY --from=dependencies /usr/local/bin /usr/local/bin

# Copy application code
COPY --chown=nonroot:nonroot . .

# Set proper permissions
RUN chmod 755 /app \
    && find /app -type f -exec chmod 644 {} \; \
    && find /app -type d -exec chmod 755 {} \; \
    && chmod 755 /app/wsgi.py \
    && chown -R nonroot:nonroot /app

# Switch to non-root user
USER nonroot

# Expose port
EXPOSE 8000

# Health check configuration
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Start Gunicorn
ENTRYPOINT ["gunicorn"]
CMD ["--bind", "0.0.0.0:8000", "--config", "gunicorn_config.py", "wsgi:application"]