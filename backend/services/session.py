"""Session management service."""

import secrets
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Any
from collections import defaultdict


class SessionManager:
    """Manages user sessions in memory with automatic timeout."""

    def __init__(self, timeout_minutes: int = 60):
        """
        Initialize session manager.

        Args:
            timeout_minutes: Session timeout in minutes (default: 60)
        """
        self.timeout_minutes = timeout_minutes
        self.sessions: dict[str, dict[str, Any]] = {}
        self.last_activity: dict[str, datetime] = {}
        self._cleanup_task: Optional[asyncio.Task] = None

    async def start_cleanup_task(self):
        """Start background task to clean up expired sessions."""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_expired_sessions())

    async def _cleanup_expired_sessions(self):
        """Background task to remove expired sessions."""
        while True:
            try:
                await asyncio.sleep(300)  # Check every 5 minutes
                now = datetime.now()
                expired_sessions = [
                    session_id
                    for session_id, last_active in self.last_activity.items()
                    if now - last_active > timedelta(minutes=self.timeout_minutes)
                ]
                for session_id in expired_sessions:
                    self.delete_session(session_id)
            except Exception as e:
                print(f"Error in cleanup task: {e}")

    def create_session(self) -> str:
        """
        Create a new session.

        Returns:
            Session ID
        """
        session_id = secrets.token_urlsafe(32)
        self.sessions[session_id] = {}
        self.last_activity[session_id] = datetime.now()
        return session_id

    def get_session(self, session_id: str) -> Optional[dict[str, Any]]:
        """
        Get session data.

        Args:
            session_id: Session ID

        Returns:
            Session data or None if session doesn't exist or is expired
        """
        if session_id not in self.sessions:
            return None

        # Check if session is expired
        if self._is_expired(session_id):
            self.delete_session(session_id)
            return None

        # Update last activity
        self.last_activity[session_id] = datetime.now()
        return self.sessions[session_id]

    def update_session(self, session_id: str, data: dict[str, Any]) -> bool:
        """
        Update session data.

        Args:
            session_id: Session ID
            data: Data to update

        Returns:
            True if successful, False if session doesn't exist
        """
        if session_id not in self.sessions:
            return False

        self.sessions[session_id].update(data)
        self.last_activity[session_id] = datetime.now()
        return True

    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session.

        Args:
            session_id: Session ID

        Returns:
            True if successful, False if session doesn't exist
        """
        if session_id in self.sessions:
            del self.sessions[session_id]
            del self.last_activity[session_id]
            return True
        return False

    def _is_expired(self, session_id: str) -> bool:
        """
        Check if a session is expired.

        Args:
            session_id: Session ID

        Returns:
            True if expired, False otherwise
        """
        if session_id not in self.last_activity:
            return True

        last_active = self.last_activity[session_id]
        now = datetime.now()
        return now - last_active > timedelta(minutes=self.timeout_minutes)

    def get_active_session_count(self) -> int:
        """Get the number of active sessions."""
        return len(self.sessions)
