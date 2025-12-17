"""Export endpoints for PDF and CSV."""

import logging
import io
from datetime import datetime
from typing import Optional
import pandas as pd
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
    columns: Optional[str] = Query(None, description="Comma-separated column keys to export"),
):
    """
    Export activities to CSV.

    Args:
        activity_types: Comma-separated list of activity types to filter
        columns: Comma-separated list of column keys to export

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

    # Map frontend column keys to DataFrame column names
    # Order matches frontend availableColumns array
    column_mapping = {
        "start_time": ("start_time", "Date"),
        "activity_name": ("activity_name", "Activity Name"),
        "activity_type": ("activity_type", "Type"),
        "duration": ("duration_formatted", "Duration"),
        "distance": ("distance_km", "Distance (km)"),
        "avg_speed": ("avg_speed_kmh", "Avg Speed (km/h)"),
        "max_speed": ("max_speed_kmh", "Max Speed (km/h)"),
        "avg_power": ("avg_power", "Avg Power (W)"),
        "max_power": ("max_power", "Max Power (W)"),
        "avg_hr": ("avg_hr", "Avg HR (bpm)"),
        "max_hr": ("max_hr", "Max HR (bpm)"),
        "total_ascent": ("total_ascent", "Elevation Gain (m)"),
        "max_elevation": ("max_elevation", "Max Elevation (m)"),
        "avg_cadence": ("avg_cadence", "Avg Cadence (rpm)"),
        "max_cadence": ("max_cadence", "Max Cadence (rpm)"),
        "calories": ("calories", "Calories"),
    }

    # Parse selected columns
    selected_keys = None
    if columns:
        selected_keys = [c.strip() for c in columns.split(",")]

    # Build export columns list maintaining order from column_mapping
    export_columns_list = []

    # If columns are selected, reorder them to match column_mapping order
    if selected_keys:
        selected_set = set(selected_keys)
        ordered_keys = [key for key in column_mapping.keys() if key in selected_set]
    else:
        ordered_keys = list(column_mapping.keys())

    for key in ordered_keys:
        if key not in column_mapping:
            continue
        df_col, label = column_mapping[key]
        # Skip if column doesn't exist in DataFrame
        if df_col not in df.columns:
            continue
        # Skip if column has no data (all null or 0)
        if df[df_col].notna().sum() == 0 or (df[df_col].fillna(0) == 0).all():
            continue
        export_columns_list.append((df_col, label))

    if not export_columns_list:
        raise HTTPException(status_code=404, detail="No data to export with selected columns")

    # Select and rename columns in order
    df_cols = [col for col, _ in export_columns_list]
    labels = {col: label for col, label in export_columns_list}
    df_export = df[df_cols].rename(columns=labels)

    # Add totals row
    totals = {}
    first_column = True

    for df_col, label in export_columns_list:
        if first_column:
            totals[label] = "TOTAL"
            first_column = False
        elif label in ["Activity Name", "Type", "Date"]:
            totals[label] = ""
        elif label == "Duration":
            # Sum durations
            total_seconds = df["duration"].sum() if "duration" in df.columns else 0
            hours = int(total_seconds // 3600)
            minutes = int((total_seconds % 3600) // 60)
            totals[label] = f"{hours:02d}:{minutes:02d}"
        elif label == "Distance (km)":
            # Sum distance with 2 decimals
            totals[label] = round(df_export[label].sum(), 2) if df_export[label].notna().any() else ""
        elif "Max" in label:
            # Max for max metrics
            value = df_export[label].max() if df_export[label].notna().any() else ""
            if value and "Speed" in label:
                totals[label] = round(value, 1)
            elif value:
                totals[label] = int(round(value, 0))
            else:
                totals[label] = ""
        elif "Avg" in label:
            # Average for avg metrics
            value = df_export[label].mean() if df_export[label].notna().any() else ""
            if value and "Speed" in label:
                totals[label] = round(value, 1)
            elif value:
                totals[label] = int(round(value, 0))
            else:
                totals[label] = ""
        elif label in ["Elevation Gain (m)", "Calories"]:
            # Sum for elevation and calories (integers)
            value = df_export[label].sum() if df_export[label].notna().any() else ""
            totals[label] = int(round(value, 0)) if value else ""
        else:
            totals[label] = ""

    # Append totals row with columns in same order as df_export
    totals_df = pd.DataFrame([totals], columns=df_export.columns)
    df_export = pd.concat([df_export, totals_df], ignore_index=True)

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
    columns: Optional[str] = Query(None, description="Comma-separated column keys to export"),
):
    """
    Export activities to PDF.

    Args:
        activity_types: Comma-separated list of activity types to filter
        columns: Comma-separated list of column keys to export

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

    # Convert to DataFrame with proper formatting
    df = DataProcessor.activities_to_dataframe(filtered)

    # Map frontend column keys to DataFrame column names
    # Order matches frontend availableColumns array
    column_mapping = {
        "start_time": ("start_time", "Date"),
        "activity_name": ("activity_name", "Activity"),
        "activity_type": ("activity_type", "Type"),
        "duration": ("duration_formatted", "Duration"),
        "distance": ("distance_km", "Distance\n(km)"),
        "avg_speed": ("avg_speed_kmh", "Avg Speed\n(km/h)"),
        "max_speed": ("max_speed_kmh", "Max Speed\n(km/h)"),
        "avg_power": ("avg_power", "Avg Power\n(W)"),
        "max_power": ("max_power", "Max Power\n(W)"),
        "avg_hr": ("avg_hr", "Avg HR\n(bpm)"),
        "max_hr": ("max_hr", "Max HR\n(bpm)"),
        "total_ascent": ("total_ascent", "Elevation\n(m)"),
        "max_elevation": ("max_elevation", "Max Elev\n(m)"),
        "avg_cadence": ("avg_cadence", "Avg Cadence\n(rpm)"),
        "max_cadence": ("max_cadence", "Max Cadence\n(rpm)"),
        "calories": ("calories", "Calories"),
    }

    # Parse selected columns
    selected_keys = None
    if columns:
        selected_keys = [c.strip() for c in columns.split(",")]

    # Build export columns list maintaining order from column_mapping
    export_columns_list = []

    # If columns are selected, reorder them to match column_mapping order
    if selected_keys:
        selected_set = set(selected_keys)
        ordered_keys = [key for key in column_mapping.keys() if key in selected_set]
    else:
        ordered_keys = list(column_mapping.keys())

    for key in ordered_keys:
        if key not in column_mapping:
            continue
        df_col, label = column_mapping[key]
        # Skip if column doesn't exist in DataFrame
        if df_col not in df.columns:
            continue
        # Skip if column has no data (all null or 0)
        if df[df_col].notna().sum() == 0 or (df[df_col].fillna(0) == 0).all():
            continue
        export_columns_list.append((df_col, label))

    if not export_columns_list:
        raise HTTPException(status_code=404, detail="No data to export with selected columns")

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
    date_text = f"Period: {start_date.strftime('%d/%m/%Y')} to {end_date.strftime('%d/%m/%Y')}"
    elements.append(Paragraph(date_text, normal_style))
    elements.append(Spacer(1, 0.2 * inch))

    # Summary section
    summary_text = f"""
    <b>Summary Statistics</b><br/>
    Total Activities: {summary.total_activities}<br/>
    Total Distance: {summary.total_distance / 1000:.2f} km<br/>
    Total Duration: {int(summary.total_duration // 3600):02d}:{int((summary.total_duration % 3600) // 60):02d}<br/>
    Average Speed: {summary.avg_speed * 3.6 if summary.avg_speed else 0:.1f} km/h<br/>
    Total Calories: {summary.total_calories or 0}
    """
    elements.append(Paragraph(summary_text, normal_style))
    elements.append(Spacer(1, 0.3 * inch))

    # Activities table - build header row from selected columns
    header_row = [label for _, label in export_columns_list]
    table_data = [header_row]

    # Add data rows from DataFrame
    for idx in range(len(df)):
        row = []
        for df_col, _ in export_columns_list:
            value = df[df_col].iloc[idx]
            # Handle NaN/None values
            if pd.isna(value):
                row.append("-")
            # Truncate long text fields
            elif df_col in ["activity_name", "activity_type"]:
                row.append(str(value)[:20] if len(str(value)) > 20 else str(value))
            else:
                row.append(str(value))
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
