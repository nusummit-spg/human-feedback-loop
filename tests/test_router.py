"""
Tests for AdaptiveRouterService (Step 3).

Each rule is tested in isolation and in combination.
Severity mapping is validated for every tier.
"""

from __future__ import annotations

import pytest

from feedback_loop.config import FeedbackLoopConfig
from feedback_loop.domain_models import (
    EvidenceChunk,
    EvidenceSnapshot,
    FeedbackRecord,
    FeedbackSource,
    FeedbackType,
    IngestionStatus,
    RatingType,
    Severity,
)
from feedback_loop.services.router import AdaptiveRouterService
from tests.conftest import TS_BASE as TS


def _snap(
    response_text="The fund returned 38%.",
    entity_name="Axis Bluechip Fund",
    chunks=None,
) -> EvidenceSnapshot:
    return EvidenceSnapshot(
        response_id="resp_001",
        original_query="What is the return?",
        response_text=response_text,
        entity_name=entity_name,
        evidence_selected=chunks or [
            EvidenceChunk(chunk_id="C_001", value="14.2%", source_version="v1",
                          content="Axis Bluechip Fund CAGR: 14.2%")
        ],
    )


def _row(notes=None, entity_name="Axis Bluechip Fund", corrections=None) -> FeedbackRecord:
    return FeedbackRecord(
        response_id="resp_001",
        session_id="sess_001",
        rating=RatingType.NEGATIVE,
        feedback_type=FeedbackType.INACCURATE,
        source=FeedbackSource.ACTIVE,
        received_at=TS,
        notes=notes,
        entity_name=entity_name,
        corrections=corrections,
    )


@pytest.fixture()
def svc() -> AdaptiveRouterService:
    return AdaptiveRouterService(FeedbackLoopConfig())


class TestC03NumericAccuracy:
    def test_large_delta_fires_critical(self, svc):
        """38% vs 14.2% â†’ delta ~168% â†’ critical."""
        snap = _snap(response_text="38% CAGR")
        result = svc.run(_row(), snap)
        rules = {f.rule for f in result.rules_fired}
        assert "C03_numeric_accuracy" in rules
        assert result.severity == Severity.CRITICAL

    def test_matching_values_no_rule(self, svc):
        snap = _snap(
            response_text="14.2% CAGR",
            chunks=[EvidenceChunk(chunk_id="C_001", value="14.2%", source_version="v1")]
        )
        result = svc.run(_row(), snap)
        rules = {f.rule for f in result.rules_fired}
        assert "C03_numeric_accuracy" not in rules

    def test_medium_delta_fires_medium(self):
        """
        2.4% vs 1.85% â†’ delta ~30%.
        With default thresholds (highâ‰¥20%, criticalâ‰¥50%) this falls into HIGH.
        Use a custom config that sets high_threshold=35% to verify the MEDIUM
        band is reachable when thresholds are configured appropriately.
        """
        custom_config = FeedbackLoopConfig(
            numeric_high_delta_pct=35.0,   # 29.7% < 35% â†’ medium
            numeric_medium_delta_pct=10.0,
        )
        svc = AdaptiveRouterService(custom_config)
        snap = EvidenceSnapshot(
            response_id="resp_001",
            original_query="What is the expense ratio?",
            response_text="HDFC Flexi Cap expense ratio of 2.4%.",
            entity_name="HDFC Flexi Cap",
            evidence_selected=[
                EvidenceChunk(
                    chunk_id="C_002",
                    value="1.85%",
                    source_version="v1",
                    content="HDFC Flexi Cap Fund expense ratio: 1.85%",
                )
            ],
        )
        result = svc.run(_row(entity_name="HDFC Flexi Cap"), snap)
        rules = {f.rule for f in result.rules_fired}
        assert "C03_numeric_accuracy" in rules
        assert "C01_referential_integrity" not in rules
        assert result.severity == Severity.MEDIUM

    def test_delta_pct_recorded(self, svc):
        snap = _snap(response_text="38% CAGR")
        result = svc.run(_row(), snap)
        numeric = next(f for f in result.rules_fired if f.rule == "C03_numeric_accuracy")
        assert numeric.delta_pct is not None
        assert numeric.delta_pct > 100


