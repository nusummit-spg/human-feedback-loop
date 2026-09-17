# AMC Session Management (5-10 Minute Windows)

## Overview

**Session management belongs in AMC, not feedback-loop.**

AMC should:
- Track user sessions with 5-10 minute active windows
- Auto-create new session after timeout
- Pass session_id to feedback-loop (already validated)

Feedback-loop should:
- Be stateless (trust session_id from AMC)
- Use session_id as context for grouping feedback
- **Not** manage or validate sessions

---

## Architecture

### **AMC Layer** (Session Manager)

```
User Session Tracking
├─ session_id created when user starts interaction
├─ last_activity_at updated on each user action
├─ Check: is last_activity_at within 5-10 min window?
│  ├─ YES → reuse session_id
│  └─ NO → create new session_id (rollover)
├─ Pass session_id to feedback-loop
└─ AMC owns the session lifecycle
```

### **Feedback-Loop Layer** (Stateless)

```
Feedback Processing
├─ Receive: feedback_id, session_id (from AMC)
├─ Trust: session_id is already validated by AMC
├─ Process: 4-step pipeline
│  └─ Session_id flows through to UnifiedEvaluationRecord
└─ Write: session_id, response_id, root_cause, etc.
   (Does not create/manage/validate sessions)
```

---

## Data Flow

### **Scenario: User's 2 Queries Over 15 Minutes**

```
AMC                                  Feedback-Loop
─────────────────────────────────────────────────

3:00 PM: User asks first question
├─ AMC creates: session_1 (created_at=3:00 PM)
├─ Pass to feedback-loop: {
│    feedback_id: "fb_1",
│    session_id: "session_1",  ← Already validated
│    response_id: "resp_1",
│    source: "active"
│  }
│
└─ Feedback-Loop processes:
   ├─ Uses session_1 as context
   └─ Writes: UnifiedEvaluationRecord(
      session_id="session_1",
      response_id="resp_1",
      ...
    )

3:08 PM: User asks second question (same topic)
├─ AMC checks: last_activity=3:00 PM
├─ Elapsed: 8 minutes (within 10-min window)
├─ Reuse: session_1
├─ Pass to feedback-loop: {
│    feedback_id: "fb_2",
│    session_id: "session_1",  ← Same session
│    response_id: "resp_2",
│    ...
│  }
│
└─ Feedback-Loop processes:
   └─ Same session context → related feedback grouped

3:20 PM: User asks different topic (after 12-min gap)
├─ AMC checks: last_activity=3:08 PM
├─ Elapsed: 12 minutes (EXCEEDS 10-min window)
├─ Create NEW: session_2_rollover_timestamp
├─ Pass to feedback-loop: {
│    feedback_id: "fb_3",
│    session_id: "session_2_rollover_xxx",  ← NEW session
│    response_id: "resp_3",
│    ...
│  }
│
└─ Feedback-Loop processes:
   └─ Different session → fresh context for evaluation
```

---

## AMC Implementation

### **Pseudocode: SessionManager in AMC**

```python
class AMCSessionManager:
    def __init__(self, window_minutes=5, max_window_minutes=10):
        self.active_sessions = {}  # user_id -> {session_id, last_activity_at}
        self.window_minutes = window_minutes
        self.max_window_minutes = max_window_minutes
    
    def get_or_create_session(self, user_id, now=None):
        """
        Get active session for user, or create new one.
        
        Returns: session_id (valid for feedback-loop)
        """
        if not now:
            now = datetime.now(timezone.utc)
        
        session = self.active_sessions.get(user_id)
        
        if session is None:
            # First interaction - create new session
            return self._create_session(user_id, now)
        
        # Check if within active window
        elapsed = (now - session["last_activity_at"]).total_seconds() / 60
        
        if elapsed <= self.max_window_minutes:
            # Still active - update and return
            session["last_activity_at"] = now
            return session["session_id"]
        else:
            # Expired - create new session
            return self._create_session(user_id, now)
    
    def _create_session(self, user_id, now):
        """Create new session with timestamp."""
        session_id = f"sess_{user_id}_{int(now.timestamp())}"
        self.active_sessions[user_id] = {
            "session_id": session_id,
            "created_at": now,
            "last_activity_at": now,
        }
        return session_id
```

### **Usage in AMC Webhook**

```python
@app.post("/feedback")
async def receive_feedback(request):
    """
    When user submits feedback, AMC:
    1. Validates session (5-10 min window)
    2. Passes to feedback-loop with session_id
    """
    user_id = request.user_id
    feedback_text = request.feedback_text
    response_id = request.response_id
    source = request.source  # "active" or "passive"
    
    # Step 1: AMC manages session
    session_manager = AMCSessionManager()
    session_id = session_manager.get_or_create_session(user_id)
    
    # Step 2: AMC creates feedback record
    feedback_id = create_feedback_record(
        user_id=user_id,
        session_id=session_id,  ← Set by AMC
        response_id=response_id,
        feedback_text=feedback_text,
        source=source,
    )
    
    # Step 3: Call feedback-loop (passes validated session_id)
    success = await start_feedback_loop(
        feedback_id=feedback_id,
        session_id=session_id,      ← Already validated
        response_id=response_id,
        source=source,
        db=db,
        evidence_adapter=evidence,
    )
    
    return {"status": "processed", "feedback_id": feedback_id}
```

