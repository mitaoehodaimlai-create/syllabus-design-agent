"""
STEP 6 — FastAPI Application
-------------------------------
Wires everything together:
  - init_db() on startup (creates tables if missing)
  - Mounts auth_routes   → /auth/*
  - Mounts upload_routes → /upload/*
  - Global exception handlers
  - CORS (configure origins for your frontend)

Run:
  cd syllabus_agent
  uvicorn api.app:app --reload --port 8000
"""

import sys
from pathlib import Path

# Make root importable (agent, models, pdf_generator live at root)
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.database import init_db
from api.routes.auth_routes import router as auth_router
from api.routes.upload_routes import router as upload_router


# ── App instance ──────────────────────────────────────────────────
app = FastAPI(
    title="Syllabus Design Agent API",
    description=(
        "OBE-aligned Syllabus Generator powered by Google Gemini.\n\n"
        "**Authentication:** All upload endpoints require admin JWT.\n\n"
        "**Flow:** Register → Login → Get JWT → Upload JSON → Poll Status → Download PDF"
    ),
    version="1.0.0",
    docs_url="/docs",        # Swagger UI
    redoc_url="/redoc",      # ReDoc UI
)

# ── CORS (allow your frontend origin in production) ───────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],     # tighten to specific origins in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Startup: create DB tables ─────────────────────────────────────
@app.on_event("startup")
def startup():
    init_db()


# ── Global error handler ──────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {str(exc)}"},
    )

# ── Routers ───────────────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(upload_router)


# ── Health check ──────────────────────────────────────────────────
@app.get("/", tags=["Health"])
def root():
    return {"status": "ok", "service": "Syllabus Design Agent API"}


@app.get("/health", tags=["Health"])
def health():
    return {"status": "healthy"}
