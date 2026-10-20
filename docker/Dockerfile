FROM node:26-alpine@sha256:c9f02360d2bc66e709b300214395588acd2d3603f600db8141117e67c0faf4ff AS builder-node

WORKDIR /app/otterdog/webapp/static

# copy only the npm manifests first so `npm ci` layer stays cached
# across source-only edits (npm ci is by far the slowest step here)
COPY ./otterdog/webapp/static/package.json ./otterdog/webapp/static/package-lock.json ./

RUN npm ci

# now copy the rest of the source and build
COPY ./otterdog /app/otterdog

RUN npm run build

# build otterdog using a python environment
FROM python:3.14-slim@sha256:a2b82f3c48559aa0a8446d9af49826b6e2b2016f4cd2afabfe6013ec53729170 AS builder-python3

ARG version=0.0.0.dev0

WORKDIR /app

ENV PIP_DEFAULT_TIMEOUT=100 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    POETRY_VERSION=2.4.1 \
    POETRY_HOME='/usr/local' \
    POETRY_INSTALLER_ONLY_BINARY=:all: \
    POETRY_INSTALLER_NO_BINARY=github-flask,jsonbender \
    POETRY_DYNAMIC_VERSIONING_BYPASS=$version

# copy only dependency manifests first so `poetry install` layer stays
# cached across source-only edits (dependency resolution/install is the
# slowest step here)
COPY ./pyproject.toml ./poetry.lock ./README.md ./

RUN pip install --only-binary :all: "poetry-dynamic-versioning[plugin]==1.10.0" "poetry==${POETRY_VERSION}"

RUN poetry config virtualenvs.in-project true && \
    poetry install --only=main,app --no-root --no-interaction --no-ansi

# now copy the actual source and build/install the root package
COPY ./otterdog ./otterdog
COPY ./docker/hypercorn-cfg.toml ./
COPY ./docker/start-webapp ./docker/start-webapp
COPY ./docker/init-webapp ./docker/init-webapp

RUN poetry build && \
    poetry install --only-root

# create the final image having python3.12 as base
FROM python:3.14-slim@sha256:a2b82f3c48559aa0a8446d9af49826b6e2b2016f4cd2afabfe6013ec53729170

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
# number of worker processes of the webapp
ENV HYPERCORN_WORKERS=4

ENTRYPOINT ["/app/start-webapp"]
