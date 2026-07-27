"""Pytest evaluation harness testing financial calculation accuracy, grounding faithfulness, PII scrubbing, and orchestration."""

import json
import os
import pytest
from agent.tools.calculation_engine import calculate_financial_variance, VarianceRequest
from agent.tools.sec_retriever import fetch_sec_10k_context, SECContextRequest
from agent.guardrails.pii_scrubber import PIIScrubber
from agent.orchestrator import RootOrchestrator, export_financial_report, ExportReportRequest

GOLDEN_DATASET_PATH = os.path.join(os.path.dirname(__file__), "golden_dataset.json")


def load_golden_dataset():
    with open(GOLDEN_DATASET_PATH, "r") as f:
        return json.load(f)


@pytest.mark.parametrize("case", load_golden_dataset())
def test_calculation_engine_golden_accuracy(case):
    """Evaluates 100% numerical accuracy for deterministic variance calculations against golden dataset."""
    request = VarianceRequest(
        ticker=case["ticker"],
        metric_name=case["metric_name"],
        current_period_value=case["current_value"],
        prior_period_value=case["prior_value"],
    )
    result = calculate_financial_variance(request)

    assert result.is_success is True
    assert result.ticker == case["ticker"]
    assert result.metric_name == case["metric_name"]
    assert result.absolute_change == case["expected_absolute_change"]
    assert result.percentage_change == case["expected_percentage_change"]
    assert result.direction == case["expected_direction"]


def test_calculation_engine_zero_prior_period():
    """Evaluates guided error recovery when prior period value is zero."""
    request = VarianceRequest(
        ticker="TEST",
        metric_name="Revenue",
        current_period_value=500.0,
        prior_period_value=0.0,
    )
    result = calculate_financial_variance(request)

    assert result.is_success is False
    assert result.percentage_change is None
    assert result.absolute_change == 500.0
    assert "Division by zero" in result.error
    assert result.recovery_instruction is not None


def test_calculation_engine_invalid_type_recovery():
    """Evaluates guided error recovery for non-numerical inputs."""
    request = VarianceRequest(
        ticker="TEST",
        metric_name="Revenue",
        current_period_value="INVALID_NUMBER",
        prior_period_value=100.0,
    )
    result = calculate_financial_variance(request)

    assert result.is_success is False
    assert "Cannot parse" in result.error
    assert "Ensure current_period_value is a valid numeric" in result.recovery_instruction


def test_pii_scrubber_redaction():
    """Evaluates PII scrubbing for SSNs, credit cards, emails, and API keys."""
    raw_text = "Contact john.doe@example.com with SSN 123-45-6789 or key AIzaSyA1234567890abcdefghijklmnopqrstuv."
    scrubbed = PIIScrubber.scrub_text(raw_text)

    assert "john.doe@example.com" not in scrubbed
    assert "123-45-6789" not in scrubbed
    assert "AIzaSyA1234567890abcdefghijklmnopqrstuv" not in scrubbed
    assert "[REDACTED_EMAIL]" in scrubbed
    assert "[REDACTED_SSN]" in scrubbed
    assert "[REDACTED_KEY]" in scrubbed


def test_human_in_the_loop_export_stop():
    """Evaluates that external exports require explicit human approval before execution."""
    req = ExportReportRequest(
        ticker="AAPL",
        destination_gcs_uri="gs://fde-sec-edgar-reports/aapl_2023.md",
        report_content="Sample report text",
    )
    # Without human approval
    unapproved_res = export_financial_report(req, human_approved=False)
    assert unapproved_res.is_success is False
    assert unapproved_res.requires_human_approval is True
    assert unapproved_res.status == "PENDING_HUMAN_APPROVAL"

    # With human approval
    approved_res = export_financial_report(req, human_approved=True)
    assert approved_res.is_success is True
    assert approved_res.status == "EXPORTED"


def test_root_orchestrator_end_to_end():
    """Evaluates ADK RootOrchestrator workflow and grounded narrative synthesis."""
    orchestrator = RootOrchestrator()
    response = orchestrator.dispatch_query(
        query_type="variance_analysis",
        ticker="AAPL",
        current_year=2023,
        prior_year=2022,
        metric_name="Revenue",
    )

    assert response["is_success"] is True
    assert response["ticker"] == "AAPL"
    assert response["variance_result"].absolute_change == -11043.0
    assert response["variance_result"].percentage_change == -2.8
    assert "AAPL" in response["narrative"]
    assert "macroeconomic" in response["narrative"].lower()
