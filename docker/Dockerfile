FROM node:26-alpine@sha256:6bd9ab43c0ec0190ca7b2d193906cb8b7edf6e7f4afa43ddeccd6452710bffb5 AS builder-node

WORKDIR /app/otterdog/webapp/static

# copy only the npm manifests first so `npm ci` layer stays cached
# across source-only edits (npm ci is by far the slowest step here)
COPY ./otterdog/webapp/static/package.json ./otterdog/webapp/static/package-lock.json ./

RUN npm ci

# now copy the rest of the source and build
COPY ./otterdog /app/otterdog

RUN npm run build

# build otterdog using a python environment
FROM python:3.15-slim@sha256:65a65fc7b30b06cb6df4930fd4650697cb23f4c2698ab81fc87e4b031bc36928 AS builder-python3

ARG version=0.0.0.dev0

WORKDIR /app

# jsonbender only publishes a source distribution. PyYAML 6.0.3 has no wheel for Python 3.15: it is built from its
# source distribution, without a compiler its pure Python implementation is installed (otterdog only uses
# yaml.safe_load). Remove pyyaml from POETRY_INSTALLER_NO_BINARY once PyYAML publishes wheels for Python 3.15.
ENV PIP_DEFAULT_TIMEOUT=100 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    POETRY_VERSION=2.5.1 \
    POETRY_HOME='/usr/local' \
    POETRY_INSTALLER_ONLY_BINARY=:all: \
    POETRY_INSTALLER_NO_BINARY=jsonbender,pyyaml \
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

# create the final image having python3.15 as base
FROM python:3.15-slim@sha256:65a65fc7b30b06cb6df4930fd4650697cb23f4c2698ab81fc87e4b031bc36928

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

# the webapp runs as an unprivileged user, with a numeric id so that Kubernetes can check it with runAsNonRoot.
# The files of the application stay owned by root, it only writes in its APP_ROOT, /app/work by default (an emptyDir
# volume in the helm chart), and in the temporary directory.
RUN chmod 0755 /app/start-webapp /app/init-webapp \
    && groupadd --gid 1000 otterdog \
    && useradd --uid 1000 --gid otterdog --create-home --home-dir /home/otterdog --shell /usr/sbin/nologin otterdog \
    && mkdir /app/work \
    && chown otterdog:otterdog /app/work

WORKDIR /app

# set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
# number of worker processes of the webapp
ENV HYPERCORN_WORKERS=4

USER 1000:1000

ENTRYPOINT ["/app/start-webapp"]
