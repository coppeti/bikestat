"""Garmin Connect service."""

from datetime import datetime, timedelta
from typing import Optional
import logging
from garminconnect import Garmin
from garth.exc import GarthHTTPError

logger = logging.getLogger(__name__)


class GarminService:
    """Service for interacting with Garmin Connect API."""

    # Mapping of Garmin activity type names to our internal names
    CYCLING_TYPES = {
        "cyclocross": "cyclocross",
        "mountain_biking_enduro": "mountain_biking_enduro",
        "gravel_cycling": "gravel_cycling",
        "mountain_biking": "mountain_biking",
        "cycling": "cycling",
        "road_biking": "cycling",  # Map road_biking to cycling
    }

    def __init__(self):
        """Initialize Garmin service."""
        self.client: Optional[Garmin] = None

    async def login(self, email: str, password: str) -> bool:
        """
        Login to Garmin Connect.

        Args:
            email: User email
            password: User password

        Returns:
            True if login successful, False otherwise

        Raises:
            ValueError: If login fails
        """
        try:
            self.client = Garmin(email, password)
            self.client.login()
            logger.info(f"Successfully logged in to Garmin Connect for {email}")
            return True
        except GarthHTTPError as e:
            logger.error(f"Garmin login failed: {e}")
            raise ValueError(f"Invalid credentials or Garmin Connect error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error during Garmin login: {e}")
            raise ValueError(f"Login failed: {e}")

    async def get_activities(
        self, start_date: datetime, end_date: datetime, activity_types: Optional[list[str]] = None
    ) -> list[dict]:
        """
        Get cycling activities from Garmin Connect.

        Args:
            start_date: Start date for activity retrieval
            end_date: End date for activity retrieval
            activity_types: List of activity types to filter (optional)

        Returns:
            List of activities

        Raises:
            ValueError: If not logged in or API error
        """
        if not self.client:
            raise ValueError("Not logged in to Garmin Connect")

        try:
            # Get activities from Garmin
            activities = self.client.get_activities_by_date(
                start_date.isoformat(), end_date.isoformat()
            )

            # Filter for cycling activities
            cycling_activities = []
            for activity in activities:
                activity_type = activity.get("activityType", {}).get("typeKey", "").lower()

                # Check if it's a cycling activity
                if activity_type in self.CYCLING_TYPES:
                    # If activity_types filter is provided, check if this type is included
                    if activity_types is None or activity_type in activity_types:
                        cycling_activities.append(activity)

            logger.info(
                f"Retrieved {len(cycling_activities)} cycling activities from {start_date} to {end_date}"
            )
            return cycling_activities

        except GarthHTTPError as e:
            logger.error(f"Error retrieving activities: {e}")
            raise ValueError(f"Failed to retrieve activities: {e}")
        except Exception as e:
            logger.error(f"Unexpected error retrieving activities: {e}")
            raise ValueError(f"Error retrieving activities: {e}")

    async def get_activity_details(self, activity_id: str) -> dict:
        """
        Get detailed information for a specific activity.

        Args:
            activity_id: Activity ID

        Returns:
            Activity details

        Raises:
            ValueError: If not logged in or API error
        """
        if not self.client:
            raise ValueError("Not logged in to Garmin Connect")

        try:
            details = self.client.get_activity(activity_id)
            logger.info(f"Retrieved details for activity {activity_id}")
            return details
        except Exception as e:
            logger.error(f"Error retrieving activity details: {e}")
            raise ValueError(f"Failed to retrieve activity details: {e}")

    def logout(self):
        """Logout from Garmin Connect and clear client."""
        if self.client:
            try:
                # garminconnect doesn't have an explicit logout method
                # Just clear the client reference
                self.client = None
                logger.info("Logged out from Garmin Connect")
            except Exception as e:
                logger.error(f"Error during logout: {e}")

    @staticmethod
    def get_default_date_range() -> tuple[datetime, datetime]:
        """
        Get default date range (last 7 days).

        Returns:
            Tuple of (start_date, end_date)
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
        return start_date, end_date
