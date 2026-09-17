"""
SessionManager — tracks active user sessions with time-based windows.

Sessions remain active for 5-10 minutes. Feedback within the window is processed.
After expiration, a new session begins automatically.

Design:
  - session_id → active/inactive/expired
  - last_activity_at → timestamp of last interaction
  - window_minutes → configurable (default 5-10 min)
  - auto-rollover to new session on timeout
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

import structlog

from feedback_loop.adapters.db import AbstractDatabaseAdapter
from feedback_loop.domain_models import FeedbackRecord

logger = structlog.get_logger(__name__)


class SessionManager:
    """
    Manages user session lifecycles with automatic timeout and rollover.

    A session is ACTIVE for 5-10 minutes after the last feedback.
    After timeout, a new session begins. Prevents mixing feedback from
    different conversation contexts.
    """

    def __init__(
        self,
        db: AbstractDatabaseAdapter,
        window_minutes: int = 5,
        max_window_minutes: int = 10,
    ) -> None:
        """
        Initialize session manager.

        Args:
            db: Database adapter (reads/writes session state)
            window_minutes: Minimum active window (default 5 min)
            max_window_minutes: Maximum before auto-rollover (default 10 min)
        """
        self._db = db
        self._window_minutes = window_minutes
        self._max_window_minutes = max_window_minutes
        self._log = logger.bind(component="session_manager")

    def validate_session(self, feedback: FeedbackRecord) -> tuple[bool, Optional[str]]:
        """
        Check if feedback belongs to active session or should start new one.

        Returns:
            (is_valid, new_session_id_if_needed)
            - (True, None): Feedback is within active window
            - (False, new_id): Session expired, new session created
        """
        session_id = feedback.session_id
        now = datetime.now(timezone.utc)

        # Check if session exists and is active
        session_state = self._db.get_session_state(session_id)

        if session_state is None:
            # First feedback in this session
            self._db.create_session(session_id, now)
            self._log.info(
                "session_created",
                session_id=session_id,
                feedback_id=feedback.feedback_id,
            )
            return True, None

        # Check if session is still active
        last_activity = session_state["last_activity_at"]
        if isinstance(last_activity, str):
            last_activity = datetime.fromisoformat(last_activity)

        elapsed = (now - last_activity).total_seconds() / 60  # Convert to minutes

        if elapsed <= self._max_window_minutes:
            # Session still active
            self._db.update_session_activity(session_id, now)
            self._log.debug(
                "session_active",
                session_id=session_id,
                elapsed_minutes=round(elapsed, 2),
            )
            return True, None

        # Session expired, create new one
        new_session_id = f"{session_id}_rollover_{int(now.timestamp())}"
        self._db.create_session(new_session_id, now)

        self._log.info(
            "session_expired_rollover",
            old_session_id=session_id,
            new_session_id=new_session_id,
            elapsed_minutes=round(elapsed, 2),
            feedback_id=feedback.feedback_id,
        )

        return False, new_session_id

    def is_within_active_window(self, session_id: str) -> bool:
        """
        Fast check: is session within active time window?

        Returns:
            True if feedback within 5-10 min window, False if expired
        """
        session_state = self._db.get_session_state(session_id)

        if session_state is None:
            return False  # Session doesn't exist

        last_activity = session_state["last_activity_at"]
        if isinstance(last_activity, str):
            last_activity = datetime.fromisoformat(last_activity)

        elapsed = (datetime.now(timezone.utc) - last_activity).total_seconds() / 60
        return elapsed <= self._max_window_minutes

    def get_active_sessions(self) -> list[dict]:
        """
        Return all sessions still within active window.

        Useful for monitoring, analytics, cleanup tasks.
        """
        return self._db.get_active_sessions(self._max_window_minutes)

    def cleanup_expired_sessions(self, days: int = 7) -> int:
        """
        Archive sessions older than N days.

        Called by background cleanup task.

        Returns:
            Count of archived sessions
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        count = self._db.archive_expired_sessions(cutoff)

        self._log.info(
            "expired_sessions_archived",
            count=count,
            days=days,
        )
        return count
