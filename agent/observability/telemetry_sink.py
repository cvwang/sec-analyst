"""BigQuery Telemetry Sink for streaming observability events and LLM cost metrics to GCP BigQuery."""

from datetime import datetime, timezone
import json
import logging
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from google.cloud import bigquery
from google.api_core import exceptions as gcp_exceptions

from agent.config import settings
from agent.observability.logging_config import structured_logger
from agent.guardrails.pii_scrubber import PIIScrubber

logger = logging.getLogger(__name__)


class TelemetryEvent(BaseModel):
    """Structured telemetry record written to BigQuery telemetry sink."""

    trace_id: str = Field(..., description="Unique trace or request correlation ID.")
    session_id: str = Field("default_session", description="Analyst session identifier.")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC event timestamp.",
    )
    event_type: str = Field("query_execution", description="Telemetry event type.")
    model_name: str = Field(..., description="Gemini model invoked.")
    input_tokens: int = Field(0, description="Input prompt tokens.")
    output_tokens: int = Field(0, description="Output response tokens.")
    cached_tokens: int = Field(0, description="Tokens served from Vertex AI Context Cache.")
    latency_ms: float = Field(0.0, description="Total execution latency in milliseconds.")
    ttft_ms: Optional[float] = Field(None, description="Time to First Token latency in milliseconds.")
    estimated_cost_usd: float = Field(0.0, description="Estimated total execution cost in USD.")
    cached_savings_usd: float = Field(0.0, description="Net cost savings from context caching in USD.")
    tool_calls_count: int = Field(0, description="Number of agent tool calls executed.")
    status: str = Field("SUCCESS", description="Execution status (SUCCESS, ERROR, BLOCKED).")
    error: Optional[str] = Field(None, description="Error detail if status is ERROR.")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional context metadata.")


# Schema definition matching BigQuery telemetry table
TELEMETRY_TABLE_SCHEMA = [
    bigquery.SchemaField("trace_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("session_id", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("timestamp", "TIMESTAMP", mode="REQUIRED"),
    bigquery.SchemaField("event_type", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("model_name", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("input_tokens", "INTEGER", mode="NULLABLE"),
    bigquery.SchemaField("output_tokens", "INTEGER", mode="NULLABLE"),
    bigquery.SchemaField("cached_tokens", "INTEGER", mode="NULLABLE"),
    bigquery.SchemaField("latency_ms", "FLOAT", mode="NULLABLE"),
    bigquery.SchemaField("ttft_ms", "FLOAT", mode="NULLABLE"),
    bigquery.SchemaField("estimated_cost_usd", "FLOAT", mode="NULLABLE"),
    bigquery.SchemaField("cached_savings_usd", "FLOAT", mode="NULLABLE"),
    bigquery.SchemaField("tool_calls_count", "INTEGER", mode="NULLABLE"),
    bigquery.SchemaField("status", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("error", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("metadata", "JSON", mode="NULLABLE"),
]


class BigQueryTelemetrySink:
    """BigQuery Telemetry Sink for streaming agent execution metrics and cost analytics."""

    def __init__(
        self,
        project_id: Optional[str] = None,
        dataset_id: Optional[str] = None,
        table_id: Optional[str] = None,
    ):
        self.project_id = project_id or settings.gcp_project_id
        self.dataset_id = dataset_id or settings.bigquery_telemetry_dataset
        self.table_id = table_id or settings.bigquery_telemetry_table
        self.client: Optional[bigquery.Client] = None
        self._table_initialized = False

        if settings.telemetry_enabled:
            try:
                self.client = bigquery.Client(project=self.project_id)
            except Exception as e:
                logger.warning(
                    f"BigQuery client initialization failed: {e}. Falling back to structured logger."
                )
                self.client = None

    def ensure_dataset_and_table(self) -> bool:
        """Ensures telemetry dataset and table exist in GCP BigQuery."""
        if not self.client or self._table_initialized:
            return self._table_initialized

        try:
            dataset_ref = bigquery.DatasetReference(self.project_id, self.dataset_id)
            try:
                self.client.get_dataset(dataset_ref)
            except gcp_exceptions.NotFound:
                dataset = bigquery.Dataset(dataset_ref)
                dataset.location = settings.gcp_region
                self.client.create_dataset(dataset, exists_ok=True)

            table_ref = dataset_ref.table(self.table_id)
            try:
                self.client.get_table(table_ref)
            except gcp_exceptions.NotFound:
                table = bigquery.Table(table_ref, schema=TELEMETRY_TABLE_SCHEMA)
                self.client.create_table(table, exists_ok=True)

            self._table_initialized = True
            return True
        except Exception as err:
            logger.warning(f"Unable to ensure BigQuery telemetry table ({self.dataset_id}.{self.table_id}): {err}")
            return False

    def log_event(self, event: TelemetryEvent) -> bool:
        """Streams a telemetry record to BigQuery or logs via structured JSON fallback."""
        if not settings.telemetry_enabled:
            return False

        # Scrub event PII fields before recording
        scrubbed_metadata = PIIScrubber.scrub_data(event.metadata) if event.metadata else {}
        scrubbed_error = PIIScrubber.scrub_text(event.error) if event.error else None

        row = {
            "trace_id": event.trace_id,
            "session_id": event.session_id,
            "timestamp": event.timestamp,
            "event_type": event.event_type,
            "model_name": event.model_name,
            "input_tokens": event.input_tokens,
            "output_tokens": event.output_tokens,
            "cached_tokens": event.cached_tokens,
            "latency_ms": round(event.latency_ms, 2),
            "ttft_ms": round(event.ttft_ms, 2) if event.ttft_ms is not None else None,
            "estimated_cost_usd": round(event.estimated_cost_usd, 6),
            "cached_savings_usd": round(event.cached_savings_usd, 6),
            "tool_calls_count": event.tool_calls_count,
            "status": event.status,
            "error": scrubbed_error,
            "metadata": json.dumps(scrubbed_metadata) if scrubbed_metadata else None,
        }

        # Structured logger is always invoked for log retention
        structured_logger.info(
            f"TELEMETRY_EVENT: [{event.event_type}] model={event.model_name} latency={event.latency_ms:.1f}ms cost=${event.estimated_cost_usd:.6f}",
            extra={"telemetry": row},
        )

        if not self.client:
            return False

        try:
            self.ensure_dataset_and_table()
            table_ref = f"{self.project_id}.{self.dataset_id}.{self.table_id}"
            errors = self.client.insert_rows_json(table_ref, [row])
            if errors:
                logger.error(f"BigQuery telemetry insert errors: {errors}")
                return False
            return True
        except Exception as err:
            logger.warning(f"BigQuery telemetry streaming insert failed: {err}")
            return False
