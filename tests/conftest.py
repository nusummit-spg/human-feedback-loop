"""
Shared fixtures for the Human Feedback Loop test suite.

All fixtures use in-memory adapters  no real DB or network calls.
The two design scenarios (Active/Hallucination, Passive/Silent) are
built here and reused across unit and integration tests.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

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
)

# â”€â”€ Fixed timestamps â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
TS_BASE = datetime(2026, 9, 2, 10, 14, 2, tzinfo=timezone.utc)
TS_FOLLOWUP = datetime(2026, 9, 2, 10, 16, 30, tzinfo=timezone.utc)


# â”€â”€ Config â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@pytest.fixture()
def config() -> FeedbackLoopConfig:
    return FeedbackLoopConfig()


# â”€â”€ Active scenario (LLD Section 2  Hallucination) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@pytest.fixture()
def active_feedback_record() -> FeedbackRecord:
    """Mirrors B1 in the LLD active scenario."""
    return FeedbackRecord(
        feedback_id="fb_9c4f1a",
        response_id="resp_9c4f1a",
        session_id="sess_2201",
        user_id="u_88213",
        rating=RatingType.NEGATIVE,
        feedback_type=FeedbackType.HALLUCINATION,
        entity_name="Axis Bluechip Fund",
        entity_type="FUND",
        notes="This is completely wrong. The fund's 5-year return is around 14%. Please check the factsheet.",
        corrections=None,
        source=FeedbackSource.ACTIVE,
        received_at=TS_BASE,
        ingestion_status=IngestionStatus.PENDING,
    )


@pytest.fixture()
def active_evidence_snapshot() -> EvidenceSnapshot:
    """Mirrors B4 in the LLD active scenario."""
    return EvidenceSnapshot(
        response_id="resp_9c4f1a",
        original_query="What was Axis Bluechip Fund's 5-year return?",
        response_text="Axis Bluechip Fund delivered a 38% CAGR over 5 years.",
        entity_name="Axis Bluechip Fund",
        evidence_selected=[
            EvidenceChunk(
                chunk_id="C_2891",
                value="14.2% CAGR",
                source_version="AMFI_v18",
                content="Axis Bluechip Fund 5-year CAGR: 14.2%",
            )
        ],
    )


# â”€â”€ Passive scenario (LLD Section 3  Silent numeric mismatch) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@pytest.fixture()
def passive_feedback_record() -> FeedbackRecord:
    """Mirrors P2 in the LLD passive scenario."""
    return FeedbackRecord(
        feedback_id="fb_hdfc_02",
        response_id="resp_7g1x3p",
        session_id="sess_3110",
        user_id="u_51120",
        rating=RatingType.UNRATED,
        feedback_type=FeedbackType.SILENT_ACCEPT,
        entity_name=None,
        entity_type=None,
        notes=None,
        corrections=None,
        source=FeedbackSource.PASSIVE,
        received_at=TS_BASE,
        ingestion_status=IngestionStatus.PENDING,
    )


@pytest.fixture()
def passive_evidence_snapshot() -> EvidenceSnapshot:
    """Mirrors P5 in the LLD passive scenario."""
    return EvidenceSnapshot(
        response_id="resp_7g1x3p",
        original_query="What is the expense ratio of HDFC Flexi Cap Fund?",
        response_text="HDFC Flexi Cap Fund has an expense ratio of 2.4%.",
        entity_name="HDFC Flexi Cap Fund",
        evidence_selected=[
            EvidenceChunk(
                chunk_id="C_5502",
                value="1.85%",
                source_version="AMFI_v18",
                content="HDFC Flexi Cap Fund expense ratio: 1.85%",
            )
        ],
    )


# â”€â”€ Adapters â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@pytest.fixture()
def active_db(active_feedback_record) -> InMemoryDatabaseAdapter:
    db = InMemoryDatabaseAdapter()
    db.seed_feedback(active_feedback_record)
    return db


@pytest.fixture()
def passive_db(passive_feedback_record) -> InMemoryDatabaseAdapter:
    db = InMemoryDatabaseAdapter()
    db.seed_feedback(passive_feedback_record)
    return db


@pytest.fixture()
def active_evidence(active_evidence_snapshot) -> InMemoryEvidenceAdapter:
    ev = InMemoryEvidenceAdapter()
    ev.seed_snapshot(active_evidence_snapshot)
    return ev


@pytest.fixture()
def passive_evidence(passive_evidence_snapshot) -> InMemoryEvidenceAdapter:
    ev = InMemoryEvidenceAdapter()
    ev.seed_snapshot(passive_evidence_snapshot)
    # No follow-up queries  user left silently
    return ev


@pytest.fixture()
def passive_evidence_with_followup(passive_evidence_snapshot) -> InMemoryEvidenceAdapter:
    """Same snapshot but with a follow-up that triggers dissatisfaction detection."""
    ev = InMemoryEvidenceAdapter()
    ev.seed_snapshot(passive_evidence_snapshot)
    ev.seed_followups(
        session_id="sess_3110",
        queries=[
            FollowUpQuery(
                query_id="q_001",
                text="No, that's wrong  what is the actual expense ratio of HDFC Flexi Cap Fund?",
                created_at=TS_FOLLOWUP,
            )
        ],
    )
    return ev

