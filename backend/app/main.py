import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.v1.router import api_router
from app.core.config import settings
from app.db.session import engine
from app.db.base import Base

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Auto-create tables on startup (useful for local development/MVP)
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        print(f"Warning: Database table auto-creation failed: {e}")
    yield

app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)


# Configure CORS. Kept open so the frontend can also be served separately
# (e.g. `python -m http.server`) during development if you don't want it
# served by this app.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins for development ease
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routers first so they take priority over the static mount below.
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/health")
def health_check():
    """Simple status check to verify API is online."""
    return {"status": "ok", "app": settings.PROJECT_NAME}


# ---------------------------------------------------------------------------
# Frontend
# ---------------------------------------------------------------------------
# Serves the static frontend (index.html + assets/) from the same origin and
# port as the API, so the browser never has to deal with cross-origin
# requests or a separately-configured API base URL. Project layout expected:
#
#   project_root/
#     backend/app/main.py   <- this file
#     frontend/index.html
#     frontend/assets/...
#
# Mounted last (and at "/") so it only catches requests that didn't match an
# API route above. If the frontend/ folder isn't present (e.g. API-only
# deployment), this is skipped instead of crashing on startup.
FRONTEND_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "frontend",
)
if os.path.isdir(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
