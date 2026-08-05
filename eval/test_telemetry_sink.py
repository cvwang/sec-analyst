"""Unit test suite for BigQuery Telemetry Sink, CostTracker, and orchestrator observability integration."""

import pytest
from unittest.mock import MagicMock, patch
from agent.observability.cost_tracker import CostTracker, CostBreakdown
from agent.observability.telemetry_sink import BigQueryTelemetrySink, TelemetryEvent
from agent.orchestrator import RootOrchestrator


def test_cost_tracker_gemini_pro_calculation():
    """Evaluates 75% context caching savings and itemized pricing for Gemini 2.5 Pro."""
    # 100k input tokens, 20k output tokens, 80k cached tokens
    cost = CostTracker.calculate_cost(
        model_name="gemini-2.5-pro",
        input_tokens=100_000,
        output_tokens=20_000,
        cached_tokens=80_000,
    )

    # Standard input rate: $1.25 / 1M = $0.00000125 -> 100,000 * 1.25/1M = $0.125
    assert cost.standard_input_cost_usd == pytest.approx(0.125, abs=1e-5)
    # Cached input rate: $0.3125 / 1M = $0.0000003125 -> 80,000 * 0.3125/1M = $0.025
    assert cost.cached_input_cost_usd == pytest.approx(0.025, abs=1e-5)
    # Output rate: $5.00 / 1M = $0.000005 -> 20,000 * 5.00/1M = $0.10
    assert cost.output_cost_usd == pytest.approx(0.10, abs=1e-5)

    # Total cost = 0.125 + 0.025 + 0.10 = $0.25
    assert cost.total_cost_usd == pytest.approx(0.25, abs=1e-5)
    # Savings = 80,000 * (1.25 - 0.3125)/1M = 80,000 * 0.9375/1M = $0.075 (75% savings!)
    assert cost.cached_savings_usd == pytest.approx(0.075, abs=1e-5)


def test_cost_tracker_gemini_flash_calculation():
    """Evaluates pricing calculations for Gemini Flash models."""
    cost = CostTracker.calculate_cost(
        model_name="gemini-3.5-flash",
        input_tokens=1_000_000,
        output_tokens=1_000_000,
        cached_tokens=1_000_000,
    )

    assert cost.standard_input_cost_usd == pytest.approx(0.075, abs=1e-5)
    assert cost.cached_input_cost_usd == pytest.approx(0.01875, abs=1e-5)
    assert cost.output_cost_usd == pytest.approx(0.30, abs=1e-5)
    assert cost.cached_savings_usd == pytest.approx(0.05625, abs=1e-5)
    assert cost.is_pricing_known is True


def test_cost_tracker_unrecognized_model_flagging():
    """Evaluates that unrecognized models set cost to 0.0, is_pricing_known=False, and log an explicit warning."""
    cost = CostTracker.calculate_cost(
        model_name="unknown-custom-model-v1",
        input_tokens=1_000_000,
        output_tokens=500_000,
    )

    assert cost.is_pricing_known is False
    assert cost.total_cost_usd == 0.0
    assert cost.warning is not None
    assert "UNRECOGNIZED_MODEL_PRICING" in cost.warning



def test_telemetry_event_schema():
    """Evaluates TelemetryEvent model serialization and validation."""
    event = TelemetryEvent(
        trace_id="test-trace-123",
        session_id="session-abc",
        model_name="gemini-2.5-pro",
        input_tokens=500,
        output_tokens=200,
        cached_tokens=100,
        latency_ms=1250.5,
        estimated_cost_usd=0.0025,
        cached_savings_usd=0.0005,
        status="SUCCESS",
        metadata={"ticker": "AAPL"},
    )

    assert event.trace_id == "test-trace-123"
    assert event.session_id == "session-abc"
    assert event.latency_ms == 1250.5
    assert event.status == "SUCCESS"
    assert event.metadata["ticker"] == "AAPL"


def test_bigquery_telemetry_sink_offline_fallback():
    """Evaluates that BigQueryTelemetrySink handles missing GCP client / offline fallback without crashing."""
    sink = BigQueryTelemetrySink(project_id="mock-project")
    sink.client = None  # Simulate offline / unauthenticated client

    event = TelemetryEvent(
        trace_id="test-offline-1",
        session_id="sess-offline",
        model_name="gemini-2.5-pro",
        input_tokens=100,
        output_tokens=50,
        latency_ms=300.0,
        estimated_cost_usd=0.0001,
        status="SUCCESS",
    )

    # Calling log_event should log via structured logger fallback and return False without throwing
    success = sink.log_event(event)
    assert success is False


@patch("agent.orchestrator.FinancialAnalystAgent.run_analysis")
def test_root_orchestrator_telemetry_output(mock_run):
    """Evaluates that RootOrchestrator includes telemetry metadata in dispatch responses."""
    mock_run.return_value = {
        "is_success": True,
        "narrative": "Revenue grew by 10%.",
        "model_used": "Vertex AI (gemini-2.5-pro)",
        "telemetry": {
            "trace_id": "trace-999",
            "latency_ms": 450.0,
            "cost_usd": 0.0012,
            "cached_savings_usd": 0.0003,
        },
    }

    orchestrator = RootOrchestrator()
    res = orchestrator.dispatch_query(prompt="Analyze AAPL Revenue", session_id="test_sess")

    assert res["is_success"] is True
    assert "telemetry" in res
    assert res["telemetry"]["trace_id"] == "trace-999"
    assert res["telemetry"]["cost_usd"] == 0.0012
