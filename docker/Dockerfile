# build jsonnet-bundler using a go environment
FROM golang:1.18 AS builder-go
RUN go install -a github.com/jsonnet-bundler/jsonnet-bundler/cmd/jb@v0.5.1

# build otterdog using a python environment
FROM python:3.12.2-slim as builder-python3

RUN apt-get update \
    && apt-get install -y \
        golang gcc patch

WORKDIR /app

ENV PIP_DEFAULT_TIMEOUT=100 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    POETRY_VERSION=1.7.1

COPY ./otterdog ./otterdog
COPY ./pyproject.toml ./poetry.lock ./README.md ./docker/hypercorn-cfg.toml ./
COPY ./docker/entrypoint.sh ./docker/entrypoint.sh
COPY ./docker/start-webapp ./docker/start-webapp
COPY ./docker/init-webapp ./docker/init-webapp

RUN pip install "poetry==$POETRY_VERSION"

RUN poetry config virtualenvs.in-project true && \
    poetry install --only=main,app --no-root && \
    poetry build && \
    poetry install --only-root

WORKDIR /app/.venv/lib/python3.12/site-packages
COPY ./docker/odmantic.patch ./
RUN patch -p1 < odmantic.patch

# create the final image having python3.12 as base
FROM python:3.12.2-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        git \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder-go /go/bin/jb /usr/bin/jb
COPY --from=builder-python3 /app/.venv /app/.venv
COPY --from=builder-python3 /app/otterdog /app/otterdog
COPY --from=builder-python3 /app/docker/entrypoint.sh /app/entrypoint.sh
COPY --from=builder-python3 /app/docker/start-webapp /app/start-webapp
COPY --from=builder-python3 /app/docker/init-webapp /app/init-webapp
COPY --from=builder-python3 /app/hypercorn-cfg.toml /app/hypercorn-cfg.toml

RUN chmod +x /app/entrypoint.sh
RUN chmod +x /app/start-webapp
RUN chmod +x /app/init-webapp

WORKDIR /app

# set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

ENTRYPOINT ["/app/entrypoint.sh"]
