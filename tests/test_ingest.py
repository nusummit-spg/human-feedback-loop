"""
Tests for IngestService  on_ingest() and retry_sweep().
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from feedback_loop.ingest import IngestService
from feedback_loop.domain_models import (
    EvidenceChunk,
    EvidenceSnapshot,
    FeedbackRecord,
    FeedbackSource,
    FeedbackType,
    IngestionStatus,
    RatingType,
)
from feedback_loop.adapters.db import InMemoryDatabaseAdapter
from feedback_loop.adapters.evidence import InMemoryEvidenceAdapter
from feedback_loop.config import FeedbackLoopConfig

TS = datetime(2026, 9, 2, 10, 0, 0, tzinfo=timezone.utc)


def _make_ingest_svc(feedback_records=None, snapshots=None):
    config = FeedbackLoopConfig()
    db = InMemoryDatabaseAdapter()
    ev = InMemoryEvidenceAdapter()

    for fb in (feedback_records or []):
        db.seed_feedback(fb)
    for snap in (snapshots or []):
        ev.seed_snapshot(snap)

    return IngestService(config, db, ev), db, ev


def _feedback(
    feedback_id="fb_001",
    response_id="resp_001",
    session_id="sess_001",
    source=FeedbackSource.ACTIVE,
    received_at=None,
    status=IngestionStatus.PENDING,
) -> FeedbackRecord:
    return FeedbackRecord(
        feedback_id=feedback_id,
        response_id=response_id,
        session_id=session_id,
        rating=RatingType.NEGATIVE,
        feedback_type=FeedbackType.INACCURATE,
        source=source,
        received_at=received_at or TS,
        entity_name="Axis Bluechip Fund",
        notes="The return is wrong. Should be 14%.",
        ingestion_status=status,
    )


def _snapshot(response_id="resp_001") -> EvidenceSnapshot:
    return EvidenceSnapshot(
        response_id=response_id,
        original_query="What is the 5-year return?",
        response_text="38% CAGR",
        entity_name="Axis Bluechip Fund",
        evidence_selected=[
            EvidenceChunk(chunk_id="C_001", value="14.2%", source_version="v1",
                          content="Axis Bluechip Fund CAGR: 14.2%")
        ],
    )


class TestOnIngest:
    def test_active_ingest_writes_unified_record(self):
        fb = _feedback()
        snap = _snapshot()
        svc, db, _ = _make_ingest_svc([fb], [snap])

        result = svc.on_ingest("fb_001", "sess_001", "resp_001", "active")

        assert result is True
        assert db.unified_record_exists("resp_001")
        assert db.fetch_feedback_record("fb_001").ingestion_status == "sent"

    def test_ingest_marks_sent_on_success(self):
        fb = _feedback()
        snap = _snapshot()
        svc, db, _ = _make_ingest_svc([fb], [snap])
        svc.on_ingest("fb_001", "sess_001", "resp_001", "active")
        assert db.fetch_feedback_record("fb_001").ingestion_status == "sent"

    def test_duplicate_ingest_returns_false(self):
        fb = _feedback()
        snap = _snapshot()
        svc, db, _ = _make_ingest_svc([fb], [snap])

        svc.on_ingest("fb_001", "sess_001", "resp_001", "active")

        # Second call with same response_id  should be skipped
        fb2 = _feedback(feedback_id="fb_002")
        db.seed_feedback(fb2)
        result = svc.on_ingest("fb_002", "sess_001", "resp_001", "active")
        assert result is False
        # Should still be marked sent (non-error)
        assert db.fetch_feedback_record("fb_002").ingestion_status == "sent"

    def test_missing_feedback_record_raises(self):
        svc, _, _ = _make_ingest_svc()
        with pytest.raises(KeyError):
            svc.on_ingest("nonexistent", "sess", "resp", "active")

    def test_missing_evidence_marks_failed_and_raises(self):
        fb = _feedback()
        svc, db, _ = _make_ingest_svc([fb])  # no snapshot seeded
        with pytest.raises(KeyError):
            svc.on_ingest("fb_001", "sess_001", "resp_001", "active")
        assert db.fetch_feedback_record("fb_001").ingestion_status == "failed"

    def test_passive_ingest_produces_automatic_record(self):
        fb = _feedback(source=FeedbackSource.PASSIVE)
        fb = fb.model_copy(update={"notes": None, "entity_name": None})
        snap = _snapshot()
        svc, db, _ = _make_ingest_svc([fb], [snap])

        result = svc.on_ingest("fb_001", "sess_001", "resp_001", "passive")

        assert result is True
        records = db.get_all_unified()
        assert len(records) == 1
        assert records[0].entry_route == "automatic"


class TestRetrySweep:
    def test_sweep_processes_pending_old_rows(self):
        old_ts = datetime.now(timezone.utc) - timedelta(minutes=10)
        fb = _feedback(received_at=old_ts, status=IngestionStatus.PENDING)
        snap = _snapshot()
        svc, db, _ = _make_ingest_svc([fb], [snap])

        summary = svc.retry_sweep(older_than_minutes=5)

        assert summary["attempted"] == 1
        assert summary["succeeded"] == 1
        assert summary["failed"] == 0

    def test_sweep_skips_recent_rows(self):
        recent_ts = datetime.now(timezone.utc) - timedelta(seconds=10)
        fb = _feedback(received_at=recent_ts)
        snap = _snapshot()
        svc, db, _ = _make_ingest_svc([fb], [snap])

        summary = svc.retry_sweep(older_than_minutes=5)
        assert summary["attempted"] == 0

    def test_sweep_skips_already_sent(self):
        old_ts = datetime.now(timezone.utc) - timedelta(minutes=10)
        fb = _feedback(received_at=old_ts, status=IngestionStatus.SENT)
        snap = _snapshot()
        svc, db, _ = _make_ingest_svc([fb], [snap])

        summary = svc.retry_sweep(older_than_minutes=5)
        assert summary["attempted"] == 0

    def test_sweep_handles_partial_failure(self):
        old_ts = datetime.now(timezone.utc) - timedelta(minutes=10)
        fb_good = _feedback(feedback_id="fb_good", received_at=old_ts)
        fb_bad = _feedback(
            feedback_id="fb_bad",
            response_id="resp_BAD",
            received_at=old_ts,
        )
        snap_good = _snapshot("resp_001")
        # No snapshot for resp_BAD â†’ will fail

        svc, db, _ = _make_ingest_svc([fb_good, fb_bad], [snap_good])

        summary = svc.retry_sweep(older_than_minutes=5)
        assert summary["attempted"] == 2
        assert summary["succeeded"] == 1
        assert summary["failed"] == 1

    def test_sweep_returns_empty_summary_when_nothing_pending(self):
        svc, _, _ = _make_ingest_svc()
        summary = svc.retry_sweep()
        assert summary == {"attempted": 0, "succeeded": 0, "failed": 0}


class TestPublicApiSurface:
    def test_start_feedback_loop_wrapper(self):
        from feedback_loop import start_feedback_loop, FeedbackLoopConfig

        fb = _feedback()
        snap = _snapshot()
        config = FeedbackLoopConfig()
        db = InMemoryDatabaseAdapter()
        ev = InMemoryEvidenceAdapter()
        db.seed_feedback(fb)
        ev.seed_snapshot(snap)

        result = start_feedback_loop(
            feedback_id="fb_001",
            session_id="sess_001",
            response_id="resp_001",
            source="active",
            config=config,
            db=db,
            evidence_adapter=ev,
        )
        assert result is True
        assert db.unified_record_exists("resp_001")

