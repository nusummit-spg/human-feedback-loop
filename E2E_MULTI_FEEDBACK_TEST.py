#!/usr/bin/env python
"""
Multi-Feedback End-to-End Test: Test logging with 3 diverse feedback scenarios.

Tests:
  1. NAV Inaccuracy (numeric mismatch) -> MODEL root cause
  2. Outdated Information -> RETRIEVAL root cause
  3. Poor Response Quality -> PRESENTATION root cause

Generates logs in: logs/session_<id>/ with per-step files.
"""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.feedback_loop import start_feedback_loop
from src.feedback_loop.adapters.sqlite.db_adapter import SQLiteDatabaseAdapter
from src.feedback_loop.adapters.sqlite.evidence_adapter import SQLiteEvidenceAdapter
from src.feedback_loop.config import FeedbackLoopConfig
from src.feedback_loop.models import Base, QueryEvidence, ResponseFeedback


def setup_database(db_path: str = "test_feedback_multi.db"):
    """Create SQLite database with schema."""
    print(f"\n📦 Setting up database: {db_path}")

    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    print("✅ Database schema created (fresh)")
    return engine


def create_feedback_scenario(scenario_num: int, scenario_name: str, engine):
    """Create a feedback scenario and return (feedback_id, response_id, session_id)."""
    Session = sessionmaker(bind=engine)
    session = Session()

    print(f"\n📝 Scenario {scenario_num}: {scenario_name}")

    response_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    feedback_id = str(uuid.uuid4())

    scenarios = {
        1: {
            "query": "What is the current NAV of Axis Bluechip Fund?",
            "response": "The current NAV of Axis Bluechip Fund is ₹150.25 as of today.",
            "evidence": "Axis Bluechip Fund NAV: ₹150.25",
            "feedback": "That NAV is outdated. Current NAV is ₹152.50. Please update your data.",
            "category": "inaccuracy",
        },
        2: {
            "query": "What are the latest COVID-19 vaccination guidelines?",
            "response": "As of 2024, vaccination guidelines are: adults 1 booster every 12 months.",
            "evidence": "COVID vaccination guidelines (2023): Annual booster recommended",
            "feedback": "This info is outdated. New 2024 guidelines recommend 2 boosters per year.",
            "category": "outdated",
        },
        3: {
            "query": "Explain quantum computing in simple terms",
            "response": "Quantum computers use qubits. That's it.",
            "evidence": "Quantum computing basics: qubits, superposition, entanglement",
            "feedback": "Response is too vague. Needs better explanation of how it differs from classical computing.",
            "category": "clarity",
        },
    }

    data = scenarios.get(scenario_num, scenarios[1])

    response = QueryEvidence(
        response_id=response_id,
        session_id=session_id,
        query_text=data["query"],
        retrieval_mode="contextgraph",
        assembled_context_json={
            "context_items": [
                {
                    "chunk_id": "c1",
                    "value": data["evidence"],
                    "source_version": "v1.0",
                    "content": "Evidence snapshot",
                },
            ]
        },
        synthesis_output_json={
            "response_text": data["response"],
            "confidence": 0.92,
        },
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    session.add(response)
    session.commit()
    print(f"  ✓ QueryEvidence created: {response_id[:8]}...")

    feedback = ResponseFeedback(
        feedback_id=feedback_id,
        response_id=response_id,
        interaction_id=str(uuid.uuid4()),
        session_id=session_id,
        turn_number=1,
        query_text=data["query"],
        actor_id=f"user_{scenario_num}",
        actor_role="end_user",
        selected_categories=[data["category"]],
        answer_relevance_score=3,
        source_quality_score=2,
        completeness_score=3,
        client_timestamp=datetime.now(timezone.utc).isoformat(),
        created_at=datetime.now(timezone.utc).isoformat(),
        response_text=data["response"],
        feedback_text=data["feedback"],
        rating_type="negative",
        feedback_type="correction",
        ingestion_source="active",
        ingestion_status="pending",
    )
    session.add(feedback)
    session.commit()
    print(f"  ✓ ResponseFeedback created: {feedback_id[:8]}...")

    session.close()
    return feedback_id, response_id, session_id


def run_pipeline(feedback_id: str, session_id: str, response_id: str, scenario_num: int):
    """Run the complete 4-step pipeline."""
    print(f"\n🚀 Running pipeline for Scenario {scenario_num}...")

    db = SQLiteDatabaseAdapter("sqlite:///test_feedback_multi.db")
    evidence = SQLiteEvidenceAdapter("sqlite:///test_feedback_multi.db")
    config = FeedbackLoopConfig()

    print("  [1] Classification (NER + Sentiment + Intent)")
    print("  [2] Enrichment (Evidence + Dissatisfaction Detection)")
    print("  [3] Adaptive Router (Rules C01-C05)")
    print("  [4] Adjudication (8-Priority Root-Cause Chain)")

    print("\n⏳ Processing feedback...")
    success = start_feedback_loop(
        feedback_id=feedback_id,
        session_id=session_id,
        response_id=response_id,
        source="active",
        config=config,
        db=db,
        evidence_adapter=evidence,
    )

    print(f"✅ Pipeline completed: {success}")
    return db


def display_logs():
    """Display generated log files."""
    print("\n" + "="*80)
    print("LOG FILES GENERATED")
    print("="*80)

    logs_dir = Path("logs")
    if not logs_dir.exists():
        print("No logs directory found")
        return

    session_dirs = sorted(logs_dir.glob("session_*"))
    print(f"\nFound {len(session_dirs)} session directories:\n")

    for session_dir in session_dirs[:3]:
        log_files = sorted(session_dir.glob("*.log"))
        print(f"session_{session_dir.name.split('_')[1][:8]}/")
        for log_file in log_files:
            size_kb = log_file.stat().st_size / 1024
            print(f"   {log_file.name} ({size_kb:.1f} KB)")
        print()


def main():
    """Run full multi-feedback test."""
    print("\n" + "="*80)
    print("MULTI-FEEDBACK END-TO-END TEST WITH LOGGING")
    print("="*80)

    engine = setup_database("test_feedback_multi.db")

    scenarios = [
        (1, "NAV Inaccuracy (Numeric Mismatch)"),
        (2, "Outdated Information"),
        (3, "Poor Response Quality"),
    ]

    results = []

    for scenario_num, scenario_name in scenarios:
        print("\n" + "-"*80)

        feedback_id, response_id, session_id = create_feedback_scenario(
            scenario_num, scenario_name, engine
        )

        db = run_pipeline(feedback_id, session_id, response_id, scenario_num)

        results.append({
            "scenario": scenario_name,
            "session_id": session_id[:8],
            "feedback_id": feedback_id[:8],
        })

    print("\n" + "="*80)
    print("RESULTS SUMMARY")
    print("="*80)
    for result in results:
        print(f"\n{result['scenario']}")
        print(f"  Session: {result['session_id']}...")
        print(f"  Feedback: {result['feedback_id']}...")

    display_logs()

    print("\n" + "="*80)
    print("TEST COMPLETE")
    print("="*80)
    print("\nTo view logs:")
    print("  ls -la logs/session_*/")
    print("  cat logs/session_*/step_*.log | python -m json.tool")
    print()


if __name__ == "__main__":
    main()
