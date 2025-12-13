"""Activities endpoints."""

import logging
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, Request, Query
from backend.services import SessionManager, DataProcessor
from backend.models.activity import Activity, ActivitySummary

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/activities", tags=["activities"])


def get_session_data(request: Request):
    """Helper to get and validate session."""
    session_manager: SessionManager = request.app.state.session_manager
    session_id = request.cookies.get("session_id")

    if not session_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=401, detail="Session expired")

    return session


@router.post("/fetch")
async def fetch_activities(
    request: Request,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    """
    Fetch activities from Garmin Connect.

    Args:
        start_date: Start date (ISO format)
        end_date: End date (ISO format)

    Returns:
        List of activities and summary
    """
    session = get_session_data(request)
    garmin_service = session.get("garmin_service")

    if not garmin_service:
        raise HTTPException(status_code=500, detail="Garmin service not initialized")

    # Parse dates or use defaults
    if start_date:
        try:
            start = datetime.fromisoformat(start_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid start_date format")
    else:
        start = session.get("start_date")

    if end_date:
        try:
            end = datetime.fromisoformat(end_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid end_date format")
    else:
        end = session.get("end_date")

    try:
        # Fetch activities from Garmin
        raw_activities = await garmin_service.get_activities(start, end)

        # Parse activities
        activities = [DataProcessor.parse_activity(raw) for raw in raw_activities]

        # Update session with fetched activities
        session_manager: SessionManager = request.app.state.session_manager
        session_manager.update_session(
            request.cookies.get("session_id"),
            {
                "activities": activities,
                "start_date": start,
                "end_date": end,
            },
        )

        # Calculate summary
        summary = DataProcessor.calculate_summary(activities)

        logger.info(f"Fetched {len(activities)} activities from {start} to {end}")

        return {
            "activities": [a.model_dump() for a in activities],
            "summary": summary.model_dump(),
            "count": len(activities),
        }

    except ValueError as e:
        logger.error(f"Error fetching activities: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error fetching activities: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch activities")


@router.get("/list")
async def list_activities(
    request: Request,
    activity_types: Optional[str] = Query(None, description="Comma-separated activity types"),
):
    """
    Get filtered list of activities from session.

    Args:
        activity_types: Comma-separated list of activity types to filter

    Returns:
        Filtered activities and summary
    """
    session = get_session_data(request)
    activities = session.get("activities", [])

    if not activities:
        return {"activities": [], "summary": None, "count": 0}

    # Parse activity types filter
    types_filter = None
    if activity_types:
        types_filter = [t.strip() for t in activity_types.split(",")]

    # Filter activities
    filtered = DataProcessor.filter_activities(activities, activity_types=types_filter)

    # Calculate summary
    summary = DataProcessor.calculate_summary(filtered)

    return {
        "activities": [a.model_dump() for a in filtered],
        "summary": summary.model_dump(),
        "count": len(filtered),
    }


@router.get("/summary")
async def get_summary(request: Request) -> ActivitySummary:
    """Get summary statistics for all activities in session."""
    session = get_session_data(request)
    activities = session.get("activities", [])

    summary = DataProcessor.calculate_summary(activities)
    return summary


@router.get("/types")
async def get_activity_types(request: Request):
    """Get list of available activity types from current activities."""
    session = get_session_data(request)
    activities = session.get("activities", [])

    if not activities:
        return {"types": []}

    # Get unique activity types
    types = list(set(a.activity_type for a in activities))
    types.sort()

    return {"types": types}
