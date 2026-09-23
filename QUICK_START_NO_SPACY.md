# Quick Start - Without spaCy Model Download

If the spaCy model download fails, use this approach:

## Setup (2 minutes, no model download)

```bash
cd /c/Workspaces/human-feedback-loop

# Create venv
python -m venv venv
source venv/Scripts/activate

# Install dependencies
pip install -r requirements.txt
```

## Run Test (uses fallback NER)

```bash
python E2E_TEST_SCRIPT.py
```

**Note:** Without the spaCy model, the NER step uses simple regex-based entity extraction. The pipeline still works end-to-end!

## If you want the full spaCy model later

```bash
# Download directly (bypasses pip issues)
python -c "import spacy.cli; spacy.cli.download('en_core_web_sm')"

# Or download manually
cd ~/Downloads
wget https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.7.4/en_core_web_sm-3.7.4-py3-none-any.whl
pip install en_core_web_sm-3.7.4-py3-none-any.whl
```

---

## The Fallback NER

The `ClassificationService` gracefully handles missing spaCy:

1. **With spaCy:** Full NER (ORG, PRODUCT, PERSON, GPE)
2. **Without spaCy:** Simple capitalized-phrase extraction

Both produce valid results for testing. The pipeline works the same either way.

## Commands Quick Reference

```bash
# Setup
python -m venv venv
source venv/Scripts/activate
pip install -r requirements.txt

# Run test (no spacy needed)
python E2E_TEST_SCRIPT.py

# Verify results
sqlite3 test_feedback.db "SELECT * FROM unified_evaluation_records LIMIT 1;"
```

**Total time:** ~2 minutes setup + 1 minute test = **3 minutes total**

Ready to go! 🚀
