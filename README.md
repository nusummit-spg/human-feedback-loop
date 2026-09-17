# Human Feedback Loop Module

Installable Python package for the AMC feedback pipeline.

## Architecture

```
AMC (host app)
   │
   └── start_feedback_loop(feedback_id, session_id, response_id, source)
            │
            ▼
      IngestService.on_ingest()
            │
            ├── [concurrent] Step 1 — ClassificationService   (active only)
            ├── [concurrent] Step 2 — EvidenceEnrichmentService
            │
            ├── [join] ──────────────────────────────────────────
            │
            ├── Step 3 — AdaptiveRouterService
            └── Step 4 — AdjudicationService
                        │
                        └── DB write → unified_evaluation_records
```

## Installation

### From git (pin to a tag, not a branch)

```
git+https://github.com/your-org/human-feedback-loop.git@v0.1.0
```

Add to the host `requirements.txt`:

```
human-feedback-loop @ git+https://github.com/your-org/human-feedback-loop.git@v0.1.0
```

### From a private PyPI (recommended for production)

```
pip install human-feedback-loop==0.1.0 --index-url https://your-private-pypi/simple
```

## Usage

```python
from feedback_loop import start_feedback_loop, FeedbackLoopConfig
from feedback_loop.adapters import YourDatabaseAdapter, YourEvidenceAdapter

config = FeedbackLoopConfig()
db = YourDatabaseAdapter(connection_string="...")
evidence = YourEvidenceAdapter(amc_base_url="...")

start_feedback_loop(
    feedback_id="fb_9c4f1a",
    session_id="sess_2201",
    response_id="resp_9c4f1a",
    source="active",
    config=config,
    db=db,
    evidence_adapter=evidence,
)
```

## Running tests

```
pip install -e ".[dev]"
pytest --cov=feedback_loop
```
