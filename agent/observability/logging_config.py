"""Structured JSON logging configuration capturing tool intent and outcome with PII redaction."""

import logging
import sys
from typing import Any, Dict, Optional
from pythonjsonlogger import json as jsonlogger
from agent.guardrails.pii_scrubber import PIIScrubber
from agent.config import settings


class PIIFilterJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON log formatter that redacts PII before serializing log records."""

    def format(self, record: logging.LogRecord) -> str:
        # Scrub message string
        if isinstance(record.msg, str):
            record.msg = PIIScrubber.scrub_text(record.msg)
        
        # Scrub extra fields
        if hasattr(record, "intent") and record.intent:
            record.intent = PIIScrubber.scrub_data(record.intent)
        if hasattr(record, "outcome") and record.outcome:
            record.outcome = PIIScrubber.scrub_data(record.outcome)

        return super().format(record)


def get_logger(name: str = "sec_edgar_agent") -> logging.Logger:
    """Configures and returns a structured JSON logger for agent actions and tool calls."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
        handler = logging.StreamHandler(sys.stdout)
        formatter = PIIFilterJsonFormatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.propagate = False
    return logger


structured_logger = get_logger()


def log_tool_execution(
    tool_name: str,
    stage: str,  # "intent" or "outcome"
    payload: Dict[str, Any],
    status: str = "SUCCESS",
    error: Optional[str] = None,
) -> None:
    """Logs tool execution lifecycle stages ('intent' before execution, 'outcome' after).

    Args:
        tool_name: Naming identifier of executed tool.
        stage: 'intent' or 'outcome'.
        payload: Input arguments (for intent) or result payload (for outcome).
        status: Execution status ('SUCCESS', 'ERROR', 'PENDING_APPROVAL').
        error: Error message if status is ERROR.
    """
    scrubbed_payload = PIIScrubber.scrub_data(payload)
    log_data = {
        "event_type": f"tool_{stage}",
        "tool_name": tool_name,
        "stage": stage,
        "status": status,
        "payload": scrubbed_payload,
    }
    if error:
        log_data["error"] = PIIScrubber.scrub_text(error)

    if stage == "intent":
        structured_logger.info(
            f"INTENT: Invoking tool '{tool_name}'",
            extra={"intent": log_data},
        )
    else:
        structured_logger.info(
            f"OUTCOME: Tool '{tool_name}' execution completed with status '{status}'",
            extra={"outcome": log_data},
        )
