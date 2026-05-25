FROM python:3.11-slim

# Install Chromium for nodriver (optional — needed for JS-heavy pages)
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml ./
COPY src/ ./src/

RUN pip install --no-cache-dir -e ".[dev]"

# Default: HTTP transport so Docker users can hit it via REST
EXPOSE 8000
ENV FASTMCP_HOST=0.0.0.0
ENV FASTMCP_PORT=8000

CMD ["mcp-web-search", "--http"]
