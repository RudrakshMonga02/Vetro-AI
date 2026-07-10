# Vetro AI — backend container for Catalyst AppSail (custom OCI runtime).
#
# Matches app-config.json's "python_3_13" stack for consistency in case the
# managed-runtime path is ever used instead of this container path.
#
# Build & test locally before pushing to AppSail:
#   docker build -t vetro-ai-backend .
#   docker run -p 9000:9000 -e X_ZOHO_CATALYST_LISTEN_PORT=9000 \
#       -e CORS_ALLOWED_ORIGINS=http://localhost:5173 \
#       -e GEMINI_API_KEY=your_key_here \
#       -e DATABASE_URL=postgresql+psycopg2://... \
#       vetro-ai-backend
#   curl http://localhost:9000/
#
# AppSail specifics this Dockerfile respects (per Catalyst AppSail docs):
#   - Must bind 0.0.0.0, not 127.0.0.1
#   - Must listen on the port given via X_ZOHO_CATALYST_LISTEN_PORT (injected at
#     runtime by AppSail) -- falls back to 9000 for local/manual runs
#   - No specific health-check path required; AppSail does a TCP liveness check
#   - No secrets baked into the image -- all config comes from runtime env vars

FROM python:3.13-slim

WORKDIR /app

# Install system deps needed by psycopg2-binary / chromadb before copying code,
# so this layer caches independently of application code changes.
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Fallback port for local `docker run` without AppSail's injected env var.
ENV X_ZOHO_CATALYST_LISTEN_PORT=9000
EXPOSE 9000

# Shell form (not exec-array form) so $X_ZOHO_CATALYST_LISTEN_PORT is expanded
# by the shell at container start -- AppSail injects this at runtime, so it
# can't be baked in as a literal at build time.
CMD uvicorn api.main:app --host 0.0.0.0 --port $X_ZOHO_CATALYST_LISTEN_PORT
