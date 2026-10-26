"""
Centralized logging configuration for feedback-loop pipeline.

Provides structured logging with automatic log file creation per session/step.

Usage:
    from feedback_loop.logging_config import get_step_logger

    logger = get_step_logger("classification", session_id, feedback_id)
    logger.info("NER extraction complete", entity_count=5)
"""

import logging
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional


# Recommended log directory structure:
# logs/
#   session_<session_id>/
#     step_1_classification_<feedback_id>_<timestamp>.log
#     step_2_enrichment_<feedback_id>_<timestamp>.log
#     step_3_router_<feedback_id>_<timestamp>.log
#     step_4_adjudication_<feedback_id>_<timestamp>.log

def _ensure_log_dir() -> Path:
    """Create logs directory if it doesn't exist."""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    return log_dir


def get_step_logger(
    step_name: str,
    session_id: str,
    feedback_id: str,
    log_level: int = logging.INFO,
) -> logging.Logger:
    """
    Create a logger for a specific pipeline step.

    Args:
        step_name: Name of the step (e.g., "classification", "enrichment")
        session_id: User session ID (groups logs by session)
        feedback_id: Unique feedback ID (for debugging specific feedback)
        log_level: Logging level (default: INFO)

    Returns:
        Configured logger instance

    Example:
        logger = get_step_logger("classification", session_id, feedback_id)
        logger.info("Starting NER", text_length=len(feedback_text))
    """
    # Create session-specific subdirectory
    log_base = _ensure_log_dir()
    session_dir = log_base / f"session_{session_id}"
    session_dir.mkdir(exist_ok=True)

    # ISO timestamp for sortability
    iso_timestamp = datetime.now(timezone.utc).isoformat().replace(":", "-")

    # Log filename: step_<step_name>_<feedback_id>_<timestamp>.log
    log_file = session_dir / f"{step_name}_{feedback_id}_{iso_timestamp}.log"

    # Create logger
    logger = logging.getLogger(f"feedback_loop.{step_name}.{feedback_id}")
    logger.setLevel(log_level)

    # Prevent duplicate handlers
    if logger.handlers:
        return logger

    # File handler (JSON format for machine-readability)
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(JSONFormatter(step_name, session_id, feedback_id))
    logger.addHandler(file_handler)

    # Console handler (human-readable)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(
        logging.Formatter(
            f"[{step_name}] %(levelname)s: %(message)s"
        )
    )
    logger.addHandler(console_handler)

    return logger


class JSONFormatter(logging.Formatter):
    """Format log records as JSON for structured logging."""

    def __init__(self, step_name: str, session_id: str, feedback_id: str):
        super().__init__()
        self.step_name = step_name
        self.session_id = session_id
        self.feedback_id = feedback_id

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "step": self.step_name,
            "session_id": self.session_id,
            "feedback_id": self.feedback_id,
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
        }

        # Add any extra fields from the log call
        if hasattr(record, "__dict__"):
            for key, value in record.__dict__.items():
                if not key.startswith("_") and key not in {
                    "name", "msg", "args", "created", "filename", "funcName",
                    "levelname", "levelno", "lineno", "module", "msecs",
                    "message", "pathname", "process", "processName", "relativeCreated",
                    "thread", "threadName", "exc_info", "exc_text", "stack_info"
                }:
                    log_data[key] = value

        return json.dumps(log_data, default=str)


# Step names for pipeline stages
STEP_NAMES = {
    "classification": "step_1_classification",
    "enrichment": "step_2_enrichment",
    "router": "step_3_router",
    "adjudication": "step_4_adjudication",
}


def get_pipeline_logger(
    step_key: str,  # "classification", "enrichment", etc.
    session_id: str,
    feedback_id: str,
) -> logging.Logger:
    """Get logger with standardized step naming."""
    step_name = STEP_NAMES.get(step_key, step_key)
    return get_step_logger(step_name, session_id, feedback_id)
