FROM node:20-alpine@sha256:c13b26e7e602ef2f1074aef304ce6e9b7dd284c419b35d89fcf3cc8e44a8def9 AS builder-node

WORKDIR /app

COPY ./otterdog ./otterdog

WORKDIR /app/otterdog/webapp/static

RUN npm ci
RUN npm run build

# build otterdog using a python environment
FROM python:3.12.7-slim@sha256:032c52613401895aa3d418a4c563d2d05f993bc3ecc065c8f4e2280978acd249 AS builder-python3

ARG version

RUN apt-get update \
    && apt-get install -y \
        curl

WORKDIR /app

ENV PIP_DEFAULT_TIMEOUT=100 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    POETRY_VERSION=2.0.1 \
    POETRY_HOME='/usr/local' \
    POETRY_DYNAMIC_VERSIONING_BYPASS=$version

COPY ./otterdog ./otterdog
COPY ./pyproject.toml ./poetry.lock ./README.md ./docker/hypercorn-cfg.toml ./
COPY ./docker/start-webapp ./docker/start-webapp
COPY ./docker/init-webapp ./docker/init-webapp

RUN curl -sSL https://install.python-poetry.org | python -

RUN poetry self add "poetry-dynamic-versioning[plugin]"

RUN poetry config virtualenvs.in-project true && \
    poetry install --only=main,app --no-root && \
    poetry build && \
    poetry install --only-root

# create the final image having python3.12 as base
FROM python:3.12.7-slim@sha256:032c52613401895aa3d418a4c563d2d05f993bc3ecc065c8f4e2280978acd249

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        git \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder-python3 /app/.venv /app/.venv
COPY --from=builder-python3 /app/otterdog /app/otterdog
COPY --from=builder-python3 /app/docker/start-webapp /app/start-webapp
COPY --from=builder-python3 /app/docker/init-webapp /app/init-webapp
COPY --from=builder-python3 /app/hypercorn-cfg.toml /app/hypercorn-cfg.toml
COPY --from=builder-node /app/otterdog/webapp/static/assets /app/otterdog/webapp/static/assets

RUN chmod +x /app/start-webapp
RUN chmod +x /app/init-webapp

WORKDIR /app

# set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["/app/start-webapp"]
