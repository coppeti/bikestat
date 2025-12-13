"""Activity data models."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class Activity(BaseModel):
    """Cycling activity model."""

    activity_id: str
    activity_name: str
    activity_type: str
    start_time: datetime
    duration: float = Field(description="Duration in seconds")
    distance: float = Field(description="Distance in meters")
    avg_speed: Optional[float] = Field(None, description="Average moving speed in m/s")
    max_speed: Optional[float] = Field(None, description="Max speed in m/s")
    avg_power: Optional[float] = Field(None, description="Average power in watts")
    max_avg_power: Optional[float] = Field(None, description="Max average power in watts")
    max_power: Optional[float] = Field(None, description="Max power in watts")
    avg_hr: Optional[float] = Field(None, description="Average heart rate in bpm")
    max_hr: Optional[float] = Field(None, description="Max heart rate in bpm")
    total_ascent: Optional[float] = Field(None, description="Total elevation gain in meters")
    max_elevation: Optional[float] = Field(None, description="Max elevation in meters")
    avg_cadence: Optional[float] = Field(None, description="Average cadence in rpm")
    max_cadence: Optional[float] = Field(None, description="Max cadence in rpm")
    calories: Optional[int] = Field(None, description="Total calories burned")

    class Config:
        json_schema_extra = {
            "example": {
                "activity_id": "123456789",
                "activity_name": "Morning Ride",
                "activity_type": "cycling",
                "start_time": "2025-01-15T08:30:00",
                "duration": 3600.0,
                "distance": 25000.0,
                "avg_speed": 6.94,
                "max_speed": 12.5,
            }
        }


class ActivitySummary(BaseModel):
    """Summary statistics for multiple activities."""

    total_activities: int
    total_duration: float = Field(description="Total duration in seconds")
    total_distance: float = Field(description="Total distance in meters")
    avg_speed: Optional[float] = Field(None, description="Average speed across all activities")
    max_speed: Optional[float] = Field(None, description="Maximum speed across all activities")
    avg_power: Optional[float] = Field(None, description="Average power across all activities")
    max_avg_power: Optional[float] = Field(None, description="Max average power")
    max_power: Optional[float] = Field(None, description="Maximum power across all activities")
    avg_hr: Optional[float] = Field(None, description="Average heart rate")
    max_hr: Optional[float] = Field(None, description="Maximum heart rate")
    total_ascent: Optional[float] = Field(None, description="Total elevation gain")
    max_elevation: Optional[float] = Field(None, description="Maximum elevation")
    avg_cadence: Optional[float] = Field(None, description="Average cadence")
    max_cadence: Optional[float] = Field(None, description="Maximum cadence")
    total_calories: Optional[int] = Field(None, description="Total calories burned")


class DateRange(BaseModel):
    """Date range for filtering activities."""

    start_date: datetime
    end_date: datetime


class FilterOptions(BaseModel):
    """Filter options for activities."""

    activity_types: list[str] = Field(
        default_factory=lambda: [
            "cyclocross",
            "mountain_biking_enduro",
            "gravel_cycling",
            "mountain_biking",
            "cycling"
        ]
    )
    columns: list[str] = Field(
        default_factory=lambda: [
            "activity_name",
            "activity_type",
            "start_time",
            "duration",
            "distance",
            "avg_speed",
            "max_speed",
            "avg_power",
            "max_power",
            "avg_hr",
            "max_hr",
            "total_ascent",
            "calories"
        ]
    )
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
