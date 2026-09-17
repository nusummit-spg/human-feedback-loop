# Session Management Implementation Guide

## Overview

Implemented time-based session windows for feedback evaluation:

- **Active Window:** 5-10 minutes
- **Behavior:** Feedback within window is evaluated together
- **Expiration:** After 10 minutes, automatically create new session
- **Database:** SQLite (with ChatSession ORM model)

---

## Architecture

### **SessionManager** (session_manager.py)

Tracks session state and validates incoming feedback:

```python
class SessionManager:
    def validate_session(feedback) -> (is_valid, new_session_id)
    def is_within_active_window(session_id) -> bool
    def get_active_sessions() -> list[dict]
    def cleanup_expired_sessions(days) -> int
```

### **Database Adapter Methods** (adapters/db.py)

New abstract methods for session tracking:

```python
# Create new session
create_session(session_id, created_at)

# Get session metadata
get_session_state(session_id) -> {session_id, created_at, last_activity_at}

# Update activity timestamp
update_session_activity(session_id, now)

# Get sessions within active window
get_active_sessions(window_minutes) -> list[dict]

# Archive old sessions
archive_expired_sessions(cutoff) -> count
```

Both `InMemoryDatabaseAdapter` and `SQLiteDatabaseAdapter` implement these.

---

## Data Flow

### **Scenario 1: Feedback Within Active Window (First Feedback)**

```
User Session Starts
│
3:00 PM: First feedback arrives
├─ SessionManager.validate_session()
├─ Session doesn't exist → create new session
├─ db.create_session(session_id, 3:00 PM)
├─ Return: (True, None) — process normally
│
└─ Pipeline processes feedback (Steps 1-4)
   └─ Writes UnifiedEvaluationRecord

3:08 PM: Second feedback (same session)
├─ SessionManager.validate_session()
├─ Last activity: 3:00 PM (8 minutes elapsed)
├─ Still within 10-min window
├─ db.update_session_activity(session_id, 3:08 PM)
├─ Return: (True, None) — process normally
│
└─ Pipeline processes feedback
   └─ Writes UnifiedEvaluationRecord (different record, same session context)
```

### **Scenario 2: Feedback After Session Expires**

```
3:00 PM: First feedback
├─ create_session(session_id_v1, 3:00 PM)
│
3:15 PM: No more feedback (silence)
│
3:30 PM: User asks another question (AFTER 15-minute gap)
├─ SessionManager.validate_session()
├─ Last activity: 3:00 PM (30 minutes elapsed)
├─ EXCEEDS 10-min window → session expired
├─ Create NEW session: session_id_v2_rollover_1234567890
├─ db.create_session(session_id_v2_rollover, 3:30 PM)
├─ Return: (False, "session_id_v2_rollover") — use NEW session_id
│
└─ Feedback re-routed to new session
   └─ NEW UnifiedEvaluationRecord with new session_id
```

---

## Integration with IngestService

### **Current Flow (Before SessionManager)**

```
IngestService.on_ingest(feedback_id, session_id, response_id, ...)
│
├─ RecordBuilder.build(row)
├─ Pipeline runs (Steps 1-4)
└─ write_unified_record()
```

### **New Flow (With SessionManager)**

```
IngestService.on_ingest(feedback_id, session_id, response_id, ...)
│
├─ SessionManager.validate_session(feedback_row)
│  │
│  ├─ Check if session active (within 10 min window)
│  │
│  └─ If expired: return new_session_id
│        └─ Update row.session_id = new_session_id
│
├─ RecordBuilder.build(row)  ← Now uses correct session_id
├─ Pipeline runs (Steps 1-4)
└─ write_unified_record()
```

---

## Configuration

### **Window Duration**

Edit in `FeedbackLoopConfig`:

```python
from feedback_loop.config import FeedbackLoopConfig
from feedback_loop.session_manager import SessionManager
from feedback_loop.adapters.db import SQLiteDatabaseAdapter

config = FeedbackLoopConfig()
db = SQLiteDatabaseAdapter("sqlite:///feedback.db")

# 5-10 minute window (default)
manager = SessionManager(db, window_minutes=5, max_window_minutes=10)

# Or custom window
manager = SessionManager(db, window_minutes=3, max_window_minutes=15)
```

### **Database Setup**

Uses existing `ChatSession` table (models.py):

```python
class ChatSession(Base):
    __tablename__ = "sessions"
    
    session_id: String (PK)
    user_id: String (optional)
    created_at: String (indexed)
    updated_at: String (indexed)  ← Updated on each feedback
    ended_at: String (optional, for cleanup)
```

---

## Usage Examples

### **1. Basic Session Validation**

```python
from feedback_loop.session_manager import SessionManager
from feedback_loop.adapters.db import SQLiteDatabaseAdapter
from feedback_loop.domain_models import FeedbackRecord

db = SQLiteDatabaseAdapter("sqlite:///feedback.db")
manager = SessionManager(db, window_minutes=5, max_window_minutes=10)

# Incoming feedback
feedback = FeedbackRecord(
    feedback_id="fb_123",
    session_id="sess_1",
    response_id="resp_1",
    ...
)

# Validate session
is_valid, new_session_id = manager.validate_session(feedback)

if not is_valid:
    # Session expired, use new one
    feedback.session_id = new_session_id
    print(f"Rolled over to new session: {new_session_id}")
```

### **2. Check If Session Is Active**

```python
is_active = manager.is_within_active_window("sess_1")

if is_active:
    print("Session still active, can process")
else:
    print("Session expired, need new one")
```

### **3. Get Active Sessions (Monitoring)**

