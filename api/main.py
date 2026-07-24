"""
Main FastAPI application. Mounts all feature routers.

Run locally:
    uvicorn api.main:app --reload

Run in a container (Catalyst AppSail or otherwise):
    uvicorn api.main:app --host 0.0.0.0 --port $X_ZOHO_CATALYST_LISTEN_PORT
"""
import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from api.rate_limiter import limiter
from api.routes import audio, chat, analytics, map_routes, graph, conversations, offenders, sociology

# Load .env explicitly here, before reading any env vars below. Don't rely on
# some other imported module (db/connection.py, gemini_provider.py, etc.)
# happening to call load_dotenv() first as a side effect of import order --
# that's fragile and broke locally on Windows when this file's own env read
# ran before any of those modules had been touched.
load_dotenv()

app = FastAPI(title="Vetro AI — KSP Crime Data Platform", version="0.1.0")

# Rate limiting, per the vulnerability review in docs/PRD.md: /chat has
# no auth in front of it yet and triggers a real, billed Gemini call
# per request -- without a limit, it's a direct cost/DoS exposure.
# Keyed by remote IP (get_remote_address, see api/rate_limiter.py)
# since there's no per-user identity to key on yet. The actual limit
# is applied per-route via @limiter.limit(...) (see api/routes/chat.py)
# rather than globally here, since different routes warrant different
# limits (chat calls an LLM and costs money per request; analytics/
# map/graph just query the DB and can tolerate a much higher rate).
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS supports a permissive local-development mode so a Vite dev server can
# always receive structured API errors. In production set
# CORS_ALLOW_ALL_ORIGINS=false and provide the explicit deployed origins.
_cors_origins_env = os.environ.get("CORS_ALLOWED_ORIGINS", "")
_allowed_origins = [o.strip() for o in _cors_origins_env.split(",") if o.strip()]
_allow_all_origins = os.environ.get("CORS_ALLOW_ALL_ORIGINS", "true").lower() in {
    "1", "true", "yes",
}

if not _allow_all_origins and not _allowed_origins:
    raise RuntimeError(
        "CORS_ALLOWED_ORIGINS is not set. Set it in .env (local) or the AppSail "
        "console (deployed) to a comma-separated list of allowed frontend origins."
    )

app.add_middleware(
    CORSMiddleware,
    # Wildcard origins and credentialed cookies are mutually exclusive in
    # browsers. This API uses header-based owner tokens, not browser cookies.
    allow_origins=["*"] if _allow_all_origins else _allowed_origins,
    allow_credentials=False if _allow_all_origins else True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router, prefix="/chat", tags=["chatbot"])
app.include_router(audio.router, prefix="/audio", tags=["audio"])
app.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
app.include_router(map_routes.router, prefix="/map", tags=["map"])
app.include_router(graph.router, prefix="/graph", tags=["graph"])
app.include_router(conversations.router, prefix="/conversations", tags=["conversations"])
app.include_router(offenders.router, prefix="/offenders", tags=["offenders"])
app.include_router(sociology.router, prefix="/sociology", tags=["sociology"])


@app.get("/")
def health_check():
    return {"status": "ok", "service": "Vetro AI — KSP Crime Data Platform"}
