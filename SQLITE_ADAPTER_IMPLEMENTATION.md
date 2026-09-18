# SQLite Database Adapter Implementation

## Overview

Added `SQLiteDatabaseAdapter` to `src/feedback_loop/adapters/db.py` — a concrete implementation of the `AbstractDatabaseAdapter` interface that maps between Pydantic domain models and SQLAlchemy ORM models.

**Status:** ✅ Complete and ready for production use

---

## Files Modified

### 1. `src/feedback_loop/adapters/db.py`

**Added:**
- **`SQLiteDatabaseAdapter` class** (production-grade SQLite implementation)
  - Maintains SQLAlchemy engine + sessionmaker
  - Translates between Pydantic models (pipeline domain) and ORM models (DB persistence)
  - Thread-safe session handling

**Public Methods:**
```python
def __init__(self, db_url: str = "sqlite:///feedback.db")
def fetch_feedback_record(self, feedback_id: str) -> FeedbackRecord
def update_ingestion_status(self, feedback_id: str, status: IngestionStatus) -> None
def fetch_pending_feedback_records(self, older_than_minutes: int = 5) -> list[FeedbackRecord]
def write_unified_record(self, record: UnifiedEvaluationRecord) -> None
def find_open_cluster(self, response_id: str, entity_name: Optional[str]) -> Optional[UnifiedEvaluationRecord]
def unified_record_exists(self, response_id: str) -> bool
```

**Private Helper Methods:**
- `_orm_to_feedback_record()` — Converts ORM ResponseFeedback → Pydantic FeedbackRecord
- `_orm_to_unified_record()` — Converts ORM UnifiedEvaluationRecord → Pydantic UnifiedEvaluationRecord

**Key Features:**
- Enum value translation (string ↔ Pydantic enums)
- DateTime ISO string ↔ Python datetime conversions
- Duplicate detection on write (raises ValueError if response_id exists)
- Single-write guarantee enforced at adapter level
- Structured logging via `structlog`

---

### 2. `src/feedback_loop/models.py`

**Added Enums (top-level):**
```python
class IngestionStatus(str, enum.Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"

class FeedbackSource(str, enum.Enum):
    ACTIVE = "active"
    PASSIVE = "passive"
```

**Updated Existing Enum:**
- `RatingType` — Added `UNRATED = "unrated"` value

**Enhanced ResponseFeedback ORM Model:**
```python
# Feedback-loop ingestion tracking
ingestion_status: Mapped[str] = mapped_column(
    String(20), nullable=False, default=IngestionStatus.PENDING.value, index=True
)
ingestion_source: Mapped[str | None] = mapped_column(String(20), nullable=True)
rating_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
feedback_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
corrections: Mapped[dict | None] = mapped_column(JSON, nullable=True)
```

---

## Data Mapping Reference

### FeedbackRecord (Pydantic) ← → ResponseFeedback (ORM)

| Pydantic Field | ORM Column | Notes |
|---|---|---|
| `feedback_id` | `feedback_id` | PK |
| `source` | `ingestion_source` (inferred as active/passive) | Mapped from domain_models enum |
| `received_at` | `created_at` | ISO string ↔ datetime |
| `ingestion_status` | `ingestion_status` | PENDING \| SENT \| FAILED |
| `response_id` | `response_id` | FK to query_evidence |
| `session_id` | `session_id` | Session context |
| `rating` | `rating_type` | POSITIVE \| NEGATIVE \| UNRATED |
| `feedback_type` | `feedback_type` | COMPLAINT \| CORRECTION \| other |
| `user_id` | `actor_id` | User who submitted feedback |
| `entity_name` | (None) | Populated by Step 1 NER, not DB |
| `entity_type` | (None) | Populated by Step 1 NER, not DB |
| `notes` | `feedback_text` (capped at 2000 chars) | User's feedback text |
| `corrections` | `corrections` | Structured user-supplied corrections (JSON) |
| `timestamp` | `client_timestamp` | Client-side timestamp if provided |

### UnifiedEvaluationRecord (Pydantic) ← → UnifiedEvaluationRecord (ORM)

| Pydantic Field | ORM Column | Notes |
|---|---|---|
| `session_id` | `session_id` | Part of composite PK |
| `response_id` | `response_id` | Part of composite PK |
| `entry_route` | `entry_route` | HITL \| AUTOMATIC \| DISSATISFACTION_CONVERTED |
| `feedback_ref` | `feedback_ref` | FK to response_feedback (optional) |
| `evidence_snapshot_ref` | `evidence_snapshot_ref` | FK to query_evidence |
| `root_cause` | `root_cause` | KNOWLEDGE \| RETRIEVAL \| MODEL \| ... |
| `severity` | `severity` | CRITICAL \| HIGH \| MEDIUM \| LOW |
| `lifecycle_status` | `lifecycle_status` | OPEN \| DIAGNOSING \| RESOLVED \| MONITORING |
| `dissatisfaction_evidence` | `dissatisfaction_evidence_json` | Evidence triggering dissatisfaction route |
| `deterministic_results` | `deterministic_results` | Evaluation Layer output (set later) |
| `gnn_plausibility_score` | `gnn_plausibility_score` | Evaluation Layer output (set later) |
| `semantic_results` | `semantic_results` | Evaluation Layer output (set later) |
| `llm_evaluation` | `llm_evaluation` | Evaluation Layer output (set later) |
| `adjudication_verdict` | `adjudication_verdict` | Evaluation Layer output (set later) |
| `adjudication_confidence` | `adjudication_confidence` | Evaluation Layer output (set later) |

---