```python
active = manager.get_active_sessions()

for session in active:
    print(f"Session: {session['session_id']}")
    print(f"  Created: {session['created_at']}")
    print(f"  Last activity: {session['last_activity_at']}")
```

### **4. Archive Old Sessions (Background Cleanup)**

```python
# Archive sessions older than 7 days
count = manager.cleanup_expired_sessions(days=7)
print(f"Archived {count} old sessions")
```

---

## With IngestService Integration

```python
from feedback_loop.ingest import IngestService
from feedback_loop.session_manager import SessionManager
from feedback_loop.config import FeedbackLoopConfig
from feedback_loop.adapters.db import SQLiteDatabaseAdapter
from feedback_loop.adapters.sqlite_evidence_adapter import SQLiteEvidenceAdapter

config = FeedbackLoopConfig()
db = SQLiteDatabaseAdapter("sqlite:///feedback.db")
evidence = SQLiteEvidenceAdapter("sqlite:///amc.db")
session_mgr = SessionManager(db, window_minutes=5, max_window_minutes=10)

ingest = IngestService(config, db, evidence, session_manager=session_mgr)

# Process feedback (session validation happens automatically)
success = ingest.on_ingest(
    feedback_id="fb_123",
    session_id="sess_1",
    response_id="resp_1",
    source="active"
)
```

---

## Database Schema

### **sessions (ChatSession ORM)**

```sql
CREATE TABLE sessions (
    session_id VARCHAR(64) PRIMARY KEY,
    user_id VARCHAR(36) NULLABLE,
    
    created_at VARCHAR(40) NOT NULL,    -- When session started
    updated_at VARCHAR(40) NOT NULL,    -- Last feedback in session
    ended_at VARCHAR(40) NULLABLE,      -- When session closed (archive)
    
    audit_id VARCHAR(64) FOREIGN KEY,
    
    INDEX idx_session_created (created_at),
    INDEX idx_session_updated (updated_at)
);
```

**Query for active sessions:**

```sql
-- Get sessions with activity in last 10 minutes
SELECT * FROM sessions
WHERE updated_at >= datetime('now', '-10 minutes')
ORDER BY updated_at DESC;
```

---

## Workflow Example

### **Timeline: User Session (2 queries over 15 minutes)**

```
3:00 PM: "What's NAV of Axis Bluechip?"
├─ session_id_v1 created
├─ Feedback evaluated
└─ UnifiedEvaluationRecord written

3:08 PM: "Is that current?"
├─ Last activity: 3:00 PM (8 min ago)
├─ Within 10-min window ✓
├─ Same session_id_v1
└─ UnifiedEvaluationRecord written (same session context)

3:15 PM: (15 min gap - user browsing elsewhere)

3:20 PM: "What about HDFC Flexi Cap?"
├─ Last activity: 3:08 PM (12 min ago)
├─ EXCEEDS 10-min window ✗
├─ Rollover to session_id_v1_rollover_timestamp
├─ NEW session begins
└─ UnifiedEvaluationRecord written (different session)
```

**Why this matters:**
- First two queries evaluated together (same context)
- Third query in fresh context (enough time has passed)
- System knows when user switched contexts automatically

---

## Monitoring & Metrics

### **Active Sessions Dashboard**

```python
def get_session_stats(manager):
    active = manager.get_active_sessions()
    return {
        "active_session_count": len(active),
        "oldest_active": min(s["created_at"] for s in active),
        "newest_active": max(s["last_activity_at"] for s in active),
    }
```

### **Logs**

```
[session_manager] session_created session_id=sess_1 feedback_id=fb_123
[session_manager] session_active session_id=sess_1 elapsed_minutes=8.5
[session_manager] session_expired_rollover old_session_id=sess_1 new_session_id=sess_1_rollover_1234567890 elapsed_minutes=12.3 feedback_id=fb_456
```

---

## Testing

```python
from feedback_loop.adapters.db import InMemoryDatabaseAdapter
from feedback_loop.session_manager import SessionManager
from feedback_loop.domain_models import FeedbackRecord
from datetime import datetime, timezone, timedelta

db = InMemoryDatabaseAdapter()
manager = SessionManager(db, window_minutes=5, max_window_minutes=10)

# Test 1: First feedback creates session
feedback1 = FeedbackRecord(
    feedback_id="fb_1",
    session_id="sess_1",
    response_id="resp_1",
    ...
)
is_valid, new_id = manager.validate_session(feedback1)
assert is_valid == True and new_id is None

# Test 2: Feedback within window
feedback2 = FeedbackRecord(
    feedback_id="fb_2",
    session_id="sess_1",
    response_id="resp_2",
    ...
)
is_valid, new_id = manager.validate_session(feedback2)
assert is_valid == True

# Test 3: Simulate timeout by manually advancing time in tests
# (Use freezegun for datetime mocking)
```

---

## Future Enhancements

1. **Session Closure** — Explicit end_at when user navigates away
2. **Multi-turn Detection** — Automatic detection of follow-up questions
3. **Session Analytics** — Track avg feedback per session, context switches
4. **Adaptive Windows** — Adjust 5-10 min based on user behavior patterns
5. **Session Replay** — Reconstruct full conversation from session_id

---

## Summary

✅ **Automatic session management with 5-10 minute active windows**
✅ **Feedback grouped by context (same session vs. new session)**
✅ **SQLite backend with ChatSession tracking**
✅ **Background cleanup for old sessions**
✅ **Transparent to pipeline (validates before processing)**

The system now knows when a user has changed context and automatically starts a new evaluation session.
