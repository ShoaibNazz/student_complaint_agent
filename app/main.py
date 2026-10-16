"""FastAPI application entry point."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import SQLAlchemyError

from app.api import admin, auth, complaints, dashboard, employee, professor, student, web
from app.core.config import BASE_DIR, get_settings, setup_logging
from app.core.exceptions import ComplaintNotFound, ComplaintValidationError
from app.database.database import init_db

logger = logging.getLogger("complaint_agent")

CSP = ("default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
       "img-src 'self' data: blob:; font-src 'self' https://cdn.jsdelivr.net; frame-ancestors 'none'; form-action 'self'")


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    init_db()
    s = get_settings()
    if not s.admin_password:
        logger.warning("ADMIN_PASSWORD is empty: admin pages and API are UNPROTECTED (development only).")
    logger.info("Started. AI provider=%s", s.ai_provider)
    yield


app = FastAPI(
    title="AI Student Complaint Management System",
    description="University Role-Based Complaint Management System with AI-assisted triage.",
    version="2.0.0", lifespan=lifespan,
)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "app" / "static")), name="static")

app.include_router(auth.router)
app.include_router(student.router)
app.include_router(employee.router)
app.include_router(professor.router)
app.include_router(admin.router)
app.include_router(web.router)
app.include_router(complaints.router)
app.include_router(dashboard.router)



from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("X-Frame-Options", "DENY")
    if not request.url.path.startswith(("/docs", "/redoc", "/openapi")):
        response.headers.setdefault("Content-Security-Policy", CSP)
    if request.url.path.startswith(("/admin", "/api")):
        response.headers.setdefault("Cache-Control", "no-store")
    return response


def _respond(request: Request, status_code: int, message: str):
    if request.url.path.startswith("/api"):
        return JSONResponse({"detail": message}, status_code=status_code)
    from html import escape
    return HTMLResponse(f"<h1>{status_code}</h1><p>{escape(message)}</p><p><a href='/admin'>Back</a></p>", status_code)


@app.exception_handler(ComplaintNotFound)
async def _not_found(request: Request, exc: ComplaintNotFound):
    return _respond(request, 404, str(exc))


@app.exception_handler(ComplaintValidationError)
async def _invalid(request: Request, exc: ComplaintValidationError):
    return JSONResponse({"detail": exc.errors}, status_code=422)


@app.exception_handler(SQLAlchemyError)
async def _db_error(request: Request, exc: SQLAlchemyError):
    logger.error("Database error: %s", type(exc).__name__)
    return _respond(request, 500, "A database error occurred. Please try again.")
