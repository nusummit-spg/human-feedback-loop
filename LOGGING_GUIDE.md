# Structured Logging Guide

## Log Directory Structure

```
logs/
├── session_<session_id_1>/
│   ├── <feedback_id_1>/
│   │   ├── step_1_classification_2026-09-22T08-30-45.log
│   │   ├── step_2_enrichment_2026-09-22T08-30-46.log
│   │   ├── step_3_router_2026-09-22T08-30-47.log
│   │   └── step_4_adjudication_2026-09-22T08-30-48.log
│   ├── <feedback_id_2>/
│   │   ├── step_1_classification_...log
│   │   ├── step_2_enrichment_...log
│   │   └── ...
│   └── <feedback_id_3>/
│       └── ...
└── session_<session_id_2>/
    ├── <feedback_id_4>/
    └── ...
```

## Benefits

✅ **Session Organization:** All feedback from one user session grouped together  
✅ **Feedback Grouping:** All 4 steps for one feedback item in one folder  
✅ **Short Filenames:** Easy to read (no feedback_id in filename)  
✅ **Easy Navigation:** `logs/session_ABC/FB_123/` shows all steps for that feedback  
✅ **Clean Hierarchy:** Step name → timestamp, nothing else  

## Quick Navigation

```bash
# List all sessions
ls logs/

# View all feedback items in a session
ls logs/session_<session_id>/

# View all steps for one feedback item
ls logs/session_<session_id>/<feedback_id>/

# Read classification log for specific feedback
cat logs/session_<id>/<feedback_id>/step_1_classification_*.log

# Pretty-print JSON logs
cat logs/session_<id>/<feedback_id>/step_*.log | python -m json.tool
```

## Log File Contents

Each log file contains JSON records (one per line):

```json
{
  "timestamp": "2026-09-22T08:30:45.123456+00:00",
  "step": "step_1_classification",
  "session_id": "sess_abc123",
  "feedback_id": "fb_xyz789",
  "level": "INFO",
  "message": "classification_complete",
  "entity": "NAV",
  "intent": "correction",
  "sentiment": -0.5
}
```

## Analysis Examples

### Find all feedback in a session
```bash
find logs/session_ABC/ -type d -mindepth 1 | sort
```

### Count feedback items processed in a session
```bash
ls -d logs/session_ABC/*/ | wc -l
```

### Extract root causes from adjudication logs
```bash
grep '"root_cause"' logs/session_*/*/step_4_adjudication_*.log | \
  python -c "import sys, json; [print(json.loads(line.split(':', 1)[1])['root_cause']) for line in sys.stdin]" | \
  sort | uniq -c
```

### Timeline of all steps for one feedback
```bash
for step in step_1 step_2 step_3 step_4; do
  echo "=== $step ==="
  cat logs/session_ABC/FB_123/${step}_*.log | python -m json.tool | grep "timestamp\|message"
done
```

## Integration with Services

Services automatically receive `session_id` and `feedback_id` from the orchestrator and bind them to the logger:

```python
def run(self, row: FeedbackRecord, session_id: str = None, feedback_id: str = None):
    # Bind session context to structlog
    if session_id and feedback_id:
        log = logger.bind(session_id=session_id, feedback_id=feedback_id)
    else:
        log = logger
    
    # All log calls now include session_id and feedback_id
    log.info("NER complete", entity_count=5, sentiment=0.8)
```

## Production Deployment

### Log Rotation
```python
from logging.handlers import RotatingFileHandler

handler = RotatingFileHandler(
    "logs/feedback.log",
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5
)
```

### Centralized Logging
Forward to ELK, Splunk, Datadog:
```bash
# Monitor logs directory and send to logging service
tail -f logs/session_*/*/step_*.log | nc logserver.example.com 5000
```

### Compression
```bash
# Archive old logs (>30 days)
find logs/ -name "*.log" -mtime +30 -exec gzip {} \;

# Clean up very old archives (>90 days)
find logs/ -name "*.log.gz" -mtime +90 -delete
```

## Troubleshooting

### No logs generated
- Check if `logs/` directory was created
- Verify `session_id` and `feedback_id` are passed to services
- Check for exceptions in console output

### Logs in wrong location
- Expected: `logs/session_<id>/<feedback_id>/step_*.log`
- Check logging_config.py is using nested directory structure

### Parsing JSON logs
```bash
# Pretty-print single line
echo '{"msg": "test"}' | python -m json.tool

# Parse entire file
python -c "
import json
with open('logs/session_ABC/FB_123/step_1_classification_*.log') as f:
    for line in f:
        record = json.loads(line)
        print(f\"{record['message']}: {record.get('entity', 'N/A')}\")
"
```

## Related Files

- `src/feedback_loop/logging_config.py` — Logging configuration & directory setup
- `src/feedback_loop/services/*.py` — Service implementations with logging
- `QUICK_START.md` — Setup guide with logging example
- `E2E_MULTI_FEEDBACK_TEST.py` — Multi-feedback test that generates logs

