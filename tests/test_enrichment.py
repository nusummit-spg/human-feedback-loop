"""
Tests for EvidenceEnrichmentService (Step 2).

Covers: evidence fetch, deduplication, entry_route derivation,
and all three dissatisfaction signal combinations.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from feedback_loop.adapters.db import InMemoryDatabaseAdapter
from feedback_loop.adapters.evidence import InMemoryEvidenceAdapter
from feedback_loop.config import FeedbackLoopConfig
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
from feedback_loop.services.enrichment import (
    EvidenceEnrichmentService,
    _cosine_similarity,
    _matches_correction_pattern,
)

TS = datetime(2026, 9, 2, 10, 0, 0, tzinfo=timezone.utc)
TS_FOLLOWUP = datetime(2026, 9, 2, 10, 3, 0, tzinfo=timezone.utc)


def _snap(response_id="resp_001", entity_name=None) -> EvidenceSnapshot:
    return EvidenceSnapshot(
        response_id=response_id,
        original_query="What is the 5-year CAGR of Axis Bluechip Fund?",
        response_text="Axis Bluechip Fund delivered 38% CAGR.",
        entity_name=entity_name or "Axis Bluechip Fund",
        evidence_selected=[
            EvidenceChunk(chunk_id="C_001", value="14.2% CAGR", source_version="v1")
        ],
    )


def _active_row(response_id="resp_001") -> FeedbackRecord:
    return FeedbackRecord(
        response_id=response_id,
        session_id="sess_001",
        rating=RatingType.NEGATIVE,
        feedback_type=FeedbackType.INACCURATE,
        source=FeedbackSource.ACTIVE,
        received_at=TS,
        entity_name="Axis Bluechip Fund",
    )


def _passive_row(response_id="resp_002", session_id="sess_002") -> FeedbackRecord:
    return FeedbackRecord(
        response_id=response_id,
        session_id=session_id,
        rating=RatingType.UNRATED,
        feedback_type=FeedbackType.SILENT_ACCEPT,
        source=FeedbackSource.PASSIVE,
        received_at=TS,
    )


def _make_svc(snap: EvidenceSnapshot, followups=None, existing_record=None):
    config = FeedbackLoopConfig()
    ev = InMemoryEvidenceAdapter()
    ev.seed_snapshot(snap)
    if followups:
        ev.seed_followups(snap.response_id.replace("resp_", "sess_") or "sess_001", followups)

    db = InMemoryDatabaseAdapter()
    if existing_record:
        db.write_unified_record(existing_record)

    return EvidenceEnrichmentService(config, ev, db), ev, db


class TestCosineSimiliarity:
    def test_identical_strings(self):
        assert _cosine_similarity("hello world", "hello world") == pytest.approx(1.0)

    def test_completely_different(self):
        assert _cosine_similarity("apple", "banana") == pytest.approx(0.0)

    def test_partial_overlap(self):
        sim = _cosine_similarity(
            "What is the 5-year return of Axis Bluechip Fund",
            "What is the 5-year CAGR of Axis Bluechip Fund",
        )
        assert sim > 0.75

    def test_empty_string(self):
        assert _cosine_similarity("", "hello") == pytest.approx(0.0)


class TestCorrectionPattern:
    def test_matches_no_thats_wrong(self):
        config = FeedbackLoopConfig()
        assert _matches_correction_pattern("No, that's wrong", config.correction_patterns)

    def test_matches_actually_its(self):
        config = FeedbackLoopConfig()
        assert _matches_correction_pattern("Actually it's 14%", config.correction_patterns)

    def test_matches_should_be(self):
        config = FeedbackLoopConfig()
        assert _matches_correction_pattern("It should be 14.2%", config.correction_patterns)

    def test_no_match_neutral_query(self):
        config = FeedbackLoopConfig()
        assert not _matches_correction_pattern("What was the fund performance?", config.correction_patterns)


class TestEntryRouteDerivation:
    def test_active_always_hitl(self):
        snap = _snap()
        svc, _, _ = _make_svc(snap)
        result = svc.run(_active_row())
        assert result.entry_route == "hitl"
        assert not result.is_duplicate

    def test_passive_silence_is_automatic(self):
        snap = _snap(response_id="resp_002")
        config = FeedbackLoopConfig()
        ev = InMemoryEvidenceAdapter()
        ev.seed_snapshot(snap)
        db = InMemoryDatabaseAdapter()
        svc = EvidenceEnrichmentService(config, ev, db)
        result = svc.run(_passive_row(response_id="resp_002"))
        assert result.entry_route == "automatic"
        assert result.dissatisfaction_signal is None

    def test_passive_with_strong_followup_converts(
        self, passive_evidence_with_followup, passive_db, config
    ):
        """Two signals (correction_language + same_entity) should convert."""
        from feedback_loop.services.enrichment import EvidenceEnrichmentService
        svc = EvidenceEnrichmentService(config, passive_evidence_with_followup, passive_db)
        from tests.conftest import passive_feedback_record as _pf
        row = FeedbackRecord(
            feedback_id="fb_hdfc_02",
            response_id="resp_7g1x3p",
            session_id="sess_3110",
            rating=RatingType.UNRATED,
            feedback_type=FeedbackType.SILENT_ACCEPT,
            source=FeedbackSource.PASSIVE,
            received_at=TS,
        )
        result = svc.run(row)
        assert result.entry_route == "dissatisfaction_converted"
        assert result.dissatisfaction_signal is not None
        assert len(result.dissatisfaction_signal.triggers) >= 2


class TestDeduplication:
    def test_duplicate_short_circuits(self):
        snap = _snap()
        existing = UnifiedEvaluationRecord(
            session_id="sess_001",
            response_id="resp_001",
            entry_route="hitl",
            evidence_snapshot_ref="ev_001",
        )
        svc, _, _ = _make_svc(snap, existing_record=existing)
        result = svc.run(_active_row())
        assert result.is_duplicate is True

    def test_no_duplicate_when_different_response(self):
        snap = _snap(response_id="resp_NEW")
        existing = UnifiedEvaluationRecord(
            session_id="sess_001",
            response_id="resp_OLD",
            entry_route="hitl",
            evidence_snapshot_ref="ev_001",
        )
        config = FeedbackLoopConfig()
        ev = InMemoryEvidenceAdapter()
        ev.seed_snapshot(snap)
        db = InMemoryDatabaseAdapter()
        db.write_unified_record(existing)
        svc = EvidenceEnrichmentService(config, ev, db)
        result = svc.run(_active_row(response_id="resp_NEW"))
        assert result.is_duplicate is False

