"""Configuration settings for the SEC EDGAR Agent system."""

import os
from pathlib import Path
from pydantic import BaseModel, Field

# Load .env file if present
_env_file = Path(__file__).resolve().parent.parent / ".env"
if _env_file.exists():
    with open(_env_file, "r") as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ[_k.strip()] = _v.strip()


class Settings(BaseModel):
    """Application runtime configuration settings."""

    gcp_project_id: str = Field(
        default_factory=lambda: os.getenv("GCP_PROJECT_ID", "sec-analyst"),
        description="GCP Project ID for Vertex AI and GCP resources",
    )
    gcp_region: str = Field(
        default_factory=lambda: os.getenv("GCP_REGION", "us-central1"),
        description="GCP Region for Vertex AI API calls",
    )
    reasoning_model: str = Field(
        default_factory=lambda: os.getenv("REASONING_MODEL", "gemini-2.5-pro"),
        description="Gemini model for complex financial reasoning and synthesis",
    )
    tool_model: str = Field(
        default_factory=lambda: os.getenv("TOOL_MODEL", "gemini-2.5-flash"),
        description="Gemini model for tool execution, lookups, and evaluation",
    )
    log_level: str = Field(
        default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"),
        description="Logging verbosity level",
    )
    model_armor_enabled: bool = Field(
        default_factory=lambda: os.getenv("MODEL_ARMOR_ENABLED", "true").lower() in ("true", "1", "yes"),
        description="Toggle Model Armor input/output screening guardrails",
    )
    model_armor_template_id: str = Field(
        default_factory=lambda: os.getenv("MODEL_ARMOR_TEMPLATE_ID", "sec-analyst-model-armor-template"),
        description="GCP Model Armor template resource ID",
    )
    model_armor_location: str = Field(
        default_factory=lambda: os.getenv("MODEL_ARMOR_LOCATION", os.getenv("GCP_REGION", "us-central1")),
        description="GCP location region for Model Armor template",
    )
    model_armor_fail_open: bool = Field(
        default_factory=lambda: os.getenv("MODEL_ARMOR_FAIL_OPEN", "false").lower() in ("true", "1", "yes"),
        description="Outage policy: True to allow requests if Model Armor API errors/times out, False to fail-closed (default: False)",
    )


settings = Settings()
