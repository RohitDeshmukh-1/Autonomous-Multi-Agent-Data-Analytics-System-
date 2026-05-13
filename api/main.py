"""
api/main.py
FastAPI application — mounts all routers, configures CORS, rate limiting, lifespan.
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from api.routers import query, upload, history, dashboard, report, schema
from api.routers import metrics as metrics_router
from api.routers import profile as profile_router


# ── Rate limiter ──────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: pre-warm LLM clients + embedding model
    from llm import get_groq_client, get_embedder
    get_groq_client()
    # Pre-download and load embedding model (first run downloads ~420MB)
    print("⏳ Loading embedding model (first run may download ~420MB)...")
    get_embedder()
    print("✅ Embedding model loaded.")
    yield
    # Shutdown: close DB pool
    try:
        from db.pool import get_pool
        get_pool().closeall()
    except Exception:
        pass


app = FastAPI(
    title="Cloud Data Analyst Agent",
    version="2.0.0",
    description="AI-powered data analyst with self-correcting LangGraph agent, "
                "multi-turn conversations, anomaly detection, and real-time observability.",
    docs_url="/docs",
    lifespan=lifespan,
)

# Attach rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS — allow the Vite frontend and any Render preview URL
ALLOWED_ORIGINS = os.environ.get(
    "ALLOWED_ORIGINS",
    "http://localhost:5173,http://localhost:3000",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if os.environ.get("DEMO_MODE") == "true" else ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(query.router,            prefix="/api/query",     tags=["query"])
app.include_router(upload.router,           prefix="/api/upload",    tags=["upload"])
app.include_router(history.router,          prefix="/api/history",   tags=["history"])
app.include_router(dashboard.router,        prefix="/api/dashboard", tags=["dashboard"])
app.include_router(report.router,           prefix="/api/report",    tags=["report"])
app.include_router(schema.router,           prefix="/api/schema",    tags=["schema"])
app.include_router(metrics_router.router,   prefix="/api/metrics",   tags=["metrics"])
app.include_router(profile_router.router,   prefix="/api/profile",   tags=["profile"])


@app.get("/health")
async def health():
    return {"status": "ok", "version": "2.0.0"}
