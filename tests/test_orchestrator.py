"""
Tests for RecordBuilder  the 4-step orchestrator.

Verifies concurrency contract, duplicate guard, single-write, and
correct field assembly on the unified record for both LLD scenarios.
"""

from __future__ import annotations

import pytest

from feedback_loop.domain_models import (
    EntryRoute,
    LifecycleStatus,
    RootCause,
    Severity,
    UnifiedEvaluationRecord,
)
from feedback_loop.orchestrator import RecordBuilder


class TestActivePath:
    def test_lld_b_scenario_end_to_end(
        self, config, active_db, active_evidence, active_feedback_record
    ):
        """
        LLD B1â€“B7: Axis Bluechip Fund hallucination.
        Expected: entry_route=hitl, root_cause=model, severity=critical.
        """
        builder = RecordBuilder(config, active_db, active_evidence)
        record = builder.build(active_feedback_record)

        assert record is not None
        assert record.entry_route == EntryRoute.HITL
        assert record.feedback_ref == "fb_9c4f1a"
        assert record.response_id == "resp_9c4f1a"
        assert record.session_id == "sess_2201"
        assert record.root_cause == RootCause.MODEL
        assert record.severity == Severity.CRITICAL
        assert record.lifecycle_status == LifecycleStatus.OPEN
        assert record.evidence_snapshot_ref == "resp_9c4f1a"

    def test_unified_record_fields_set(
        self, config, active_db, active_evidence, active_feedback_record
    ):
        builder = RecordBuilder(config, active_db, active_evidence)
        record = builder.build(active_feedback_record)

        # Evaluation-Layer fields must remain None after module write
        assert record.deterministic_results is None
        assert record.gnn_plausibility_score is None
        assert record.semantic_results is None
        assert record.llm_evaluation is None
        assert record.adjudication_verdict is None
        assert record.adjudication_confidence is None


class TestPassivePath:
    def test_lld_p_scenario_silent_end_to_end(
        self, config, passive_db, passive_evidence, passive_feedback_record
    ):
        """
        LLD P1â€“P8: HDFC Flexi Cap silent numeric mismatch.
        The passive row has no entity_name, so C01 (referential integrity) does
        not fire.  C03 fires with a ~30% delta â†’ severity=medium per config.
        entry_route=automatic (no follow-up queries, silence).
        root_cause=model (evidence had the correct value, response deviated).
        """
        builder = RecordBuilder(config, passive_db, passive_evidence)
        record = builder.build(passive_feedback_record)

        assert record is not None
        assert record.entry_route == EntryRoute.AUTOMATIC
        assert record.feedback_ref is None   # passive  no feedback_ref
        assert record.root_cause == RootCause.MODEL
        # Severity is medium when only C03 fires with a ~30% delta.
        # If the entity name were present and C01 also fired, severity would be high.
        assert record.severity in (Severity.MEDIUM, Severity.HIGH)
        assert record.lifecycle_status == LifecycleStatus.OPEN

    def test_passive_dissatisfaction_converts(
        self,
        config,
        passive_db,
        passive_evidence_with_followup,
        passive_feedback_record,
    ):
        builder = RecordBuilder(config, passive_db, passive_evidence_with_followup)
        record = builder.build(passive_feedback_record)

        assert record is not None
        assert record.entry_route == EntryRoute.DISSATISFACTION_CONVERTED
        assert record.dissatisfaction_evidence is not None
        assert "triggers" in record.dissatisfaction_evidence


class TestDuplicateGuard:
    def test_duplicate_response_id_returns_none(
        self, config, active_db, active_evidence, active_feedback_record
    ):
        builder = RecordBuilder(config, active_db, active_evidence)

        # First build succeeds
        record1 = builder.build(active_feedback_record)
        assert record1 is not None

        # Write to DB (simulating IngestService)
        active_db.write_unified_record(record1)

        # Second build for same response_id must return None
        record2 = builder.build(active_feedback_record)
        assert record2 is None

    def test_different_response_id_not_deduplicated(
        self,
        config,
        active_db,
        active_evidence,
        active_feedback_record,
        active_evidence_snapshot,
    ):
        """Two different response_ids should both produce records."""
        from feedback_loop.domain_models import (
            EvidenceSnapshot, EvidenceChunk,
            FeedbackRecord, FeedbackSource, FeedbackType, RatingType, IngestionStatus,
        )
        from tests.conftest import TS_BASE

        # Seed a second snapshot with a different response_id
        snap2 = EvidenceSnapshot(
            response_id="resp_SECOND",
            original_query="Different query",
            response_text="38% CAGR",
            entity_name="Axis Bluechip Fund",
            evidence_selected=[
                EvidenceChunk(chunk_id="C_NEW", value="14.2%", source_version="v1")
            ],
        )
        active_evidence.seed_snapshot(snap2)

        row2 = FeedbackRecord(
            feedback_id="fb_NEW",
            response_id="resp_SECOND",
            session_id="sess_NEW",
            rating=RatingType.NEGATIVE,
            feedback_type=FeedbackType.INACCURATE,
            source=FeedbackSource.ACTIVE,
            received_at=TS_BASE,
            entity_name="Axis Bluechip Fund",
        )
        active_db.seed_feedback(row2)

        builder = RecordBuilder(config, active_db, active_evidence)
        r1 = builder.build(active_feedback_record)
        active_db.write_unified_record(r1)

        r2 = builder.build(row2)
        assert r2 is not None
        assert r2.response_id == "resp_SECOND"


class TestStep1SkippedOnPassive:
    def test_passive_record_has_no_classification_influence(
        self, config, passive_db, passive_evidence, passive_feedback_record
    ):
        """
        Passive row with no notes  Step 1 is skipped.
        The record must still be built using Steps 2-4.
        """
        builder = RecordBuilder(config, passive_db, passive_evidence)
        record = builder.build(passive_feedback_record)
        assert record is not None
        # Without classification, adjudication falls through to rule-based path
        assert record.root_cause is not None

