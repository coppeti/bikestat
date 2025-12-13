"""Main FastAPI application for BikeStat."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from backend.api import auth_router, activities_router, export_router
from backend.services import SessionManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Paths
BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "backend" / "templates"
STATIC_DIR = BASE_DIR / "backend" / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown events."""
    # Startup
    logger.info("Starting BikeStat application...")
    session_manager = SessionManager(timeout_minutes=60)
    await session_manager.start_cleanup_task()
    app.state.session_manager = session_manager
    logger.info("Session manager initialized")

    yield

    # Shutdown
    logger.info("Shutting down BikeStat application...")


# Create FastAPI app
app = FastAPI(
    title="BikeStat",
    description="SaaS web app for Garmin Connect cycling activities analysis",
    version="0.1.0",
    lifespan=lifespan,
)

# Mount static files
STATIC_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Templates
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Include routers
app.include_router(auth_router)
app.include_router(activities_router)
app.include_router(export_router)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Landing page with login form."""
    # Check if already logged in
    session_id = request.cookies.get("session_id")
    if session_id:
        session_manager: SessionManager = request.app.state.session_manager
        session = session_manager.get_session(session_id)
        if session:
            return RedirectResponse(url="/dashboard", status_code=303)

    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard page."""
    # Check authentication
    session_id = request.cookies.get("session_id")
    if not session_id:
        return RedirectResponse(url="/", status_code=303)

    session_manager: SessionManager = request.app.state.session_manager
    session = session_manager.get_session(session_id)

    if not session:
        response = RedirectResponse(url="/", status_code=303)
        response.delete_cookie("session_id")
        return response

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "email": session.get("email"),
            "start_date": session.get("start_date"),
            "end_date": session.get("end_date"),
        },
    )


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "service": "BikeStat"}


def main():
    """Run the application with uvicorn."""
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )


if __name__ == "__main__":
    main()
