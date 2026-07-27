"""ADK Root Orchestrator and Financial Analyst Agent supervising financial variance analysis with live Vertex AI model calls."""

import os
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from google import genai
from agent.config import settings
from agent.constitution import SYSTEM_CONSTITUTION
from agent.tools.calculation_engine import calculate_financial_variance, VarianceRequest, VarianceResult
from agent.tools.sec_retriever import fetch_sec_10k_context, SECContextRequest, SECContextResult
from agent.observability.logging_config import log_tool_execution
from agent.observability.tracer import trace_span


class ExportReportRequest(BaseModel):
    """Input request for exporting analyzed financial variance reports."""

    ticker: str = Field(..., description="Ticker symbol.")
    destination_gcs_uri: str = Field(..., description="GCS bucket destination URI.")
    report_content: str = Field(..., description="Final financial report markdown text.")


class ExportReportResult(BaseModel):
    """Result of export report execution."""

    is_success: bool
    requires_human_approval: bool = False
    status: str
    message: str


def export_financial_report(request: ExportReportRequest, human_approved: bool = False) -> ExportReportResult:
    """External report export tool with Human-In-The-Loop approval stop guardrail."""
    log_tool_execution(
        tool_name="export_financial_report",
        stage="intent",
        payload=request.model_dump(),
    )

    if not human_approved:
        result = ExportReportResult(
            is_success=False,
            requires_human_approval=True,
            status="PENDING_HUMAN_APPROVAL",
            message=f"Export request to '{request.destination_gcs_uri}' paused. Human confirmation required before writing external data.",
        )
        log_tool_execution(
            tool_name="export_financial_report",
            stage="outcome",
            payload=result.model_dump(),
            status="PENDING_HUMAN_APPROVAL",
        )
        return result

    result = ExportReportResult(
        is_success=True,
        requires_human_approval=False,
        status="EXPORTED",
        message=f"Financial report for {request.ticker} successfully exported to {request.destination_gcs_uri}.",
    )
    log_tool_execution(
        tool_name="export_financial_report",
        stage="outcome",
        payload=result.model_dump(),
        status="SUCCESS",
    )
    return result


