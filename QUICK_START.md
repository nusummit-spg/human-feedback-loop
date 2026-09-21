# Quick Start Guide - End-to-End Testing

## Setup (5 minutes)

### 1. Create Virtual Environment

```bash
cd /c/Workspaces/human-feedback-loop
python -m venv venv

# Activate it
source venv/Scripts/activate  # Git Bash
# OR
.\venv\Scripts\Activate.ps1   # PowerShell
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Download spaCy Model (one-time, ~50MB)

```bash
python -m spacy download en_core_web_sm
```

This step takes a few minutes - it downloads the NLP model for NER extraction.

---

## Run End-to-End Test

Once the venv is ready:

```bash
# Make sure you're in repo root
cd /c/Workspaces/human-feedback-loop

# Activate venv if not already
source venv/Scripts/activate

# Run the test
python E2E_TEST_SCRIPT.py
```

---

## What Happens

The script will:

1. **Create SQLite database** with schema
2. **Populate test data:**
   - QueryEvidence: "What is NAV of Axis Bluechip Fund?"
   - ResponseFeedback: User says "That NAV is outdated. Current NAV is ₹152.50"
3. **Run 4-step pipeline:**
   - Step 1: Classification (extract entities, sentiment, intent)
   - Step 2: Enrichment (fetch frozen evidence, detect dissatisfaction)
   - Step 3: Router (apply rules C01-C05, map severity)
   - Step 4: Adjudication (8-priority root-cause assignment)
4. **Write output** to unified_evaluation_records table
5. **Display results:**
   - Entry Route: HITL (active feedback)
   - Root Cause: MODEL (hallucination detection)
   - Severity: HIGH (numeric accuracy mismatch)

---

## Expected Output

```
================================================================================
🧪 FEEDBACK-LOOP END-TO-END TEST
================================================================================

📦 Setting up database: test_feedback.db
✅ Database schema created

📝 Populating test data...
  ✓ Created QueryEvidence: xxx
  ✓ Created ResponseFeedback: xxx
  ✓ Session ID: xxx

🚀 Running end-to-end pipeline...

📋 Pipeline Stages:
  [1] Classification (NER + Sentiment + Intent)
  [2] Enrichment (Evidence + Dissatisfaction Detection)
  [3] Adaptive Router (Rules C01-C05)
  [4] Adjudication (8-Priority Root-Cause Chain)

⏳ Processing feedback...
✅ Pipeline completed: True

================================================================================
📊 UNIFIED EVALUATION RECORD OUTPUT
================================================================================

Session ID:        sess_xxx
Response ID:       resp_xxx
Entry Route:       hitl
Root Cause:        model
Severity:          high
Lifecycle Status:  open
Created At:        2026-09-21T...

Dissatisfaction Signals: {...}

================================================================================
✅ TEST COMPLETE
================================================================================

📌 Summary:
  • Database: test_feedback.db
  • Feedback ID: fb_xxx
  • Response ID: resp_xxx
  • Session ID: sess_xxx

  Check the database with:
    sqlite3 test_feedback.db 'SELECT * FROM unified_evaluation_records;'
```

---

## Verify Results

After the test completes, query the database:

```bash
# Show all unified records
sqlite3 test_feedback.db "SELECT session_id, response_id, entry_route, root_cause, severity FROM unified_evaluation_records;"

# Show with formatting
sqlite3 test_feedback.db ".headers on" ".mode column" "SELECT * FROM unified_evaluation_records LIMIT 1;"
```

---

## Troubleshooting

### `ModuleNotFoundError: No module named 'src'`
- **Fix:** Make sure you're in the repo root directory when running the test
- Check: `pwd` should show `.../human-feedback-loop`

### `ImportError: cannot import name 'validate_core_schema'`
- **Fix:** Virtual environment has version mismatch
- Solution: `pip install --upgrade pydantic pydantic-core`

### `No module named 'spacy'`
- **Fix:** spaCy not installed
- Solution: `pip install spacy` and `python -m spacy download en_core_web_sm`

### Test hangs on spaCy model download
- **Fix:** First-time setup takes time (50MB download)
- Wait 5-10 minutes, or run separately: `python -m spacy download en_core_web_sm`

---

## What's Being Tested

✅ **Database Layer**
- SQLite adapter connects to database
- Schema creation works
- Read/write to response_feedback and unified_evaluation_records

✅ **Evidence Adapter**
- Fetches query_evidence snapshots
- Extracts evidence chunks
- Freezes data at ingestion time

✅ **4-Step Pipeline**
- Step 1: NER + sentiment + intent classification
- Step 2: Evidence enrichment + dissatisfaction detection
- Step 3: Rules (C01-C05) application + severity mapping
- Step 4: Root-cause adjudication (8-priority chain)

✅ **End-to-End Flow**
- Feedback ingestion
- Pipeline orchestration
- Database persistence
- Output validation

---

## Next Steps

After E2E test passes:

1. **Run unit tests** for individual steps:
   ```bash
   pytest tests/ -v
   ```

2. **Check database contents**:
   ```bash
   sqlite3 test_feedback.db ".tables"
   ```

3. **Deploy to production** (PostgreSQL URL instead of SQLite)

---

## Commands Reference

```bash
# Setup
python -m venv venv
source venv/Scripts/activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm

# Test
python E2E_TEST_SCRIPT.py

# Verify
sqlite3 test_feedback.db "SELECT * FROM unified_evaluation_records;"

# Run all tests
pytest tests/ -v

# Check coverage
pytest --cov=src/feedback_loop tests/
```

---

**Total setup time:** ~10 minutes (mostly spaCy model download)  
**Test runtime:** ~30-60 seconds  
**Database:** `test_feedback.db` (created by test)

✅ Ready to test! 🚀
