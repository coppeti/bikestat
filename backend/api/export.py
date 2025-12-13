"""Export endpoints for PDF and CSV."""

import logging
import io
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, Request, Query
from fastapi.responses import StreamingResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from backend.services import SessionManager, DataProcessor

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/export", tags=["export"])


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


@router.get("/csv")
async def export_csv(
    request: Request,
    activity_types: Optional[str] = Query(None, description="Comma-separated activity types"),
):
    """
    Export activities to CSV.

    Args:
        activity_types: Comma-separated list of activity types to filter

    Returns:
        CSV file
    """
    session = get_session_data(request)
    activities = session.get("activities", [])

    if not activities:
        raise HTTPException(status_code=404, detail="No activities found")

    # Parse activity types filter
    types_filter = None
    if activity_types:
        types_filter = [t.strip() for t in activity_types.split(",")]

    # Filter activities
    filtered = DataProcessor.filter_activities(activities, activity_types=types_filter)

    if not filtered:
        raise HTTPException(status_code=404, detail="No activities match the filter")

    # Convert to DataFrame
    df = DataProcessor.activities_to_dataframe(filtered)

    # Select and rename columns for export
    export_columns = {
        "activity_name": "Activity Name",
        "activity_type": "Type",
        "start_time": "Date",
        "duration_formatted": "Duration",
        "distance_km": "Distance (km)",
        "avg_speed_kmh": "Avg Speed (km/h)",
        "max_speed_kmh": "Max Speed (km/h)",
        "avg_power": "Avg Power (W)",
        "max_power": "Max Power (W)",
        "avg_hr": "Avg HR (bpm)",
        "max_hr": "Max HR (bpm)",
        "total_ascent": "Elevation Gain (m)",
        "max_elevation": "Max Elevation (m)",
        "avg_cadence": "Avg Cadence (rpm)",
        "max_cadence": "Max Cadence (rpm)",
        "calories": "Calories",
    }

    # Filter available columns
    available_cols = {k: v for k, v in export_columns.items() if k in df.columns}
    df_export = df[list(available_cols.keys())].rename(columns=available_cols)

    # Generate CSV
    csv_buffer = io.StringIO()
    df_export.to_csv(csv_buffer, index=False)
    csv_buffer.seek(0)

    # Create filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"bikestat_activities_{timestamp}.csv"

    logger.info(f"Exported {len(filtered)} activities to CSV")

    return StreamingResponse(
        iter([csv_buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/pdf")
async def export_pdf(
    request: Request,
    activity_types: Optional[str] = Query(None, description="Comma-separated activity types"),
):
    """
    Export activities to PDF.

    Args:
        activity_types: Comma-separated list of activity types to filter

    Returns:
        PDF file
    """
    session = get_session_data(request)
    activities = session.get("activities", [])

    if not activities:
        raise HTTPException(status_code=404, detail="No activities found")

    # Parse activity types filter
    types_filter = None
    if activity_types:
        types_filter = [t.strip() for t in activity_types.split(",")]

    # Filter activities
    filtered = DataProcessor.filter_activities(activities, activity_types=types_filter)

    if not filtered:
        raise HTTPException(status_code=404, detail="No activities match the filter")

    # Calculate summary
    summary = DataProcessor.calculate_summary(filtered)

    # Create PDF in memory
    pdf_buffer = io.BytesIO()
    doc = SimpleDocTemplate(pdf_buffer, pagesize=landscape(A4))
    elements = []

    # Styles
    styles = getSampleStyleSheet()
    title_style = styles["Title"]
    normal_style = styles["Normal"]

    # Title
    title = Paragraph("BikeStat - Cycling Activities Report", title_style)
    elements.append(title)
    elements.append(Spacer(1, 0.2 * inch))

    # Date range
    start_date = session.get("start_date")
    end_date = session.get("end_date")
    date_text = f"Period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"
    elements.append(Paragraph(date_text, normal_style))
    elements.append(Spacer(1, 0.2 * inch))

    # Summary section
    summary_text = f"""
    <b>Summary Statistics</b><br/>
    Total Activities: {summary.total_activities}<br/>
    Total Distance: {summary.total_distance / 1000:.2f} km<br/>
    Total Duration: {int(summary.total_duration // 3600):02d}:{int((summary.total_duration % 3600) // 60):02d}:{int(summary.total_duration % 60):02d}<br/>
    Average Speed: {summary.avg_speed * 3.6 if summary.avg_speed else 0:.2f} km/h<br/>
    Total Calories: {summary.total_calories or 0}
    """
    elements.append(Paragraph(summary_text, normal_style))
    elements.append(Spacer(1, 0.3 * inch))

    # Activities table
    table_data = [
        [
            "Date",
            "Activity",
            "Type",
            "Duration",
            "Distance\n(km)",
            "Avg Speed\n(km/h)",
            "Calories",
        ]
    ]

    for activity in filtered:
        row = [
            activity.start_time.strftime("%Y-%m-%d %H:%M"),
            activity.activity_name[:20],  # Truncate long names
            activity.activity_type[:15],
            f"{int(activity.duration // 3600):02d}:{int((activity.duration % 3600) // 60):02d}",
            f"{activity.distance / 1000:.2f}",
            f"{activity.avg_speed * 3.6 if activity.avg_speed else 0:.1f}",
            str(activity.calories or "-"),
        ]
        table_data.append(row)

    # Create table
    table = Table(table_data, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 10),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                ("GRID", (0, 0), (-1, -1), 1, colors.black),
                ("FONTSIZE", (0, 1), (-1, -1), 8),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
            ]
        )
    )
    elements.append(table)

    # Build PDF
    doc.build(elements)
    pdf_buffer.seek(0)

    # Create filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"bikestat_activities_{timestamp}.pdf"

    logger.info(f"Exported {len(filtered)} activities to PDF")

    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
