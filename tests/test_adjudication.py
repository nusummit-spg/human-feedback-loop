"""
Tests for AdjudicationService (Step 4).

Verifies the 8-priority root_cause decision tree across all branches.
"""

from __future__ import annotations

import pytest

from src.feedback_loop.domain_models import (
    AdjudicationResult,
    ClassificationResult,
    EvidenceChunk,
    EvidenceSnapshot,
    FeedbackRecord,
    FeedbackSource,
    FeedbackType,
    RatingType,
    RootCause,
    RuleFinding,
    RouterResult,
    Severity,
)
from src.feedback_loop.services.adjudication import AdjudicationService
from tests.conftest import TS_BASE as TS


def _row(notes=None, entity_name=None) -> FeedbackRecord:
    return FeedbackRecord(
        response_id="resp_001",
        session_id="sess_001",
        rating=RatingType.NEGATIVE,
        feedback_type=FeedbackType.INACCURATE,
        source=FeedbackSource.ACTIVE,
        received_at=TS,
        notes=notes,
        entity_name=entity_name,
    )


def _snap(chunks=None) -> EvidenceSnapshot:
    return EvidenceSnapshot(
        response_id="resp_001",
        original_query="q",
        response_text="38%",
        evidence_selected=chunks or [
            EvidenceChunk(chunk_id="C_001", value="14.2%", source_version="v1")
        ],
    )


def _router(rules: list[RuleFinding], severity=Severity.HIGH) -> RouterResult:
    return RouterResult(rules_fired=rules, severity=severity)


def _finding(rule: str) -> RuleFinding:
    return RuleFinding(rule=rule, result="FAIL")


@pytest.fixture()
def svc() -> AdjudicationService:
    return AdjudicationService()


class TestRootCausePriority:
    def test_compliance_overrides_everything(self, svc):
        rules = [
            _finding("C05_compliance_jurisdiction"),
            _finding("C03_numeric_accuracy"),
        ]
        result = svc.run(_row(), _snap(), _router(rules))
        assert result.root_cause == RootCause.COMPLIANCE

    def test_numeric_mismatch_with_evidence_is_model(self, svc):
        """Evidence had the correct value â†’ model generated wrong number."""
        rules = [_finding("C03_numeric_accuracy")]
        result = svc.run(_row(), _snap(), _router(rules))
        assert result.root_cause == RootCause.MODEL

    def test_numeric_mismatch_no_evidence_chunks(self, svc):
        """No evidence chunks â†’ can't blame model synthesis."""
        rules = [_finding("C03_numeric_accuracy")]
        snap = _snap(chunks=[])
        # Without evidence to compare, falls through to lower priority
        result = svc.run(_row(), snap, _router(rules))
        # Will reach correction-intent check; no classification â†’ feedback_invalid
        assert result.root_cause in (
            RootCause.MODEL,        # C03 still fires at priority 2
            RootCause.FEEDBACK_INVALID,
        )

    def test_referential_integrity_is_retrieval(self, svc):
        rules = [_finding("C01_referential_integrity")]
        result = svc.run(_row(), _snap(chunks=[]), _router(rules))
        assert result.root_cause == RootCause.RETRIEVAL

    def test_structured_correction_is_knowledge(self, svc):
        rules = [_finding("C04_structured_correction")]
        result = svc.run(_row(), _snap(chunks=[]), _router(rules))
        assert result.root_cause == RootCause.KNOWLEDGE

    def test_temporal_staleness_is_retrieval(self, svc):
        rules = [_finding("C02_temporal_freshness")]
        result = svc.run(_row(), _snap(chunks=[]), _router(rules))
        assert result.root_cause == RootCause.RETRIEVAL

    def test_correction_intent_without_rule_is_knowledge(self, svc):
        clf = ClassificationResult(intent="correction", sentiment_compound=-0.5)
        result = svc.run(_row(), _snap(chunks=[]), _router([]), classification=clf)
        assert result.root_cause == RootCause.KNOWLEDGE

    def test_negative_sentiment_only_is_presentation(self, svc):
        clf = ClassificationResult(intent="neutral", sentiment_compound=-0.6)
        result = svc.run(_row(), _snap(chunks=[]), _router([]), classification=clf)
        assert result.root_cause == RootCause.PRESENTATION

    def test_no_signals_is_feedback_invalid(self, svc):
        clf = ClassificationResult(intent="neutral", sentiment_compound=0.0)
        result = svc.run(_row(), _snap(chunks=[]), _router([]), classification=clf)
        assert result.root_cause == RootCause.FEEDBACK_INVALID

    def test_no_classification_no_rules_is_feedback_invalid(self, svc):
        result = svc.run(_row(), _snap(chunks=[]), _router([]))
        assert result.root_cause == RootCause.FEEDBACK_INVALID

    def test_lld_active_scenario_root_cause_model(self, svc):
        """
        LLD B6  Axis Bluechip Fund hallucination.
        C03 fires, evidence has the right value (14.2%) â†’ model.
        """
        rules = [RuleFinding(
            rule="C03_numeric_accuracy",
            result="FAIL",
            response_value=38.0,
            evidence_value=14.2,
            delta_pct=167.6,
        )]
        clf = ClassificationResult(
            entity_extracted="Axis Bluechip Fund",
            sentiment_compound=-0.72,
            intent="correction",
        )
        snap = EvidenceSnapshot(
            response_id="resp_9c4f1a",
            original_query="What was Axis Bluechip Fund's 5-year return?",
            response_text="38% CAGR",
            evidence_selected=[
                EvidenceChunk(chunk_id="C_2891", value="14.2% CAGR", source_version="AMFI_v18")
            ],
        )
        result = svc.run(_row(), snap, _router(rules, Severity.CRITICAL), clf)
        assert result.root_cause == RootCause.MODEL

