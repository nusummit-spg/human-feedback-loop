# Python Environment Setup Guide

## Quick Start (5 minutes)

### 1. Create Virtual Environment

```bash
cd /c/Workspaces/human-feedback-loop

# Windows PowerShell
python -m venv venv
.\venv\Scripts\Activate.ps1

# Or Windows CMD
python -m venv venv
venv\Scripts\activate.bat

# Or Git Bash
python -m venv venv
source venv/Scripts/activate
```

### 2. Install Dependencies

```bash
# Install production + dev dependencies
pip install -e ".[dev]"

# Or use requirements.txt
pip install -r requirements.txt
```

### 3. Verify Installation

```bash
python --version
python -c "import sqlalchemy; print(f'SQLAlchemy {sqlalchemy.__version__}')"
python -c "import pydantic; print(f'Pydantic {pydantic.__version__}')"
python -c "import pytest; print(f'pytest {pytest.__version__}')"
```

---

## Dependencies Installed

### Production Runtime
```
pydantic==2.7.1              # Domain models validation
vaderSentiment==3.3.1        # Sentiment analysis (Step 1)
spacy==3.7.4                 # NER entity extraction (Step 1)
scikit-learn==1.4.2          # TF-IDF for similarity (Step 2)
numpy==1.26.4                # Numerical operations
httpx==0.27.0                # HTTP client (for AMC API)
tenacity==8.3.0              # Retry logic
python-dateutil==2.9.0       # Date parsing
structlog==24.1.0            # Structured logging
sqlalchemy==2.0.23           # ORM for database adapters ✨
psycopg2-binary==2.9.9       # PostgreSQL driver ✨
```

### Development/Testing
```
pytest==8.2.0                # Test runner
pytest-asyncio==0.23.6       # Async test support
pytest-cov==5.0.0            # Coverage reporting
freezegun==1.5.0             # Time mocking
```

---

## Running Tests

### Run All Tests
```bash
pytest
```

### Run Specific Test Suite
```bash
# Unit tests only
pytest tests/test_models.py -v
pytest tests/test_classification.py -v
pytest tests/test_enrichment.py -v
pytest tests/test_router.py -v
pytest tests/test_adjudication.py -v

# Integration tests
pytest tests/test_orchestrator.py -v

# Database adapter tests
pytest tests/test_adapters.py -v

# End-to-end tests
pytest tests/test_ingest.py -v
```

### Run with Coverage
```bash
pytest --cov=src/feedback_loop --cov-report=term-missing
```

---

## Database Setup

### Option 1: SQLite (Development)

```python
from feedback_loop.adapters.db import SQLiteDatabaseAdapter
from feedback_loop.adapters.sqlite_evidence_adapter import SQLiteEvidenceAdapter
from feedback_loop.models import Base
from sqlalchemy import create_engine

# Create database file
db = SQLiteDatabaseAdapter("sqlite:///feedback.db")
evidence = SQLiteEvidenceAdapter("sqlite:///amc.db")

# Initialize schema
engine = create_engine("sqlite:///feedback.db")
Base.metadata.create_all(engine)
```

### Option 2: PostgreSQL (Production)

```python
from feedback_loop.adapters.db import SQLiteDatabaseAdapter
from feedback_loop.adapters.sqlite_evidence_adapter import SQLiteEvidenceAdapter
from feedback_loop.models import Base
from sqlalchemy import create_engine

# Connection string format:
# postgresql://user:password@host:port/database

db = SQLiteDatabaseAdapter("postgresql://feedback_user:pass@localhost:5432/feedback_db")
evidence = SQLiteEvidenceAdapter("postgresql://amc_user:pass@localhost:5432/amc_db")

# Create schema
engine = create_engine("postgresql://feedback_user:pass@localhost:5432/feedback_db")
Base.metadata.create_all(engine)
```

---

## IDE Setup

### VS Code

1. Open the project folder
2. Python extension will ask to select interpreter
3. Choose: `./venv/Scripts/python` (Windows) or `./venv/bin/python` (Mac/Linux)
4. Configure pytest:
   - Settings → Python: Testing
   - Test Framework: pytest
   - Test Path: `tests`

### PyCharm

1. Open project
2. File → Settings → Project → Python Interpreter
3. Click ⚙️ → Add → Existing Environment
4. Browse to `./venv/Scripts/python.exe` (Windows) or `./venv/bin/python` (Mac/Linux)
5. Test discovery should auto-detect pytest

---

## Troubleshooting

### `ModuleNotFoundError: No module named 'sqlalchemy'`

**Solution:** Install dependencies
```bash
pip install sqlalchemy==2.0.23 psycopg2-binary==2.9.9
# Or use full install
pip install -r requirements.txt
```

### `ImportError: No module named 'spacy'`

**Download the language model:**
```bash
python -m spacy download en_core_web_sm
```

### Virtual environment not activating

```bash
# Verify venv exists
ls venv/

# Recreate if needed
python -m venv venv --clear
source venv/Scripts/activate  # or ./venv/Scripts/Activate.ps1
pip install -r requirements.txt
```

### PostgreSQL connection refused

```bash
# Check if PostgreSQL is running
psql --version

# Test connection
psql -h localhost -U feedback_user -d feedback_db

# If missing driver:
pip install psycopg2-binary
```

---

## Running the Pipeline

### In Python REPL

```python
from feedback_loop.adapters.db import SQLiteDatabaseAdapter
from feedback_loop.adapters.sqlite_evidence_adapter import SQLiteEvidenceAdapter
from feedback_loop.config import FeedbackLoopConfig
from feedback_loop.ingest import IngestService

# Initialize
config = FeedbackLoopConfig()
db = SQLiteDatabaseAdapter("sqlite:///feedback.db")
evidence = SQLiteEvidenceAdapter("sqlite:///amc.db")
ingest = IngestService(config, db, evidence)

# Process feedback
success = ingest.on_ingest(
    feedback_id="fb_123",
    session_id="sess_1",
    response_id="resp_1",
    source="active"
)

print(f"Success: {success}")
```

### Via API

```python
from feedback_loop import start_feedback_loop, FeedbackLoopConfig

config = FeedbackLoopConfig()
db = SQLiteDatabaseAdapter("sqlite:///feedback.db")
evidence = SQLiteEvidenceAdapter("sqlite:///amc.db")

success = start_feedback_loop(
    feedback_id="fb_123",
    session_id="sess_1",
    response_id="resp_1",
    source="active",
    config=config,
    db=db,
    evidence_adapter=evidence,
)
```

---

## Environment Variables

Create `.env` file (optional):

```bash
# Database URLs
FEEDBACK_DB_URL=postgresql://feedback_user:pass@localhost:5432/feedback_db
AMC_DB_URL=postgresql://amc_user:pass@localhost:5432/amc_db

# Feature flags
DEBUG=true
LOG_LEVEL=INFO
```

Load in Python:

```python
import os
from dotenv import load_dotenv

load_dotenv()

db_url = os.getenv("FEEDBACK_DB_URL", "sqlite:///feedback.db")
amc_url = os.getenv("AMC_DB_URL", "sqlite:///amc.db")
```

---

## Next Steps

1. ✅ Create virtual environment
2. ✅ Install dependencies
3. ✅ Run tests: `pytest`
4. ✅ Set up database (SQLite or PostgreSQL)
5. ✅ Run the pipeline on sample feedback
6. ✅ Check logs and outputs

---

**Need help?** See individual adapter guides:
- `SQLITE_ADAPTER_IMPLEMENTATION.md` — Database adapter reference
- `PRODUCTION_EVIDENCE_ADAPTER_GUIDE.md` — Evidence adapter reference
