"""Structured JSON logging configuration capturing tool intent and outcome."""

import logging
import sys
from typing import Any, Dict, Optional
from pythonjsonlogger import json as jsonlogger
from agent.config import settings


class StructuredJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON log formatter for serializing log records."""

    def format(self, record: logging.LogRecord) -> str:
        return super().format(record)


def get_logger(name: str = "sec_edgar_agent") -> logging.Logger:
    """Configures and returns a structured JSON logger for agent actions and tool calls."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
        handler = logging.StreamHandler(sys.stdout)
        formatter = StructuredJsonFormatter(
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
    log_data = {
        "event_type": f"tool_{stage}",
        "tool_name": tool_name,
        "stage": stage,
        "status": status,
        "payload": payload,
    }
    if error:
        log_data["error"] = error

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
