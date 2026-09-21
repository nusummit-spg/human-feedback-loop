# Structured Logging Guide

## Overview

The feedback-loop pipeline now has centralized structured logging with per-step audit trails.

### Log Structure

```
logs/
├── session_<session_id_1>/
│   ├── step_1_classification_<feedback_id_1>_2026-09-21T12-17-00.log
│   ├── step_2_enrichment_<feedback_id_1>_2026-09-21T12-17-01.log
│   ├── step_3_router_<feedback_id_1>_2026-09-21T12-17-02.log
│   └── step_4_adjudication_<feedback_id_1>_2026-09-21T12-17-03.log
├── session_<session_id_2>/
│   ├── step_1_classification_<feedback_id_2>_2026-09-21T12-18-00.log
│   └── ...
```

## Benefits

✅ **Session Grouping:** All logs for a user session in one directory  
✅ **Step Tracking:** Separate files per pipeline step for easy debugging  
✅ **Machine-Readable:** JSON format for log analysis & monitoring  
✅ **Human-Readable:** Console output for interactive debugging  
✅ **ISO Timestamps:** Sortable filenames for easy navigation  
✅ **Full Audit Trail:** Every action captured with context  

## Integration Examples

### Step 1: Classification Service

```python
from src.feedback_loop.logging_config import get_pipeline_logger

class ClassificationService:
    def run(self, feedback_record: FeedbackRecord, session_id: str, feedback_id: str):
        logger = get_pipeline_logger("classification", session_id, feedback_id)
        
        logger.info("Starting NER extraction", 
                   text_length=len(feedback_record.feedback_text))
        
        entities = self.ner_extractor.extract(feedback_record.feedback_text)
        logger.info("NER complete", 
                   entity_count=len(entities),
                   entities=[e.text for e in entities])
        
        sentiment = self.vader.polarity_scores(feedback_record.feedback_text)
        logger.info("Sentiment analysis complete",
                   sentiment_score=sentiment["compound"],
                   positive=sentiment["pos"],
                   negative=sentiment["neg"],
                   neutral=sentiment["neu"])
        
        return ClassificationOutput(...)
```

### Step 2: Enrichment Service

```python
logger = get_pipeline_logger("enrichment", session_id, feedback_id)

logger.info("Fetching evidence snapshot", response_id=row.response_id)

snapshot = self.evidence_adapter.get_evidence_snapshot(row.response_id)

logger.info("Evidence snapshot frozen",
           evidence_chunk_count=len(snapshot.evidence_selected))
```

### Step 3: Router Service

```python
logger = get_pipeline_logger("router", session_id, feedback_id)

logger.info("Applying routing rules", rule_count=len(self.rules))

fired_rules = []
for rule in self.rules:
    if rule.matches(enrichment_output):
        fired_rules.append(rule.code)

logger.info("Routing complete", rules_fired=fired_rules)
```

### Step 4: Adjudication Service

```python
logger = get_pipeline_logger("adjudication", session_id, feedback_id)

logger.info("Starting root-cause adjudication")

root_cause = self.find_root_cause(router_output)

logger.info("Adjudication complete", root_cause=root_cause)
```

## Log File Format

### File Output (JSON)
```json
{"timestamp": "2026-09-21T12:17:00.123Z", "step": "step_1_classification", "session_id": "sess_abc123", "feedback_id": "fb_xyz789", "level": "INFO", "message": "NER complete", "entity_count": 5}
```

### Console Output
```
[step_1_classification] INFO: NER complete
[step_2_enrichment] INFO: Evidence snapshot frozen
```

## Naming Nomenclature

```
<step_name>_<feedback_id>_<ISO_timestamp>.log
```

- **step_name:** Standardized (step_1_classification, etc.)
- **feedback_id:** Unique per feedback, correlates across all steps
- **ISO_timestamp:** Sortable, helps find recent sessions

Organization:
- **Session directories:** Group related feedback together
- **Step files:** Easy to find specific pipeline stage
- **Timestamps:** Track execution timing

## Usage

```python
from src.feedback_loop.logging_config import get_pipeline_logger

# Create logger for this step
logger = get_pipeline_logger("classification", session_id, feedback_id)

# Log with custom fields
logger.info("NER complete", entity_count=5, entities=["NAV", "Fund"])
```

Fields are automatically added:
- `timestamp` (ISO 8601)
- `step` (step_1_classification, etc.)
- `session_id` (from your code)
- `feedback_id` (from your code)
- `level` (INFO, DEBUG, ERROR)
- `message` (your message)
- Any custom fields you pass as kwargs

## Querying

```bash
# Find logs for a session
ls logs/session_<session_id>/

# Find logs for a feedback item
grep -r '<feedback_id>' logs/

# Parse JSON logs
python -c "
import json
with open('logs/session_xyz/step_1_classification_fb_123.log') as f:
    for line in f:
        record = json.loads(line)
        print(f\"{record['message']} - {record['entity_count']}\")
"

# Real-time monitoring
tail -f logs/session_*/step_*.log
```

## Best Practices

### DO
✅ Log at step boundaries (entry and exit)  
✅ Include quantitative metrics (counts, scores)  
✅ Use structured fields for machine parsing  
✅ Group logs by session for interactions  

### DON'T
❌ Log sensitive data (passwords, keys, PII)  
❌ Log very long strings (truncate)  
❌ Use generic messages ("processing...")  
❌ Forget to handle log rotation in production  

## Production

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
Forward to ELK, Splunk, Datadog, etc using syslog or file-based forwarders.

### Archive Old Logs
```bash
find logs/ -type f -mtime +30 -exec gzip {} \;
```
