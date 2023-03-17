# build jsonnet-bundler using a go environment
FROM docker.io/library/golang:1.18 AS builder-go
RUN go install -a github.com/jsonnet-bundler/jsonnet-bundler/cmd/jb@latest

# build otterdog using a python environment
FROM docker.io/library/python:3.10.10-slim as builder-python3

WORKDIR /app

ENV PIP_DEFAULT_TIMEOUT=100 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    POETRY_VERSION=1.4.0

COPY otterdog ./otterdog
COPY otterdog.* ./
COPY pyproject.toml poetry.lock README.md ./

RUN pip install "poetry==$POETRY_VERSION"

RUN poetry config virtualenvs.in-project true && \
    poetry install --only=main --no-root && \
    poetry build && \
    poetry install --only-root

# create the final image having python3.10 as base
FROM python:3.10.10-slim

RUN apt-get update \
    && apt-get install -y \
        jq \
        pass \
        curl \
        unzip \
        jsonnet

ARG BW_VERSION
ARG BW_RELEASE
ENV BW_VERSION=${BW_VERSION}
ENV BW_RELEASE=${BW_RELEASE}

RUN cd /tmp/ && curl -k -L -O https://github.com/bitwarden/clients/releases/download/${BW_RELEASE}/${BW_VERSION} \
    && unzip /tmp/${BW_VERSION} -d /usr/bin/ && rm -rf /tmp/${BW_VERSION}

COPY --from=builder-go /go/bin/jb /usr/bin/jb
COPY --from=builder-python3 /app/.venv /app/.venv
COPY --from=builder-python3 /app/otterdog /app/otterdog
COPY --from=builder-python3 /app/otterdog.sh /app/otterdog.sh

WORKDIR /app

RUN ./.venv/bin/playwright install-deps firefox && \
    ./.venv/bin/playwright install firefox

ENTRYPOINT ["/app/otterdog.sh"]
