"""Authentication endpoints."""

import logging
from fastapi import APIRouter, HTTPException, Form, Request, Response
from fastapi.responses import RedirectResponse
from backend.services import SessionManager, GarminService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
async def login(
    request: Request,
    response: Response,
    email: str = Form(...),
    password: str = Form(...),
):
    """
    Login to Garmin Connect.

    Args:
        email: Garmin Connect email
        password: Garmin Connect password

    Returns:
        Redirect to dashboard on success
    """
    session_manager: SessionManager = request.app.state.session_manager

    # Create session
    session_id = session_manager.create_session()

    # Initialize Garmin service
    garmin_service = GarminService()

    try:
        # Attempt login
        await garmin_service.login(email, password)

        # Get default date range (last 7 days)
        start_date, end_date = GarminService.get_default_date_range()

        # Store in session
        session_manager.update_session(
            session_id,
            {
                "garmin_service": garmin_service,
                "email": email,
                "start_date": start_date,
                "end_date": end_date,
                "activities": [],
            },
        )

        logger.info(f"User {email} logged in successfully")

        # Set session cookie
        redirect_response = RedirectResponse(url="/dashboard", status_code=303)
        redirect_response.set_cookie(
            key="session_id",
            value=session_id,
            httponly=True,
            max_age=3600,  # 1 hour
            samesite="lax",
        )
        return redirect_response

    except ValueError as e:
        logger.error(f"Login failed for {email}: {e}")
        # Delete failed session
        session_manager.delete_session(session_id)
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error during login: {e}")
        session_manager.delete_session(session_id)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/logout")
async def logout(request: Request, response: Response):
    """Logout and destroy session."""
    session_manager: SessionManager = request.app.state.session_manager
    session_id = request.cookies.get("session_id")

    if session_id:
        session = session_manager.get_session(session_id)
        if session:
            # Logout from Garmin
            garmin_service = session.get("garmin_service")
            if garmin_service:
                garmin_service.logout()

        # Delete session
        session_manager.delete_session(session_id)

    # Clear cookie and redirect
    redirect_response = RedirectResponse(url="/", status_code=303)
    redirect_response.delete_cookie("session_id")
    return redirect_response


@router.get("/status")
async def status(request: Request):
    """Check authentication status."""
    session_manager: SessionManager = request.app.state.session_manager
    session_id = request.cookies.get("session_id")

    if not session_id:
        return {"authenticated": False}

    session = session_manager.get_session(session_id)
    if not session:
        return {"authenticated": False}

    return {
        "authenticated": True,
        "email": session.get("email"),
        "active_sessions": session_manager.get_active_session_count(),
    }
