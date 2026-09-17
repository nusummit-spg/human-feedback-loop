# Production Evidence Adapter Implementation

## Overview

The `SQLiteEvidenceAdapter` is the production-grade implementation of `AbstractEvidenceAdapter`. It reads from AMC's database tables to:

1. **Fetch frozen evidence snapshots** — Immutable point-in-time copies of responses
2. **Detect follow-up queries** — User's next questions within a time window
3. **Validate response existence** — Fast checks for response IDs

**Status:** ✅ Production-ready, fully documented

---

## Files Created/Modified

### **New File: `src/feedback_loop/adapters/sqlite_evidence_adapter.py`**

Production adapter with three main methods:
- `get_evidence_snapshot()` — Freeze evidence at ingestion time
- `get_followup_activity()` — Find queries within N minutes
- `validate_response_exists()` — Quick existence check

### **Updated: `src/feedback_loop/models.py`**

Added `QueryLog` table to track user queries in sessions:
```python
class QueryLog(Base):
    __tablename__ = "query_log"
    
    query_id: String (PK)
    session_id: String (indexed)
    response_id: String (indexed, nullable)
    query_text: Text
    created_at: String (indexed)
```

---

## How It Works

### **1. Freezing Evidence Snapshot**

**Scenario:** User submits feedback 2 days after AMC generated a response

```python
# Step 1: Response generated (Day 1, 3pm)
query_evidence row:
├─ response_id = "resp_123"
├─ query_text = "What's NAV of Axis Bluechip?"
├─ synthesis_output_json = {
│   "response_text": "₹150",
│   "entity": "Axis Bluechip",
│   ...
│ }
├─ assembled_context_json = {
│   "context_items": [
│     {"chunk_id": "c1", "value": "Latest NAV: ₹150", "source_version": "v1"},
│     {"chunk_id": "c2", "value": "Fund manager: XYZ", "source_version": "v1"},
│   ]
│ }
└─ created_at = "2026-09-14T15:00:00Z"

# Step 2: Feedback submitted (Day 3, 10am)
response_feedback row:
├─ feedback_id = "fb_456"
├─ response_id = "resp_123"  ← Same response
├─ notes = "That's wrong, NAV is ₹152"
└─ created_at = "2026-09-16T10:00:00Z"

# Step 3: Pipeline ingestion (Day 3, 10:00:01am)
snapshot = adapter.get_evidence_snapshot("resp_123")
│
├─ Reads query_evidence row for resp_123
├─ Freezes: response_text = "₹150" (NOT updated to ₹152)
├─ Freezes: evidence_chunks = [chunk_1, chunk_2]
├─ Returns immutable EvidenceSnapshot
│
└─ Step 3 Router compares against frozen ₹150
   └─ Detects mismatch with feedback (₹152) ✓
```

### **2. Detecting Follow-Up Queries**

**Timeline:**

```
3:00 PM (Day 1)
├─ User asks: "What's NAV of Axis Bluechip?"
├─ AMC responds: "₹150"
├─ INSERT query_evidence (response_id="resp_123", created_at="3:00 PM")
│
3:15 PM
├─ User asks: "Is that the latest?"  ← FOLLOWUP (within 30-min window)
├─ INSERT query_log (session_id="sess_1", query_text="Is that the latest?", created_at="3:15 PM")
│
3:45 PM
├─ User asks: "What about HDFC?" ← STILL IN WINDOW (45 min total)
├─ INSERT query_log (session_id="sess_1", query_text="What about HDFC?", created_at="3:45 PM")
│
4:00 PM
└─ No more queries
```

**Adapter call (when feedback arrives):**

```python
followups = adapter.get_followup_activity(
    session_id="sess_1",
    response_id="resp_123",
    window_minutes=30
)
│
├─ Finds response_123.created_at = 3:00 PM
├─ Looks for queries where: 3:00 PM ≤ created_at ≤ 3:30 PM
├─ Finds: "Is that the latest?" at 3:15 PM
├─ Returns: [FollowUpQuery(text="Is that the latest?", created_at="3:15 PM")]
│
└─ Step 2 Enrichment uses this to detect dissatisfaction
   (re-query + correction language signals)
```