class TestC01ReferentialIntegrity:
    def test_entity_absent_fires_rule(self, svc):
        snap = _snap(
            response_text="The scheme performed well.",
            entity_name="Axis Bluechip Fund",
            chunks=[EvidenceChunk(chunk_id="C_x", value="10%", source_version="v1", content="other fund data")]
        )
        result = svc.run(_row(entity_name="Axis Bluechip Fund"), snap)
        rules = {f.rule for f in result.rules_fired}
        assert "C01_referential_integrity" in rules

    def test_entity_in_response_passes(self, svc):
        snap = _snap(response_text="Axis Bluechip Fund returned 14.2%.")
        result = svc.run(_row(entity_name="Axis Bluechip Fund"), snap)
        rules = {f.rule for f in result.rules_fired}
        assert "C01_referential_integrity" not in rules

    def test_no_entity_name_skips_rule(self, svc):
        snap = _snap(entity_name=None)
        result = svc.run(_row(entity_name=None), snap)
        rules = {f.rule for f in result.rules_fired}
        assert "C01_referential_integrity" not in rules


class TestC02TemporalFreshness:
    def test_missing_source_version_fires_warn(self, svc):
        snap = _snap(
            chunks=[EvidenceChunk(chunk_id="C_old", value="14%", source_version=None)]
        )
        result = svc.run(_row(), snap)
        rules = {f.rule for f in result.rules_fired}
        assert "C02_temporal_freshness" in rules

    def test_versioned_chunks_no_warn(self, svc):
        snap = _snap()  # default chunks have source_version="v1"
        result = svc.run(_row(), snap)
        # C02 should not fire (unless C03 fires due to value mismatch, which is fine)
        temporal_rules = [f for f in result.rules_fired if f.rule == "C02_temporal_freshness"]
        assert len(temporal_rules) == 0


class TestC04StructuredCorrection:
    def test_corrections_present_fires_rule(self, svc):
        snap = _snap()
        result = svc.run(
            _row(corrections={"proposed_value": "14.2%", "proposed_entity": "Axis Bluechip Fund"}),
            snap,
        )
        rules = {f.rule for f in result.rules_fired}
        assert "C04_structured_correction" in rules

    def test_no_corrections_skips_rule(self, svc):
        snap = _snap()
        result = svc.run(_row(), snap)
        rules = {f.rule for f in result.rules_fired}
        assert "C04_structured_correction" not in rules


class TestC05Compliance:
    def test_compliance_keyword_in_notes(self, svc):
        snap = _snap(response_text="Fund NAV is 150.")
        result = svc.run(
            _row(notes="This violates SEBI regulations.", entity_name=None),
            snap,
        )
        rules = {f.rule for f in result.rules_fired}
        assert "C05_compliance_jurisdiction" in rules
        assert result.severity == Severity.CRITICAL

    def test_no_compliance_keywords(self, svc):
        snap = _snap()
        result = svc.run(_row(notes="Wrong value"), snap)
        rules = {f.rule for f in result.rules_fired}
        assert "C05_compliance_jurisdiction" not in rules


class TestSeverityMapping:
    def test_no_rules_no_severity(self, svc):
        snap = EvidenceSnapshot(
            response_id="r",
            original_query="q",
            response_text="no numbers",
            entity_name=None,
        )
        result = svc.run(_row(entity_name=None), snap)
        assert result.severity is None

    def test_compliance_always_critical(self, svc):
        snap = _snap(response_text="Fund value 100.")
        result = svc.run(_row(notes="SEBI breach"), snap)
        assert result.severity == Severity.CRITICAL

