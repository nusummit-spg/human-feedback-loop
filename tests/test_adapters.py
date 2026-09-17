"""
Tests for InMemoryDatabaseAdapter and InMemoryEvidenceAdapter.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from feedback_loop.adapters.db import InMemoryDatabaseAdapter
from feedback_loop.adapters.evidence import InMemoryEvidenceAdapter
from feedback_loop.domain_models import (
    EvidenceChunk,
    EvidenceSnapshot,
    FeedbackRecord,
    FeedbackSource,
    FeedbackType,
    FollowUpQuery,
    IngestionStatus,
    RatingType,
    UnifiedEvaluationRecord,
)

TS = datetime(2026, 9, 2, 10, 0, 0, tzinfo=timezone.utc)


def _make_feedback(feedback_id: str = "fb_001", received_at=None) -> FeedbackRecord:
    return FeedbackRecord(
        feedback_id=feedback_id,
        response_id="resp_001",
        session_id="sess_001",
        rating=RatingType.NEGATIVE,
        feedback_type=FeedbackType.INACCURATE,
        source=FeedbackSource.ACTIVE,
        received_at=received_at or TS,
    )


def _make_unified(response_id: str = "resp_001") -> UnifiedEvaluationRecord:
    return UnifiedEvaluationRecord(
        session_id="sess_001",
        response_id=response_id,
        entry_route="hitl",
        evidence_snapshot_ref="ev_001",
    )


class TestInMemoryDatabaseAdapter:
    def test_seed_and_fetch(self):
        db = InMemoryDatabaseAdapter()
        fb = _make_feedback()
        db.seed_feedback(fb)
        fetched = db.fetch_feedback_record("fb_001")
        assert fetched.feedback_id == "fb_001"

    def test_fetch_missing_raises(self):
        db = InMemoryDatabaseAdapter()
        with pytest.raises(KeyError):
            db.fetch_feedback_record("nonexistent")

    def test_update_ingestion_status(self):
        db = InMemoryDatabaseAdapter()
        db.seed_feedback(_make_feedback())
        db.update_ingestion_status("fb_001", IngestionStatus.SENT)
        assert db.fetch_feedback_record("fb_001").ingestion_status == "sent"

    def test_update_status_missing_raises(self):
        db = InMemoryDatabaseAdapter()
        with pytest.raises(KeyError):
            db.update_ingestion_status("ghost", IngestionStatus.SENT)

    def test_write_and_exists(self):
        db = InMemoryDatabaseAdapter()
        record = _make_unified()
        assert not db.unified_record_exists("resp_001")
        db.write_unified_record(record)
        assert db.unified_record_exists("resp_001")

    def test_find_open_cluster_returns_existing(self):
        db = InMemoryDatabaseAdapter()
        record = _make_unified()
        db.write_unified_record(record)
        found = db.find_open_cluster("resp_001", None)
        assert found is not None
        assert found.response_id == "resp_001"

    def test_find_open_cluster_returns_none_when_absent(self):
        db = InMemoryDatabaseAdapter()
        assert db.find_open_cluster("resp_999", None) is None

    def test_fetch_pending_returns_old_rows(self):
        db = InMemoryDatabaseAdapter()
        old_ts = datetime.now(timezone.utc) - timedelta(minutes=10)
        fb = _make_feedback(received_at=old_ts)
        db.seed_feedback(fb)
        pending = db.fetch_pending_feedback_records(older_than_minutes=5)
        assert len(pending) == 1

    def test_fetch_pending_excludes_recent_rows(self):
        db = InMemoryDatabaseAdapter()
        recent_ts = datetime.now(timezone.utc) - timedelta(seconds=30)
        fb = _make_feedback(received_at=recent_ts)
        db.seed_feedback(fb)
        pending = db.fetch_pending_feedback_records(older_than_minutes=5)
        assert len(pending) == 0

    def test_fetch_pending_excludes_sent_rows(self):
        db = InMemoryDatabaseAdapter()
        old_ts = datetime.now(timezone.utc) - timedelta(minutes=10)
        fb = _make_feedback(received_at=old_ts)
        db.seed_feedback(fb)
        db.update_ingestion_status("fb_001", IngestionStatus.SENT)
        pending = db.fetch_pending_feedback_records(older_than_minutes=5)
        assert len(pending) == 0

    def test_get_all_unified(self):
        db = InMemoryDatabaseAdapter()
        db.write_unified_record(_make_unified("resp_A"))
        db.write_unified_record(_make_unified("resp_B"))
        all_records = db.get_all_unified()
        assert len(all_records) == 2


class TestInMemoryEvidenceAdapter:
    def test_get_snapshot(self):
        ev = InMemoryEvidenceAdapter()
        snap = EvidenceSnapshot(
            response_id="resp_001",
            original_query="test query",
            response_text="test response",
        )
        ev.seed_snapshot(snap)
        fetched = ev.get_evidence_snapshot("resp_001")
        assert fetched.response_id == "resp_001"

    def test_get_snapshot_missing_raises(self):
        ev = InMemoryEvidenceAdapter()
        with pytest.raises(KeyError):
            ev.get_evidence_snapshot("ghost")

    def test_validate_response_exists(self):
        ev = InMemoryEvidenceAdapter()
        ev.seed_known_response("resp_001")
        assert ev.validate_response_exists("resp_001") is True
        assert ev.validate_response_exists("resp_999") is False

    def test_get_followup_activity_empty_by_default(self):
        ev = InMemoryEvidenceAdapter()
        followups = ev.get_followup_activity("sess_001", "resp_001", window_minutes=3)
        assert followups == []

    def test_get_followup_activity_with_seeded_data(self):
        ev = InMemoryEvidenceAdapter()
        fq = FollowUpQuery(
            query_id="q1",
            text="No, that's wrong",
            created_at=datetime(2026, 9, 2, 10, 16, tzinfo=timezone.utc),
        )
        ev.seed_followups("sess_001", [fq])
        followups = ev.get_followup_activity("sess_001", "resp_001", window_minutes=3)
        assert len(followups) == 1
        assert followups[0].query_id == "q1"

