#!/usr/bin/env python
"""
End-to-End Test: Populate DB → Run 4-Step Pipeline → Verify Output

This script demonstrates the complete feedback-loop flow:
1. Create SQLite database with schema
2. Populate sample data (query_evidence, response_feedback)
3. Call start_feedback_loop() for feedback processing
4. Display unified_evaluation_records output
"""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Import feedback-loop components
from src.feedback_loop import start_feedback_loop
from src.feedback_loop.adapters.db import SQLiteDatabaseAdapter
from src.feedback_loop.adapters.sqlite_evidence_adapter import SQLiteEvidenceAdapter
from src.feedback_loop.config import FeedbackLoopConfig
from src.feedback_loop.domain_models import FeedbackRecord, FeedbackSource, FeedbackType, RatingType
from src.feedback_loop.models import Base, ResponseFeedback, QueryEvidence


def setup_database(db_path: str = "test_feedback.db"):
    """Create SQLite database with schema."""
    print(f"📦 Setting up database: {db_path}")

    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    Base.metadata.create_all(engine)

    print("✅ Database schema created")
    return engine


def populate_test_data(engine):
    """Populate database with sample data."""
    Session = sessionmaker(bind=engine)
    session = Session()

    print("\n📝 Populating test data...")

    # Sample response (QueryEvidence)
    response_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())

    response = QueryEvidence(
        response_id=response_id,
        session_id=session_id,
        query_text="What is the current NAV of Axis Bluechip Fund?",
        retrieval_mode="contextgraph",
        assembled_context_json={
            "context_items": [
                {
                    "chunk_id": "c1",
                    "value": "Axis Bluechip Fund NAV: ₹150.25",
                    "source_version": "v1.2",
                    "content": "Latest fund valuation data",
                },
                {
                    "chunk_id": "c2",
                    "value": "Fund Manager: Anish Singh Thakur",
                    "source_version": "v1.0",
                    "content": "Fund management info",
                },
            ]
        },
        synthesis_output_json={
            "response_text": "The current NAV of Axis Bluechip Fund is ₹150.25 as of today.",
            "entity": "Axis Bluechip Fund",
            "confidence": 0.95,
        },
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    session.add(response)
    session.commit()

    print(f"  ✓ Created QueryEvidence: {response_id}")

    # Sample feedback (ResponseFeedback)
    feedback_id = str(uuid.uuid4())

    feedback = ResponseFeedback(
        feedback_id=feedback_id,
        response_id=response_id,
        interaction_id=str(uuid.uuid4()),
        session_id=session_id,
        turn_number=1,
        query_text="What is the current NAV of Axis Bluechip Fund?",
        actor_id="user_123",
        actor_role="investor",
        selected_categories=["inaccuracy"],
        answer_relevance_score=4,
        source_quality_score=3,
        completeness_score=4,
        client_timestamp=datetime.now(timezone.utc).isoformat(),
        created_at=datetime.now(timezone.utc).isoformat(),
        # Feedback-loop fields
        response_text="The current NAV of Axis Bluechip Fund is ₹150.25 as of today.",
        feedback_text="That NAV is outdated. Current NAV is ₹152.50. Please update your data.",
        rating_type="negative",
        feedback_type="correction",
        ingestion_source="active",
        ingestion_status="pending",
    )
    session.add(feedback)
    session.commit()

    print(f"  ✓ Created ResponseFeedback: {feedback_id}")
    print(f"  ✓ Session ID: {session_id}")

    session.close()

    return feedback_id, response_id, session_id


def run_e2e_test(feedback_id: str, session_id: str, response_id: str):
    """Run the complete 4-step pipeline."""
    print("\n🚀 Running end-to-end pipeline...")

    # Initialize adapters
    db = SQLiteDatabaseAdapter("sqlite:///test_feedback.db")
    evidence = SQLiteEvidenceAdapter("sqlite:///test_feedback.db")
    config = FeedbackLoopConfig()

    print("\n📋 Pipeline Stages:")
    print("  [1] Classification (NER + Sentiment + Intent)")
    print("  [2] Enrichment (Evidence + Dissatisfaction Detection)")
    print("  [3] Adaptive Router (Rules C01-C05)")
    print("  [4] Adjudication (8-Priority Root-Cause Chain)")

    # Call start_feedback_loop
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

    print(f"\n✅ Pipeline completed: {success}")

    return db


def display_results(db: SQLiteDatabaseAdapter):
    """Display unified_evaluation_records output."""
    print("\n" + "="*80)
    print("📊 UNIFIED EVALUATION RECORD OUTPUT")
    print("="*80)

    # Fetch and display all records
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from src.feedback_loop.models import UnifiedEvaluationRecord as UnifiedEvaluationORM

    engine = create_engine("sqlite:///test_feedback.db")
    Session = sessionmaker(bind=engine)
    session = Session()

    records = session.query(UnifiedEvaluationORM).all()

    if not records:
        print("\n❌ No records found!")
        return

    for record in records:
        print(f"""
Session ID:        {record.session_id}
Response ID:       {record.response_id}
Entry Route:       {record.entry_route}
Root Cause:        {record.root_cause}
Severity:          {record.severity}
Lifecycle Status:  {record.lifecycle_status}
Created At:        {record.created_at}

Dissatisfaction Signals: {record.dissatisfaction_evidence_json}
""")

    session.close()


def main():
    """Run full end-to-end test."""
    print("\n" + "="*80)
    print("🧪 FEEDBACK-LOOP END-TO-END TEST")
    print("="*80 + "\n")

    # Step 1: Setup database
    engine = setup_database("test_feedback.db")

    # Step 2: Populate test data
    feedback_id, response_id, session_id = populate_test_data(engine)

    # Step 3: Run pipeline
    db = run_e2e_test(feedback_id, session_id, response_id)

    # Step 4: Display results
    display_results(db)

    print("\n" + "="*80)
    print("✅ TEST COMPLETE")
    print("="*80 + "\n")

    print("📌 Summary:")
    print(f"  • Database: test_feedback.db")
    print(f"  • Feedback ID: {feedback_id}")
    print(f"  • Response ID: {response_id}")
    print(f"  • Session ID: {session_id}")
    print(f"\n  Check the database with:")
    print(f"    sqlite3 test_feedback.db 'SELECT * FROM unified_evaluation_records;'")
    print()


if __name__ == "__main__":
    main()
