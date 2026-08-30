# syntax=docker/dockerfile:1.7

FROM python:3.12-slim-bookworm

ARG PLATFORM_SOURCE_SHA=unknown
ARG PLATFORM_WHEEL_SHA256=unknown
ARG PLATFORM_DISTRIBUTION_EVIDENCE_SHA256=unknown
LABEL org.opencontainers.image.revision="${PLATFORM_SOURCE_SHA}" \
      org.opencontainers.image.research-platform.wheel.sha256="${PLATFORM_WHEEL_SHA256}" \
      org.opencontainers.image.research-platform.distribution-evidence.sha256="${PLATFORM_DISTRIBUTION_EVIDENCE_SHA256}"

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PLATFORM_STATE_DIR=/var/lib/research-platform \
    PLATFORM_EMBEDDED_WHEEL=/opt/research-platform-artifact/research_platform.whl

WORKDIR /opt/research-platform
COPY research_platform.whl /opt/research-platform-artifact/research_platform.whl
COPY container-entrypoint.sh /usr/local/bin/research-platform-entrypoint

RUN printf '%s  %s\n' "$PLATFORM_WHEEL_SHA256" "$PLATFORM_EMBEDDED_WHEEL" | sha256sum -c - \
    && python -m pip install --no-deps "$PLATFORM_EMBEDDED_WHEEL" \
    && chmod 0444 "$PLATFORM_EMBEDDED_WHEEL" \
    && chmod 0755 /usr/local/bin/research-platform-entrypoint

RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin platform \
    && mkdir -p "$PLATFORM_STATE_DIR" \
    && chown -R platform:platform /opt/research-platform "$PLATFORM_STATE_DIR"

USER platform
ENTRYPOINT ["/usr/local/bin/research-platform-entrypoint"]
CMD ["doctor"]