---

## Feedback-Loop Expectations

### **What Feedback-Loop Receives**

```python
@dataclass
class IncomingFeedback:
    feedback_id: str          # Unique feedback identifier
    session_id: str           # ← Already validated by AMC (within 5-10 min)
    response_id: str          # Response being evaluated
    source: str               # "active" or "passive"
    rating: str               # User's rating
    feedback_text: str        # User's comment
    created_at: datetime      # When feedback was submitted
```

### **Feedback-Loop's Job**

```python
def start_feedback_loop(feedback):
    """
    Process feedback without managing sessions.
    Trust session_id is already valid.
    """
    # Fetch feedback record with validated session_id
    row = db.fetch_feedback_record(feedback.feedback_id)
    # session_id is already set by AMC ✓
    
    # Run 4-step pipeline
    record = RecordBuilder.build(row)
    # Step 1: NER + sentiment
    # Step 2: Evidence enrichment
    # Step 3: Rules (C01-C05)
    # Step 4: Root-cause adjudication
    
    # Write result with session_id as context
    db.write_unified_record(record)
    # session_id preserved throughout ✓
```

---

## Database: What Feedback-Loop Sees

### **response_feedback Table**

```sql
CREATE TABLE response_feedback (
    feedback_id VARCHAR(64) PRIMARY KEY,
    
    -- Context from AMC (including session management)
    session_id VARCHAR(64) NOT NULL,        ← Set by AMC
    response_id VARCHAR(64) NOT NULL,
    
    -- User feedback
    feedback_text TEXT,
    rating_type VARCHAR(20),
    
    -- Ingestion tracking
    ingestion_status VARCHAR(20),           ← Managed by feedback-loop
    created_at VARCHAR(40),                 ← Set by AMC
    
    INDEX idx_session (session_id)
);
```

### **unified_evaluation_records Table**

```sql
CREATE TABLE unified_evaluation_records (
    session_id VARCHAR(36) NOT NULL,        ← From feedback-loop
    response_id VARCHAR(36) NOT NULL,
    
    -- Pipeline outputs (Steps 1-4)
    entry_route VARCHAR(40),
    root_cause VARCHAR(30),
    severity VARCHAR(20),
    
    PRIMARY KEY (session_id, response_id),
    INDEX idx_session (session_id)
);
```

**Key insight:** `session_id` flows from AMC → feedback-loop → database untouched. No management inside feedback-loop.

---

## Session Timeout Scenarios

### **Scenario 1: Active Session (Within 5-10 min)**

```
User Actions
├─ 3:00 PM: Ask question #1
├─ 3:02 PM: Ask question #2 (2 min gap) ← Within window
├─ 3:05 PM: Ask question #3 (3 min gap) ← Within window
└─ Result: All 3 in SAME session_id
```

**AMC Flow:**
```
Q1: session_id = session_A
Q2: elapsed 2 min < 10 min → session_id = session_A
Q3: elapsed 3 min < 10 min → session_id = session_A
```

### **Scenario 2: Session Rollover (>10 min)**

```
User Actions
├─ 3:00 PM: Ask question #1
├─ 3:05 PM: Ask question #2 (5 min gap) ← Within window
├─ 3:20 PM: Ask question #3 (15 min gap) ← EXCEEDS window
└─ Result: Q1+Q2 in session_A, Q3 in NEW session_B
```

**AMC Flow:**
```
Q1: session_id = session_A (created_at=3:00)
Q2: elapsed 5 min < 10 min → session_id = session_A (last_activity=3:05)
Q3: elapsed 15 min > 10 min → session_id = session_B_rollover (new session)
```

---

## Configuration

### **Window Sizes**

AMC should configure:

```python
# In AMC config
FEEDBACK_SESSION_WINDOW_MINUTES = 5      # Min active window
FEEDBACK_SESSION_MAX_WINDOW_MINUTES = 10 # Max before rollover
```

These are **AMC's responsibility**, not feedback-loop's.

---

## Benefits of This Design

1. **Stateless Feedback-Loop**
   - ✅ No session management complexity
   - ✅ Can scale horizontally (no state)
   - ✅ Simpler to test (just process feedback)

2. **Clear Separation**
   - ✅ AMC owns: session lifecycle, timeouts, rollover
   - ✅ Feedback-loop owns: feedback evaluation pipeline
   - ✅ No confusion about responsibilities

3. **Flexibility**
   - ✅ AMC can change window timing without touching feedback-loop
   - ✅ AMC can implement custom session logic (e.g., user-based windows)
   - ✅ Feedback-loop agnostic to session details

4. **Single Source of Truth**
   - ✅ AMC database is authoritative for session state
   - ✅ Feedback-loop is read-only on sessions (only uses session_id)
   - ✅ No sync issues between two session managers

---

## Summary

✅ **AMC manages sessions** (5-10 minute windows, timeouts, rollover)
✅ **Feedback-loop is stateless** (trusts session_id, processes feedback)
✅ **Clean boundary** (AMC → feedback-loop → database)
✅ **SQLite used for feedback evaluation**, not session management

This is the correct architecture. 🎯
