"""
Tests for ClassificationService (Step 1).

spaCy and VADER are heavy dependencies that may not be installed in CI.
Tests mock them at the module level so the service's control flow is
fully exercised regardless of whether the NLP models are present.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.feedback_loop.domain_models import (
    FeedbackRecord,
    FeedbackSource,
    FeedbackType,
    IngestionStatus,
    RatingType,
)
from src.feedback_loop.services.classification import ClassificationService

TS = datetime(2026, 9, 2, 10, 0, 0, tzinfo=timezone.utc)


def _make_active(notes: str, entity_name=None, corrections=None) -> FeedbackRecord:
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


def _make_passive() -> FeedbackRecord:
    return FeedbackRecord(
        response_id="resp_002",
        session_id="sess_002",
        rating=RatingType.UNRATED,
        feedback_type=FeedbackType.SILENT_ACCEPT,
        source=FeedbackSource.PASSIVE,
        received_at=TS,
    )


class TestShouldRun:
    def test_skipped_for_passive(self):
        svc = ClassificationService()
        assert svc.should_run(_make_passive()) is False

    def test_skipped_when_corrections_present(self):
        svc = ClassificationService()
        row = _make_active("some notes", corrections={"proposed_value": "14%"})
        assert svc.should_run(row) is False

    def test_skipped_when_no_notes(self):
        svc = ClassificationService()
        row = _make_active("")
        # empty string is falsy
        assert svc.should_run(row) is False

    def test_runs_for_active_with_notes(self):
        svc = ClassificationService()
        row = _make_active("This is wrong, the fund returned 14%.")
        assert svc.should_run(row) is True


class TestRunWithMockedNLP:
    """Full run() path with spaCy and VADER mocked  tests logic, not NLP quality."""

    def _make_svc_with_mocks(self):
        svc = ClassificationService()

        # Mock VADER
        mock_vader = MagicMock()
        mock_vader.polarity_scores.return_value = {
            "compound": -0.72, "pos": 0.0, "neu": 0.4, "neg": 0.6
        }
        svc._vader = mock_vader

        # Mock spaCy entity
        mock_ent = MagicMock()
        mock_ent.text = "Axis Bluechip Fund"
        mock_ent.label_ = "ORG"

        mock_doc = MagicMock()
        mock_doc.ents = [mock_ent]

        mock_nlp = MagicMock()
        mock_nlp.return_value = mock_doc
        svc._nlp = mock_nlp

        return svc

    def test_active_hallucination_scenario(self):
        """Mirrors LLD B3  Axis Bluechip Fund, 14.2% mentioned."""
        svc = self._make_svc_with_mocks()
        row = _make_active(
            notes="This is completely wrong. The fund's 5-year return is around 14%. Please check the factsheet.",
            entity_name="Axis Bluechip Fund",
        )
        result = svc.run(row)

        assert result.sentiment_compound == -0.72
        assert result.intent == "correction"
        assert result.entity_extracted == "Axis Bluechip Fund"
        assert result.value_mentioned == "14%"

    def test_intent_classified_as_complaint(self):
        svc = self._make_svc_with_mocks()
        svc._vader.polarity_scores.return_value = {
            "compound": -0.80, "pos": 0.0, "neu": 0.2, "neg": 0.8
        }
        row = _make_active("This is terrible and completely useless.")
        result = svc.run(row)
        assert result.intent == "complaint"

    def test_intent_classified_as_query(self):
        svc = self._make_svc_with_mocks()
        svc._vader.polarity_scores.return_value = {
            "compound": 0.0, "pos": 0.0, "neu": 1.0, "neg": 0.0
        }
        row = _make_active("What is the correct NAV?")
        result = svc.run(row)
        assert result.intent == "query"

    def test_entity_falls_back_to_row_field_when_no_ner_match(self):
        svc = ClassificationService()
        # Disable NLP entirely
        svc._nlp = False
        svc._vader = False
        row = _make_active("Wrong value", entity_name="HDFC Fund")
        result = svc.run(row)
        assert result.entity_extracted == "HDFC Fund"

    def test_numeric_value_extracted(self):
        svc = self._make_svc_with_mocks()
        row = _make_active(
            "The correct value is 38.5% not 14%.",
            entity_name="Some Fund",
        )
        result = svc.run(row)
        # First numeric match from the notes
        assert result.value_mentioned is not None
        assert "%" in result.value_mentioned

    def test_graceful_degradation_no_nlp(self):
        """Service should not raise when both NLP libs are unavailable."""
        svc = ClassificationService()
        svc._nlp = False
        svc._vader = False
        row = _make_active("Something is wrong here.")
        result = svc.run(row)  # must not raise
        assert result is not None
        assert result.sentiment_compound == 0.0