### **3. Response Validation**

**Fast existence check:**

```python
# Before starting pipeline
if not adapter.validate_response_exists(response_id):
    raise KeyError(f"Response {response_id} not found in AMC system")

# Prevents wasted processing on orphaned feedback
```

---

## Data Mapping Reference

### **query_evidence → EvidenceSnapshot**

| Pydantic Field | ORM Column | Extraction |
|---|---|---|
| `response_id` | `response_id` | Direct copy |
| `original_query` | `query_text` | Direct copy |
| `response_text` | `synthesis_output_json["response_text"]` | Nested JSON parse |
| `entity_name` | `synthesis_output_json["entity"]` | Heuristic extraction |
| `evidence_selected[]` | `assembled_context_json["context_items"]` | Array extraction |

### **query_log → FollowUpQuery**

| Pydantic Field | ORM Column |
|---|---|
| `query_id` | `query_id` |
| `text` | `query_text` |
| `created_at` | `created_at` (ISO string → datetime) |

---

## Database Schema

### **query_evidence (AMC table)**

```sql
CREATE TABLE query_evidence (
    response_id VARCHAR(64) PRIMARY KEY,
    session_id VARCHAR(64) NOT NULL,
    query_text TEXT,
    
    -- Response content (frozen at generation time)
    synthesis_output_json JSON NOT NULL,  -- {"response_text": "...", "entity": "..."}
    assembled_context_json JSON NOT NULL, -- {"context_items": [...]}
    
    created_at VARCHAR(40) NOT NULL,
    updated_at VARCHAR(40),
    
    INDEX idx_query_evidence_session (session_id),
    INDEX idx_query_evidence_created (created_at)
);
```

### **query_log (new table)**

```sql
CREATE TABLE query_log (
    query_id VARCHAR(64) PRIMARY KEY,
    session_id VARCHAR(64) NOT NULL,
    response_id VARCHAR(64),  -- Nullable (query may not be about a specific response)
    
    query_text TEXT NOT NULL,
    query_type VARCHAR(60),
    
    created_at VARCHAR(40) NOT NULL,
    
    INDEX idx_query_log_session_time (session_id, created_at),
    INDEX idx_query_log_response_time (response_id, created_at)
);
```

---

## Usage Examples

### **Initialize Adapter**

```python
from feedback_loop.adapters.sqlite_evidence_adapter import SQLiteEvidenceAdapter
from feedback_loop.ingest import IngestService

# Production (SQLite)
evidence = SQLiteEvidenceAdapter(db_url="sqlite:///amc.db")

# Production (PostgreSQL)
evidence = SQLiteEvidenceAdapter(db_url="postgresql://user:pass@host/amc_db")

# With IngestService
ingest = IngestService(config, db_adapter, evidence)
```

### **Fetch Evidence Snapshot**

```python
try:
    snapshot = evidence.get_evidence_snapshot("resp_123")
    print(f"Frozen response: {snapshot.response_text}")
    print(f"Evidence chunks: {len(snapshot.evidence_selected)}")
except KeyError:
    print("Response not found")
```

### **Detect Follow-up Queries**

```python
followups = evidence.get_followup_activity(
    session_id="sess_1",
    response_id="resp_123",
    window_minutes=30
)

if followups:
    print(f"User asked {len(followups)} follow-up question(s)")
    for q in followups:
        print(f"  - {q.text} (at {q.created_at})")
else:
    print("No follow-ups detected (automatic route)")
```

### **Validate Before Processing**

```python
if not evidence.validate_response_exists(response_id):
    # Fail early instead of deep in pipeline
    raise ValueError(f"Response {response_id} not found in AMC")
```

---

## Error Handling

### **Missing Response**

```python
try:
    snapshot = evidence.get_evidence_snapshot("invalid_id")
except KeyError as e:
    logger.error(f"Response not found: {e}")
    # IngestService catches this and marks feedback as FAILED
```

### **Missing JSON Fields**

