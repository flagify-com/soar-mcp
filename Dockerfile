# SOAR MCP Server Docker Image

ARG PYTHON_IMAGE=python:3.11-slim
FROM ${PYTHON_IMAGE}

ARG VERSION=dev
ARG USE_CHINA_MIRRORS=false

LABEL org.opencontainers.image.title="soar-mcp"
LABEL org.opencontainers.image.description="SOAR MCP Server for OctoMation"
LABEL org.opencontainers.image.version="${VERSION}"
LABEL org.opencontainers.image.source="https://github.com/flagify-com/soar-mcp"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    TZ=Asia/Shanghai \
    MCP_PORT=12345 \
    ADMIN_PORT=12346 \
    BIND_HOST=0.0.0.0

WORKDIR /app

# Optional China mainland mirrors for local builds:
# docker build --build-arg USE_CHINA_MIRRORS=true .
RUN if [ "$USE_CHINA_MIRRORS" = "true" ]; then \
        sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources \
        && sed -i 's/security.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources; \
    fi

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN if [ "$USE_CHINA_MIRRORS" = "true" ]; then \
        pip install --no-cache-dir -r requirements.txt \
            -i https://mirrors.aliyun.com/pypi/simple/ \
            --trusted-host mirrors.aliyun.com; \
    else \
        pip install --no-cache-dir -r requirements.txt; \
    fi

COPY . .

RUN mkdir -p /app/logs /app/data

EXPOSE 12345 12346

ENTRYPOINT []

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:${ADMIN_PORT}/login || exit 1

CMD ["python", "soar_mcp_server.py"]
