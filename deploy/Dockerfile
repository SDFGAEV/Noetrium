# syntax=docker/dockerfile:1.7

FROM python:3.12-slim-bookworm AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build
COPY pyproject.toml README.md ./
COPY research_platform ./research_platform

RUN python -m pip install --upgrade pip setuptools wheel \
    && python -m pip wheel --no-deps --wheel-dir /wheelhouse .

FROM python:3.12-slim-bookworm

ARG PLATFORM_SOURCE_SHA=unknown
LABEL org.opencontainers.image.revision="${PLATFORM_SOURCE_SHA}"

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PLATFORM_STATE_DIR=/var/lib/research-platform

WORKDIR /opt/research-platform
COPY --from=builder /wheelhouse /tmp/wheelhouse
COPY deploy/container-entrypoint.sh /usr/local/bin/research-platform-entrypoint

RUN python -m pip install --no-deps /tmp/wheelhouse/research_platform-*.whl \
    && rm -rf /tmp/wheelhouse \
    && chmod 0755 /usr/local/bin/research-platform-entrypoint

RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin platform \
    && mkdir -p "$PLATFORM_STATE_DIR" \
    && chown -R platform:platform /opt/research-platform "$PLATFORM_STATE_DIR"

USER platform
ENTRYPOINT ["/usr/local/bin/research-platform-entrypoint"]
CMD ["doctor"]
