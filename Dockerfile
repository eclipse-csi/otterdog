FROM docker.io/library/golang:1.18 AS builder-go
RUN go install -a github.com/jsonnet-bundler/jsonnet-bundler/cmd/jb@latest


FROM docker.io/library/ubuntu:22.04 as builder-runtime

ARG BW_VERSION
ARG BW_RELEASE
ENV BW_VERSION=${BW_VERSION}
ENV BW_RELEASE=${BW_RELEASE}


RUN apt-get update \
    && apt-get install -y \
        jq \
        pass \
        curl \ 
        unzip \
        build-essential \
        git \
        python3 \
        python3-setuptools \
        python3.10-venv \
        python3.10-dev \
        jsonnet

WORKDIR /app
COPY otterdog /app/otterdog
COPY otterdog.* /app/
COPY *.md /app/
COPY requirements.txt /app/
COPY --from=builder-go /go/bin/jb /usr/bin/jb
RUN python3 -m venv /app/venv \ 
    && /app/venv/bin/pip3 install -r /app/requirements.txt \
    && /app/venv/bin/playwright install-deps
RUN cd /tmp/ && curl -k -L -O https://github.com/bitwarden/clients/releases/download/${BW_RELEASE}/${BW_VERSION} \ 
    && unzip /tmp/${BW_VERSION} -d /usr/bin/ && rm -rf /tmp/${BW_VERSION}


FROM ubuntu:22.04
COPY --from=builder-runtime /usr /usr
COPY --from=builder-runtime /etc /etc
COPY --from=builder-runtime /app /app
RUN /app/venv/bin/playwright install chromium 
WORKDIR /app


ENTRYPOINT ["/app/otterdog.sh"]