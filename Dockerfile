# One container runs the whole daily cycle: fetch (Python) -> build the
# dashboard (Node) -> deploy to Netlify (netlify-cli). Two runtimes in one
# image on purpose -- splitting into separate containers would need shared
# storage and an orchestrator for a single-writer, once-a-day job that isn't
# worth the extra moving parts on a server.
FROM node:22-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-venv \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY backend/ backend/
COPY frontend/ frontend/

RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
# Locked exact versions first (see backend/requirements-lock.txt), then the
# local package with --no-deps so it can't silently pull in anything looser.
RUN pip install --no-cache-dir -r backend/requirements-lock.txt
RUN pip install --no-cache-dir --no-deps -e backend/

RUN npm --prefix frontend ci
RUN npm install -g netlify-cli

COPY docker-entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

WORKDIR /app/backend
ENTRYPOINT ["/entrypoint.sh"]
