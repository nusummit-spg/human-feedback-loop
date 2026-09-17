"""
SQLite Database Initialization Script
======================================

Drops and recreates all tables from the current models.py.

Usage (run from any directory):
    python src/database/scripts/init_sqlite_db.py

    # or from within the scripts directory:
    cd src/database/scripts
    python init_sqlite_db.py

Creates: compliance_audit.db in the current working directory.

WARNING: drops all existing tables before recreating them.
         Do not run against a database with data you need to keep.
"""

import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent   # .../src/database/scripts
_DATABASE_DIR = _SCRIPTS_DIR.parent              # .../src/database
sys.path.insert(0, str(_DATABASE_DIR))

from sqlalchemy import create_engine, text, inspect

from app.core.models import (
    Base,
    AuditMetadata,
    Violation,
    ResponseFeedback,
    QueryEvidence,
    ComplianceRule,
    FundScheme,
    ChatSession,
    UnifiedEvaluationRecord,
)

DB_PATH = Path.cwd() / "compliance_audit.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"


def drop_all_tables(engine):
    """
    Drop tables in reverse-dependency order so FK constraints are satisfied.
    SQLite does not enforce FKs by default, but we keep the order clean anyway.
    """
    # Disable FK enforcement during drop so order does not matter
    with engine.connect() as conn:
        conn.execute(text("PRAGMA foreign_keys=OFF"))

    print("Dropping existing tables...")
    Base.metadata.drop_all(engine)

    with engine.connect() as conn:
        conn.execute(text("PRAGMA foreign_keys=ON"))
    print("  All tables dropped.")


def create_all_tables(engine):
    print("Creating tables from updated models...")
    Base.metadata.create_all(engine)
    print("  Tables created.")


def verify(engine):
    inspector = inspect(engine)
    tables = sorted(inspector.get_table_names())
    print(f"\nTables ({len(tables)}):")
    for t in tables:
        cols = inspector.get_columns(t)
        print(f"\n  {t}  ({len(cols)} columns)")
        for c in cols:
            nullable = "NULL" if c["nullable"] else "NOT NULL"
            pk = " [PK]" if c.get("primary_key") else ""
            print(f"    {c['name']:<35} {str(c['type']):<20} {nullable}{pk}")

        idxs = inspector.get_indexes(t)
        if idxs:
            print(f"    -- {len(idxs)} index(es)")


if __name__ == "__main__":
    print(f"Database : {DB_PATH}\n")

    engine = create_engine(
        DATABASE_URL,
        echo=False,
        connect_args={"check_same_thread": False},
    )

    # Enable FK pragmas on every connection
    from sqlalchemy import event

    @event.listens_for(engine, "connect")
    def _enable_fk(dbapi_conn, _rec):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    try:
        drop_all_tables(engine)
        create_all_tables(engine)
        verify(engine)
        print("\nDone — database is ready.")
    except Exception as exc:
        import traceback
        print(f"\nFailed: {exc}")
        traceback.print_exc()
        sys.exit(1)