```python
# If synthesis_output_json is malformed:
snapshot = evidence.get_evidence_snapshot("resp_123")
# ├─ response_text = "" (empty string, not None)
# ├─ entity_name = None (graceful degradation)
# └─ Returns successfully (non-fatal)
```

### **No Follow-ups**

```python
followups = evidence.get_followup_activity(...)
# Returns: []
# Step 2 Enrichment interprets empty list as "automatic" (no dissatisfaction)
```

---

## Performance Considerations

### **Indexed Lookups**

```sql
-- Fast response lookup
SELECT * FROM query_evidence WHERE response_id = ?
  -- Index: PK (response_id)
  -- Expected: <1ms

-- Fast session queries lookup
SELECT * FROM query_log 
  WHERE session_id = ? 
    AND created_at BETWEEN ? AND ?
  -- Composite index: (session_id, created_at)
  -- Expected: <5ms for typical sessions
```

### **Frozen Snapshot**

- ✅ **Fast:** O(1) lookup in query_evidence (PK)
- ✅ **Small:** EvidenceSnapshot is ~5-10KB JSON
- ✅ **Immutable:** No locks needed (read-only)

### **Follow-up Detection**

- ✅ **Indexed:** Composite index on (session_id, created_at)
- ✅ **Time-bounded:** Window_minutes limit prevents table scans
- ✅ **Sorted:** ORDER BY created_at (chronological for dissatisfaction detection)

---

## Testing

### **Unit Tests**

```python
from feedback_loop.adapters.sqlite_evidence_adapter import SQLiteEvidenceAdapter
from tests.conftest import response_evidence_axis_bluechip, followup_queries_axis

# Initialize with :memory: database
adapter = SQLiteEvidenceAdapter("sqlite:///:memory:")

# Seed test data
db.seed_snapshot(response_evidence_axis_bluechip())
db.seed_followups("sess_1", followup_queries_axis())

# Test snapshot
snapshot = adapter.get_evidence_snapshot("resp_axis_bluechip")
assert snapshot.response_text == "₹150"
assert len(snapshot.evidence_selected) > 0

# Test followups
followups = adapter.get_followup_activity("sess_1", "resp_axis_bluechip", 30)
assert len(followups) > 0
assert "Is that the latest" in followups[0].text
```

### **Integration Tests**

```python
# Against real test database
from sqlalchemy import create_engine

engine = create_engine("sqlite:///test_amc.db")
Base.metadata.create_all(engine)

adapter = SQLiteEvidenceAdapter("sqlite:///test_amc.db")
snapshot = adapter.get_evidence_snapshot("real_response_id")
# Validates real data flow
```

---

## Migration Path

### **From In-Memory to Production**

```python
# Before (testing)
from feedback_loop.adapters.evidence import InMemoryEvidenceAdapter
evidence = InMemoryEvidenceAdapter()

# After (production)
from feedback_loop.adapters.sqlite_evidence_adapter import SQLiteEvidenceAdapter
evidence = SQLiteEvidenceAdapter(db_url="postgresql://...")

# Code using evidence adapter: NO CHANGES
# Swappable interface ✓
```

---

## Future Enhancements

1. **ResponseMetadataCache** — Add Redis cache for ~1ms existence checks
2. **Async support** — Switch to AsyncSession for high concurrency
3. **Batch snapshots** — Fetch multiple responses in one DB round-trip
4. **Query deduplication** — Detect repeated questions (same entity/intent)
5. **Evidence versioning** — Track how evidence evolved over time

---

## Summary

The `SQLiteEvidenceAdapter` provides a clean, production-ready interface to AMC's evidence tables. It:

- ✅ Freezes evidence at the moment of feedback ingestion
- ✅ Detects follow-up queries for dissatisfaction signals
- ✅ Validates responses exist before processing
- ✅ Uses indexed queries for performance
- ✅ Handles malformed JSON gracefully
- ✅ Maintains the abstract interface (swappable backends)

All three abstract methods from `AbstractEvidenceAdapter` are fully implemented and ready for production use.
