# SQLite Database Setup Guide

## Quick Start

### Option 1: Python Script (recommended on Windows)

```powershell
# From the repo root
cd src\database\scripts
C:\Python\python.exe init_sqlite_db.py
```

This creates `compliance_audit.db` in the current directory, prints all
table names, and dumps the full column/index schema.

---

### Option 2: SQL Script via Python one-liner

The `sqlite3` CLI is not installed by default on Windows.  Use Python instead:

```powershell
C:\Python\python.exe -c "
import sqlite3, pathlib
sql = pathlib.Path('create_tables.sql').read_text()
conn = sqlite3.connect('compliance_audit.db')
conn.executescript(sql)
conn.close()
print('Done.')
"
```

---

### Option 3: Install the sqlite3 CLI (optional)

Download the precompiled binary from https://www.sqlite.org/download.html
(`sqlite-tools-win-x64-*.zip`), extract `sqlite3.exe`, and add its folder
to your PATH.  After that the Unix-style commands in this guide work as-is.

---

## Database Location

Both methods create: **`compliance_audit.db`** in the current working directory.

---

## 8 Tables Created

| # | Table | Purpose |
|----|-------|---------|
| 1 | `audit_metadata` | Audit runs and scope |
| 2 | `violations` | Individual findings |
| 3 | `response_feedback` | Human feedback |
| 4 | `query_evidence` | Query traces |
| 5 | `compliance_rules` | Rule definitions |
| 6 | `fund_schemes` | Fund metadata |
| 7 | `sessions` | Chat sessions |
| 8 | `unified_evaluation_records` | Feedback loop output |

---

## Querying the Database

### From Python (sqlite3 stdlib)

```python
import sqlite3
from pathlib import Path

conn = sqlite3.connect(Path.cwd() / "compliance_audit.db")
cursor = conn.cursor()

# List tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
print(cursor.fetchall())

# Count rows
cursor.execute("SELECT COUNT(*) FROM audit_metadata")
print(cursor.fetchone()[0])

conn.close()
```

### From Python (SQLAlchemy)

```python
from sqlalchemy import create_engine, text

engine = create_engine("sqlite:///compliance_audit.db")
with engine.connect() as conn:
    result = conn.execute(text("SELECT * FROM audit_metadata LIMIT 5"))
    for row in result:
        print(row)
```

### From PowerShell (quick one-liners)

```powershell
# List tables
python -c "import sqlite3; c=sqlite3.connect('compliance_audit.db'); print([r[0] for r in c.execute(\"SELECT name FROM sqlite_master WHERE type='table'\")])"

# Row count for a table
python -c "import sqlite3; c=sqlite3.connect('compliance_audit.db'); print(c.execute('SELECT COUNT(*) FROM violations').fetchone()[0])"

# Database file size in MB
(Get-Item compliance_audit.db).Length / 1MB
```

---

## Sample DML

### Insert an audit run

```sql
INSERT INTO audit_metadata
(audit_id, audit_run_timestamp, region, audit_type, funds_audited_count,
 total_rules_evaluated, total_violations_detected, status, created_at, updated_at)
VALUES
('audit_20260908_001', '2026-09-08T10:30:00Z', 'SEBI', 'batch', 150,
 45, 12, 'completed', '2026-09-08T10:30:00Z', '2026-09-08T10:35:00Z');
```

### Insert a violation

```sql
INSERT INTO violations
(violation_id, audit_id, rule_id, fund_id, severity, violation_type, region,
 description, confidence_score, status, detected_at, created_at, updated_at)
VALUES
('viol_001', 'audit_20260908_001', 'RULE_C03', 'FUND_AXIS_BC', 'high', 'portfolio', 'SEBI',
 'Numeric value exceeds threshold by 15%', 0.85, 'detected',
 '2026-09-08T10:31:00Z', '2026-09-08T10:31:00Z', '2026-09-08T10:31:00Z');
```

### Query violations by severity

```sql
SELECT severity, COUNT(*) as count
FROM violations
WHERE audit_id = 'audit_20260908_001'
GROUP BY severity
ORDER BY
  CASE severity
    WHEN 'critical' THEN 1
    WHEN 'high'     THEN 2
    WHEN 'medium'   THEN 3
    WHEN 'low'      THEN 4
  END;
```

---

## Backup and Restore

```powershell
# Backup via Python
python -c "
import sqlite3
src = sqlite3.connect('compliance_audit.db')
bak = sqlite3.connect('compliance_audit_backup.db')
src.backup(bak)
bak.close(); src.close()
print('Backup complete.')
"

# Export to SQL dump
python -c "
import sqlite3
conn = sqlite3.connect('compliance_audit.db')
with open('backup.sql', 'w') as f:
    for line in conn.iterdump():
        f.write(line + '\n')
conn.close()
print('Dump complete.')
"

# Restore from SQL dump
python -c "
import sqlite3, pathlib
sql = pathlib.Path('backup.sql').read_text()
conn = sqlite3.connect('restored.db')
conn.executescript(sql)
conn.close()
print('Restore complete.')
"
```

---

## Verification

```python
import sqlite3
conn = sqlite3.connect("compliance_audit.db")

# Table count — expected 8
tables = conn.execute(
    "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
).fetchone()[0]
print(f"Tables: {tables}")

# Index count — expected 50+
indices = conn.execute(
    "SELECT COUNT(*) FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'"
).fetchone()[0]
print(f"Indices: {indices}")

conn.close()
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `sqlite3` not recognized | Use `python init_sqlite_db.py` instead (see Option 1) |
| `ModuleNotFoundError: No module named 'app'` | Run the script from `src\database\scripts`, not the repo root |
| Database is locked | Close all open Python processes / connections holding the file |
| Permission denied | `icacls compliance_audit.db /grant:r "$env:USERNAME":F` |

---

## Files

| File | Purpose |
|------|---------|
| `create_tables.sql` | Raw SQL schema |
| `init_sqlite_db.py` | Python initialiser (cross-platform, recommended) |
| `SQLITE_SETUP_GUIDE.md` | This guide |
