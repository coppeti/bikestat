"""Data processing service for activities."""

from datetime import datetime
from typing import Optional
import pandas as pd
from backend.models.activity import Activity, ActivitySummary


class DataProcessor:
    """Process and transform Garmin activity data."""

    @staticmethod
    def parse_activity(raw_activity: dict) -> Activity:
        """
        Parse raw Garmin activity data into Activity model.

        Args:
            raw_activity: Raw activity data from Garmin API

        Returns:
            Activity model instance
        """
        # Extract basic info
        activity_id = str(raw_activity.get("activityId", ""))
        activity_name = raw_activity.get("activityName", "Unnamed Activity")
        activity_type = raw_activity.get("activityType", {}).get("typeKey", "unknown")

        # Parse start time
        start_time_str = raw_activity.get("startTimeLocal", "")
        try:
            start_time = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            start_time = datetime.now()

        # Extract metrics with safe defaults
        duration = raw_activity.get("duration", 0.0)
        distance = raw_activity.get("distance", 0.0)

        # Speed metrics (convert from km/h to m/s if needed)
        avg_speed = raw_activity.get("averageSpeed")
        max_speed = raw_activity.get("maxSpeed")

        # Power metrics
        avg_power = raw_activity.get("avgPower")
        max_avg_power = raw_activity.get("maxAvgPower")
        max_power = raw_activity.get("maxPower")

        # Heart rate metrics
        avg_hr = raw_activity.get("averageHR")
        max_hr = raw_activity.get("maxHR")

        # Elevation metrics
        total_ascent = raw_activity.get("elevationGain")
        max_elevation = raw_activity.get("maxElevation")

        # Cadence metrics
        avg_cadence = raw_activity.get("averageBikingCadenceInRevPerMinute")
        if avg_cadence is None:
            avg_cadence = raw_activity.get("avgBikeCadence")

        max_cadence = raw_activity.get("maxBikingCadenceInRevPerMinute")
        if max_cadence is None:
            max_cadence = raw_activity.get("maxBikeCadence")

        # Calories
        calories = raw_activity.get("calories")

        return Activity(
            activity_id=activity_id,
            activity_name=activity_name,
            activity_type=activity_type,
            start_time=start_time,
            duration=duration,
            distance=distance,
            avg_speed=avg_speed,
            max_speed=max_speed,
            avg_power=avg_power,
            max_avg_power=max_avg_power,
            max_power=max_power,
            avg_hr=avg_hr,
            max_hr=max_hr,
            total_ascent=total_ascent,
            max_elevation=max_elevation,
            avg_cadence=avg_cadence,
            max_cadence=max_cadence,
            calories=calories,
        )

    @staticmethod
    def calculate_summary(activities: list[Activity]) -> ActivitySummary:
        """
        Calculate summary statistics from activities.

        Args:
            activities: List of Activity instances

        Returns:
            ActivitySummary instance
        """
        if not activities:
            return ActivitySummary(
                total_activities=0,
                total_duration=0.0,
                total_distance=0.0,
            )

        # Convert to DataFrame for easier calculations
        data = [activity.model_dump() for activity in activities]
        df = pd.DataFrame(data)

        # Calculate totals
        total_activities = len(activities)
        total_duration = df["duration"].sum()
        total_distance = df["distance"].sum()

        # Calculate averages (only from non-null values)
        def safe_mean(column: str) -> Optional[float]:
            values = df[column].dropna()
            return float(values.mean()) if len(values) > 0 else None

        def safe_max(column: str) -> Optional[float]:
            values = df[column].dropna()
            return float(values.max()) if len(values) > 0 else None

        def safe_sum(column: str) -> Optional[float]:
            values = df[column].dropna()
            return float(values.sum()) if len(values) > 0 else None

        return ActivitySummary(
            total_activities=total_activities,
            total_duration=total_duration,
            total_distance=total_distance,
            avg_speed=safe_mean("avg_speed"),
            max_speed=safe_max("max_speed"),
            avg_power=safe_mean("avg_power"),
            max_avg_power=safe_max("max_avg_power"),
            max_power=safe_max("max_power"),
            avg_hr=safe_mean("avg_hr"),
            max_hr=safe_max("max_hr"),
            total_ascent=safe_sum("total_ascent"),
            max_elevation=safe_max("max_elevation"),
            avg_cadence=safe_mean("avg_cadence"),
            max_cadence=safe_max("max_cadence"),
            total_calories=int(safe_sum("calories") or 0),
        )

    @staticmethod
    def filter_activities(
        activities: list[Activity],
        activity_types: Optional[list[str]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> list[Activity]:
        """
        Filter activities by type and date range.

        Args:
            activities: List of activities to filter
            activity_types: List of activity types to include
            start_date: Start date for filtering
            end_date: End date for filtering

        Returns:
            Filtered list of activities
        """
        filtered = activities

        # Filter by activity type
        if activity_types:
            filtered = [a for a in filtered if a.activity_type in activity_types]

        # Filter by date range
        if start_date:
            filtered = [a for a in filtered if a.start_time >= start_date]
        if end_date:
            filtered = [a for a in filtered if a.start_time <= end_date]

        return filtered

    @staticmethod
    def activities_to_dataframe(activities: list[Activity]) -> pd.DataFrame:
        """
        Convert activities to pandas DataFrame for export.

        Args:
            activities: List of activities

        Returns:
            DataFrame with activity data
        """
        if not activities:
            return pd.DataFrame()

        data = [activity.model_dump() for activity in activities]
        df = pd.DataFrame(data)

        # Format datetime
        df["start_time"] = pd.to_datetime(df["start_time"])

        # Convert duration to readable format (HH:MM:SS)
        df["duration_formatted"] = df["duration"].apply(
            lambda x: f"{int(x // 3600):02d}:{int((x % 3600) // 60):02d}:{int(x % 60):02d}"
        )

        # Convert distance to km
        df["distance_km"] = df["distance"] / 1000

        # Convert speeds to km/h if in m/s
        if "avg_speed" in df.columns:
            df["avg_speed_kmh"] = df["avg_speed"] * 3.6
        if "max_speed" in df.columns:
            df["max_speed_kmh"] = df["max_speed"] * 3.6

        return df