class FinancialAnalystAgent:
    """Financial Analyst Agent using Gemini 2.5 Pro on Vertex AI for reasoning and narrative synthesis."""

    def __init__(self):
        self.model_name = settings.reasoning_model
        self.constitution = SYSTEM_CONSTITUTION
        self.client = self._init_genai_client()

    def _init_genai_client(self) -> Optional[genai.Client]:
        """Initializes GenAI client with Vertex AI or API Key fallback."""
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            try:
                return genai.Client(api_key=api_key)
            except Exception:
                pass

        try:
            return genai.Client(
                vertexai=True,
                project=settings.gcp_project_id,
                location=settings.gcp_region,
            )
        except Exception:
            return None

    @trace_span("FinancialAnalystAgent.run_analysis")
    def run_analysis(
        self,
        ticker: str,
        current_year: int,
        prior_year: int,
        metric_name: str,
    ) -> Dict[str, Any]:
        """Executes full variance analysis workflow and calls Vertex AI Gemini model to synthesize narrative.

        Args:
            ticker: Ticker symbol (e.g., AAPL).
            current_year: Current fiscal year (e.g., 2023).
            prior_year: Prior fiscal year (e.g., 2022).
            metric_name: Financial metric to analyze ('Revenue', 'Operating Income', 'Net Income').

        Returns:
            Dictionary containing calculation results, grounding context, and live Vertex AI narrative.
        """
        # Step 1: Fetch SEC Context for Current Year
        log_tool_execution("fetch_sec_10k_context", "intent", {"ticker": ticker, "fiscal_year": current_year})
        current_ctx = fetch_sec_10k_context(SECContextRequest(ticker=ticker, fiscal_year=current_year))
        log_tool_execution("fetch_sec_10k_context", "outcome", current_ctx.model_dump(), status="SUCCESS" if current_ctx.is_success else "ERROR")

        # Step 2: Fetch SEC Context for Prior Year
        log_tool_execution("fetch_sec_10k_context", "intent", {"ticker": ticker, "fiscal_year": prior_year})
        prior_ctx = fetch_sec_10k_context(SECContextRequest(ticker=ticker, fiscal_year=prior_year))
        log_tool_execution("fetch_sec_10k_context", "outcome", prior_ctx.model_dump(), status="SUCCESS" if prior_ctx.is_success else "ERROR")

        if not current_ctx.is_success or not prior_ctx.is_success:
            error_msg = f"Failed to retrieve 10-K data for {ticker}. Current year error: {current_ctx.error}. Prior year error: {prior_ctx.error}."
            return {"is_success": False, "error": error_msg}

        # Extract metric values dynamically
        metric_attr = metric_name.lower().replace(" ", "_")
        curr_val = getattr(current_ctx, metric_attr, None)
        prior_val = getattr(prior_ctx, metric_attr, None)

        # Step 3: Execute Deterministic Variance Calculation
        calc_req = VarianceRequest(
            ticker=ticker,
            metric_name=metric_name,
            current_period_value=curr_val if curr_val is not None else 0.0,
            prior_period_value=prior_val if prior_val is not None else 0.0,
        )
        log_tool_execution("calculate_financial_variance", "intent", calc_req.model_dump())
        calc_res = calculate_financial_variance(calc_req)
        log_tool_execution("calculate_financial_variance", "outcome", calc_res.model_dump(), status="SUCCESS" if calc_res.is_success else "ERROR")

        # Step 4: LIVE VERTEX AI GEMINI LLM INVOCATION
        prompt = f"""
{SYSTEM_CONSTITUTION}

USER REQUEST: Analyze the period-over-period financial variance for {ticker} ({metric_name}) between FY{prior_year} and FY{current_year}.

DETERMINISTIC CALCULATION TOOL OUTPUT:
- Ticker: {ticker}
- Metric: {metric_name}
- FY{prior_year} Value: {calc_res.prior_period_value} USD (Millions)
- FY{current_year} Value: {calc_res.current_period_value} USD (Millions)
- Absolute Variance: {calc_res.absolute_change:+} USD (Millions)
- Percentage Variance: {calc_res.percentage_change:+}%
- Direction: {calc_res.direction}

SEC 10-K FILING EXCERPT:
"{current_ctx.excerpt}"

INSTRUCTIONS:
Synthesize an Executive Summary report following the System Constitution. Include:
1. Executive Summary
2. Period-over-Period Variance Breakdown (matching tool output exactly)
3. MD&A Grounding Insights
"""
        narrative = ""
        model_used = "deterministic-fallback"

        if self.client:
            models_to_try = [self.model_name, "gemini-2.0-flash", "gemini-1.5-pro"]
            for model_id in models_to_try:
                try:
                    log_tool_execution("vertex_ai_generate_content", "intent", {"model": model_id, "ticker": ticker})
                    response = self.client.models.generate_content(
                        model=model_id,
                        contents=prompt,
                    )
                    narrative = response.text.strip()
                    model_used = f"Vertex AI ({model_id})"
                    log_tool_execution("vertex_ai_generate_content", "outcome", {"model": model_id, "status": "SUCCESS"})
                    break
                except Exception as err:
                    log_tool_execution("vertex_ai_generate_content", "outcome", {"model": model_id, "error": str(err)}, status="ERROR")

        if not narrative:
            # Deterministic fallback if API call fails
            narrative = (
                f"### Financial Variance Analysis for {ticker} ({metric_name})\n"
                f"- **Fiscal Year {prior_year}**: {calc_res.prior_period_value} USD (Millions)\n"
                f"- **Fiscal Year {current_year}**: {calc_res.current_period_value} USD (Millions)\n"
                f"- **Absolute Variance**: {calc_res.absolute_change:+} USD (Millions)\n"
                f"- **Percentage Variance**: {calc_res.percentage_change:+}% ({calc_res.direction})\n\n"
                f"**10-K Grounding Excerpt ({current_year})**: {current_ctx.excerpt}\n"
            )

        return {
            "is_success": True,
            "ticker": ticker,
            "metric_name": metric_name,
            "variance_result": calc_res,
            "current_context": current_ctx,
            "prior_context": prior_ctx,
            "narrative": narrative,
            "model_used": model_used,
        }


class RootOrchestrator:
    """ADK Root Orchestrator supervising FinancialAnalystAgent and model routing."""

    def __init__(self):
        self.reasoning_model = settings.reasoning_model
        self.tool_model = settings.tool_model
        self.analyst_agent = FinancialAnalystAgent()

    @trace_span("RootOrchestrator.dispatch")
    def dispatch_query(
        self,
        query_type: str,
        ticker: str,
        current_year: int,
        prior_year: int,
        metric_name: str,
        export_gcs_uri: Optional[str] = None,
        human_approved_export: bool = False,
    ) -> Dict[str, Any]:
        """Routes user queries to sub-agents and tool callers with live model routing."""
        analysis_res = self.analyst_agent.run_analysis(
            ticker=ticker,
            current_year=current_year,
            prior_year=prior_year,
            metric_name=metric_name,
        )

        if not analysis_res.get("is_success"):
            return analysis_res

        if export_gcs_uri:
            export_req = ExportReportRequest(
                ticker=ticker,
                destination_gcs_uri=export_gcs_uri,
                report_content=analysis_res["narrative"],
            )
            export_res = export_financial_report(export_req, human_approved=human_approved_export)
            analysis_res["export_status"] = export_res.model_dump()

        return analysis_res
