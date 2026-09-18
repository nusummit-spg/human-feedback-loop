"""
Tests for domain models  field validation, enum coercion, defaults.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from feedback_loop.domain_models import (
    FeedbackRecord,
    FeedbackSource,
    FeedbackType,
    IngestionStatus,
    LifecycleStatus,
    RatingType,
    UnifiedEvaluationRecord,
)

TS = datetime(2026, 9, 2, 10, 0, 0, tzinfo=timezone.utc)


class TestFeedbackRecord:
    def test_active_record_valid(self):
        r = FeedbackRecord(
            feedback_id="fb_001",
            response_id="resp_001",
            session_id="sess_001",
            rating=RatingType.NEGATIVE,
            feedback_type=FeedbackType.HALLUCINATION,
            source=FeedbackSource.ACTIVE,
            received_at=TS,
        )
        assert r.feedback_id == "fb_001"
        assert r.ingestion_status == IngestionStatus.PENDING
        assert r.user_id is None

    def test_passive_record_valid(self):
        r = FeedbackRecord(
            response_id="resp_002",
            session_id="sess_002",
            rating=RatingType.UNRATED,
            feedback_type=FeedbackType.SILENT_ACCEPT,
            source=FeedbackSource.PASSIVE,
            received_at=TS,
        )
        assert r.notes is None
        assert r.corrections is None
        assert r.source == "passive"

    def test_notes_max_length_enforced(self):
        with pytest.raises(ValidationError):
            FeedbackRecord(
                response_id="r",
                session_id="s",
                rating=RatingType.NEGATIVE,
                feedback_type=FeedbackType.INACCURATE,
                source=FeedbackSource.ACTIVE,
                received_at=TS,
                notes="x" * 2001,  # exceeds max_length=2000
            )

    def test_uuid_auto_generated(self):
        r1 = FeedbackRecord(
            response_id="r",
            session_id="s",
            rating=RatingType.POSITIVE,
            feedback_type=FeedbackType.OTHER,
            source=FeedbackSource.ACTIVE,
            received_at=TS,
        )
        r2 = FeedbackRecord(
            response_id="r",
            session_id="s",
            rating=RatingType.POSITIVE,
            feedback_type=FeedbackType.OTHER,
            source=FeedbackSource.ACTIVE,
            received_at=TS,
        )
        assert r1.feedback_id != r2.feedback_id


class TestUnifiedEvaluationRecord:
    def test_defaults(self):
        r = UnifiedEvaluationRecord(
            session_id="s",
            response_id="r",
            entry_route="hitl",
            evidence_snapshot_ref="ev_001",
        )
        assert r.lifecycle_status == LifecycleStatus.OPEN
        assert r.root_cause is None
        assert r.severity is None
        assert r.deterministic_results is None

    def test_full_record(self):
        r = UnifiedEvaluationRecord(
            session_id="s",
            response_id="r",
            entry_route="automatic",
            evidence_snapshot_ref="ev_002",
            root_cause="model",
            severity="critical",
            lifecycle_status=LifecycleStatus.OPEN,
        )
        assert r.root_cause == "model"
        assert r.severity == "critical"