## Usage

### Initialization

```python
from feedback_loop.adapters.db import SQLiteDatabaseAdapter

# Local development
db = SQLiteDatabaseAdapter(db_url="sqlite:///feedback.db")

# Production (Postgres)
db = SQLiteDatabaseAdapter(db_url="postgresql://user:pass@host/db")

# In-memory (testing)
from feedback_loop.adapters.db import InMemoryDatabaseAdapter
db = InMemoryDatabaseAdapter()
```

### With IngestService

```python
from feedback_loop.ingest import IngestService
from feedback_loop.config import FeedbackLoopConfig

config = FeedbackLoopConfig()
ingest = IngestService(config, db, evidence_adapter)

# Process a single feedback record
success = ingest.on_ingest(
    feedback_id="fb_9c4f1a",
    session_id="sess_2201",
    response_id="resp_9c4f1a",
    source="active",
)

# Retry sweep (background task)
summary = ingest.retry_sweep(older_than_minutes=5)
print(f"Attempted: {summary['attempted']}, Succeeded: {summary['succeeded']}")
```

### With start_feedback_loop API

```python
from feedback_loop import start_feedback_loop, FeedbackLoopConfig

config = FeedbackLoopConfig()
db = SQLiteDatabaseAdapter("sqlite:///feedback.db")

# Called from AMC webhook
success = start_feedback_loop(
    feedback_id=...,
    session_id=...,
    response_id=...,
    source="active",
    config=config,
    db=db,
    evidence_adapter=evidence_adapter,
)
```

---

## Database Schema Assumptions

The adapter assumes the following tables exist in the database:

### response_feedback
- PK: `feedback_id` (String 64)
- Indexed columns: `response_id`, `session_id`, `created_at`, `ingestion_status`
- Fields used by adapter:
  - `feedback_id`, `response_id`, `session_id`
  - `actor_id`, `actor_role`
  - `feedback_text`, `client_timestamp`
  - `created_at`, `ingestion_status`, `ingestion_source`
  - `rating_type`, `feedback_type`, `corrections`

### unified_evaluation_records
- PK: Composite `(session_id, response_id)`
- Indexed columns: `response_id`, `entry_route`, `root_cause`, `lifecycle_status`, `created_at`
- Fields used by adapter:
  - All fields (reads + writes)
  - Auto-populated: `created_at`, `created_by` (= "feedback_loop_module")

### query_evidence
- PK: `response_id` (String 64)
- Referenced by FK from `unified_evaluation_records.evidence_snapshot_ref`

---

## Error Handling

### fetch_feedback_record
- **Raises:** `KeyError` if `feedback_id` not found
- **Caller responsibility:** (IngestService) catches and propagates as fatal

### update_ingestion_status
- **Raises:** `KeyError` if `feedback_id` not found
- **Caller responsibility:** (IngestService) catches and logs

### write_unified_record
- **Raises:** `ValueError` if `response_id` already exists
- **Guarantee:** Single-write per response (duplicates rejected)
- **Caller responsibility:** (IngestService.on_ingest) catches

### fetch_pending_feedback_records
- **Returns:** Empty list if no pending records found
- **Time threshold:** Configurable (default 5 minutes)

---

## Testing Strategy

### Unit Tests
Use `InMemoryDatabaseAdapter` for fast, isolated tests:
```python
from tests.conftest import response_feedback_axis_bluechip

db = InMemoryDatabaseAdapter()
db.seed_feedback(response_feedback_axis_bluechip())

record = db.fetch_feedback_record(record.feedback_id)
assert record.response_id == "resp_..."
```

### Integration Tests
Use `SQLiteDatabaseAdapter` with `:memory:` database:
```python
from feedback_loop.adapters.db import SQLiteDatabaseAdapter
from feedback_loop.models import Base
from sqlalchemy import create_engine

engine = create_engine("sqlite:///:memory:")
Base.metadata.create_all(engine)

db = SQLiteDatabaseAdapter("sqlite:///:memory:")
# ... run full tests ...
```

### Production Tests
Use local SQLite file for manual testing:
```python
db = SQLiteDatabaseAdapter("sqlite:///test_feedback.db")
```

---

## Known Limitations & Future Work

1. **No async support** — Uses synchronous SQLAlchemy sessions
   - Add `AsyncSession` support for high-concurrency deployments

2. **No automatic retry logic** — Adapter is stateless
   - `IngestService.retry_sweep()` handles retries at service layer

3. **No soft-delete** — `write_unified_record` raises on duplicate
   - Future: Support "upsert" mode for idempotency

4. **No custom query builder** — Uses SQLAlchemy ORM only
   - All queries are simple equality filters; complex queries will be slow

5. **Enum conversion** — Manual mapping in helper methods
   - Fragile if enums change; consider SQLAlchemy TypeDecorator in future

---

## Imports Required

### New Dependencies
```python
import json
import structlog
from sqlalchemy import and_, create_engine, select
from sqlalchemy.orm import Session, sessionmaker
```

### Existing Dependencies
```python
from feedback_loop.domain_models import (...)
from feedback_loop.models import ResponseFeedback, UnifiedEvaluationRecord
```

---

## Summary

The `SQLiteDatabaseAdapter` provides a production-ready bridge between the Pydantic domain models used by the feedback-loop pipeline and the SQLAlchemy ORM models that define the database schema. It enforces single-write guarantees, handles enum conversions, and supports both SQLite and PostgreSQL backends through the standard SQLAlchemy connection string interface.

All adapter methods match the `AbstractDatabaseAdapter` contract exactly and include comprehensive error handling and logging.
