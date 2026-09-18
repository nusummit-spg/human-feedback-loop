"""
feedback_trigger.py
===================
SQLAlchemy event hook that automatically fires start_feedback_loop()
whenever a ResponseFeedback row is inserted into the session.

How to wire it
--------------
Call register_feedback_trigger() once at application startup, passing the
same SQLAlchemy Session factory your app uses:

    from feedback_loop.triggers.feedback_trigger import register_feedback_trigger
    from feedback_loop.adapters.sqlite import SQLiteDatabaseAdapter, SQLiteEvidenceAdapter
    from feedback_loop import FeedbackLoopConfig

    DB_URL = "sqlite:///src/database/scripts/compliance_audit.db"

    db_adapter  = SQLiteDatabaseAdapter(db_url=DB_URL)
    ev_adapter  = SQLiteEvidenceAdapter(db_url=DB_URL)
    config      = FeedbackLoopConfig()

    register_feedback_trigger(
        session_factory=SessionLocal,   # your app's sessionmaker instance
        config=config,
        db_adapter=db_adapter,
        ev_adapter=ev_adapter,
    )

After that, any session.add(ResponseFeedback(...)) followed by session.commit()
will automatically kick off the 4-step pipeline and write a
unified_evaluation_records row.

Design notes
------------
- The trigger fires on after_flush (after the INSERT is issued to SQLite but
  before the outer transaction commits) so the feedback row is readable by
  the pipeline within the same connection.
- The pipeline runs synchronously in the same thread. For production workloads
  consider moving to an async task queue (Celery, ARQ) — swap the body of
  _run_pipeline for a task.delay() call.
- Errors inside the pipeline are caught and logged; they do NOT roll back the
  original ResponseFeedback insert. The retry sweep will reprocess failed rows.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import event
from sqlalchemy.orm import Session

from feedback_loop import start_feedback_loop, FeedbackLoopConfig
from feedback_loop.adapters.db import AbstractDatabaseAdapter
from feedback_loop.adapters.evidence import AbstractEvidenceAdapter
from feedback_loop.models import ResponseFeedback

if TYPE_CHECKING:
    from sqlalchemy.orm import sessionmaker

logger = structlog.get_logger(__name__)


def register_feedback_trigger(
    session_factory,           # sqlalchemy.orm.sessionmaker instance
    config: FeedbackLoopConfig,
    db_adapter: AbstractDatabaseAdapter,
    ev_adapter: AbstractEvidenceAdapter,
) -> None:
    """
    Attach an after_flush listener to the given session factory so that
    every new ResponseFeedback insert automatically triggers the pipeline.

    Safe to call multiple times — SQLAlchemy deduplicates identical listeners.
    """

    @event.listens_for(session_factory, "after_flush")
    def _on_flush(session: Session, flush_context) -> None:
        """
        Fires after every flush. Iterates over newly inserted objects and
        invokes the pipeline for each ResponseFeedback row.
        """
        new_feedback_rows = [
            obj for obj in session.new
            if isinstance(obj, ResponseFeedback)
        ]

        for row in new_feedback_rows:
            # Derive source: system-generated rows are passive, human rows are active
            actor_role = (row.actor_role or "").lower()
            source = "passive" if actor_role == "system" else "active"

            log = logger.bind(
                feedback_id=row.feedback_id,
                response_id=row.response_id,
                session_id=row.session_id,
                source=source,
            )
            log.info("feedback_trigger_fired")

            try:
                result = start_feedback_loop(
                    feedback_id=row.feedback_id,
                    session_id=row.session_id,
                    response_id=row.response_id,
                    source=source,
                    config=config,
                    db=db_adapter,
                    evidence_adapter=ev_adapter,
                )
                log.info("feedback_trigger_complete", produced_record=result)

            except KeyError as exc:
                # query_evidence row doesn't exist yet — normal for rows
                # inserted before the corresponding evidence is written.
                # The retry sweep will pick this up.
                log.warning(
                    "feedback_trigger_missing_evidence",
                    error=str(exc),
                )
            except Exception as exc:
                # Pipeline failure must NOT roll back the feedback insert.
                log.error(
                    "feedback_trigger_pipeline_error",
                    error=str(exc),
                    exc_info=True,
                )

    logger.info(
        "feedback_trigger_registered",
        session_factory=str(session_factory),
    )
