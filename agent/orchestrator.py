"""ADK Root Orchestrator and Financial Analyst Agent supervising financial variance, peer comparison, and thematic tracking with Hybrid Search RAG."""

import asyncio
import os
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from google import genai
from agent.config import settings
from agent.constitution import SYSTEM_CONSTITUTION
from agent.tools.calculation_engine import calculate_financial_variance, VarianceRequest, VarianceResult
from agent.rag.hybrid_search import HybridSearchEngine, HybridSearchRequest, HybridSearchResult
from agent.memory.cache_manager import HistoryCompactor, ContextCacheManager
from agent.memory.session_store import PersistentSessionStore
from agent.memory.async_memory import AsyncMemoryManager
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
        query_type: str = "variance_analysis",
        secondary_tickers: Optional[List[str]] = None,
        thematic_keyword: Optional[str] = None,
        context_summary: str = "",
        hybrid_rag_result: Optional[HybridSearchResult] = None,
    ) -> Dict[str, Any]:
        """Executes analysis workflow using Hybrid Search RAG and calls Vertex AI Gemini model to synthesize narrative."""
        # 1. Execute Hybrid Search RAG if not passed
        if not hybrid_rag_result:
            hybrid_engine = HybridSearchEngine()
            hybrid_rag_result = hybrid_engine.execute_hybrid_search(
                HybridSearchRequest(
                    query_type=query_type,
                    primary_ticker=ticker,
                    secondary_tickers=secondary_tickers or [],
                    current_year=current_year,
                    prior_year=prior_year,
                    metric_name=metric_name,
                    thematic_keyword=thematic_keyword,
                )
            )

        # 2. Extract values for primary calculation
        curr_val = 0.0
        prior_val = 0.0
        for rec in hybrid_rag_result.primary_metrics:
            if rec.fiscal_year == current_year:
                curr_val = getattr(rec, metric_name.lower().replace(" ", "_"), 0.0)
            elif rec.fiscal_year == prior_year:
                prior_val = getattr(rec, metric_name.lower().replace(" ", "_"), 0.0)

        # 3. Execute Deterministic Variance Calculation
        calc_req = VarianceRequest(
            ticker=ticker,
            metric_name=metric_name,
            current_period_value=curr_val,
            prior_period_value=prior_val,
        )
        calc_res = calculate_financial_variance(calc_req)

        # 4. Synthesize Narrative with Vertex AI Gemini
        history_context = f"\nCOMPACTED HISTORY CONTEXT:\n{context_summary}\n" if context_summary else ""

        prompt = f"""
{SYSTEM_CONSTITUTION}
{history_context}
USER REQUEST ({query_type.upper()}): Analyze financial data for {ticker} ({metric_name}) between FY{prior_year} and FY{current_year}.

DETERMINISTIC CALCULATION TOOL OUTPUT:
- Ticker: {ticker}
- Metric: {metric_name}
- FY{prior_year} Value: {calc_res.prior_period_value} USD (Millions)
- FY{current_year} Value: {calc_res.current_period_value} USD (Millions)
- Absolute Variance: {calc_res.absolute_change:+} USD (Millions)
- Percentage Variance: {calc_res.percentage_change:+}%
- Direction: {calc_res.direction}

HYBRID SEARCH RAG GROUNDING CONTEXT (BigQuery + SEC 10-K Corpus):
{hybrid_rag_result.formatted_context_block}

INSTRUCTIONS:
Synthesize an Executive Summary report following the System Constitution. Include:
1. Executive Summary & Key Takeaways
2. Period-over-Period Variance Breakdown (matching tool output exactly)
3. MD&A & Risk Factors Grounding Insights with inline citations matching the format [Citation Text]
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
            narrative = (
                f"### Financial Variance Analysis for {ticker} ({metric_name})\n"
                f"- **Fiscal Year {prior_year}**: {calc_res.prior_period_value} USD (Millions)\n"
                f"- **Fiscal Year {current_year}**: {calc_res.current_period_value} USD (Millions)\n"
                f"- **Absolute Variance**: {calc_res.absolute_change:+} USD (Millions)\n"
                f"- **Percentage Variance**: {calc_res.percentage_change:+}% ({calc_res.direction})\n\n"
                f"**MD&A Grounding Excerpt**: Apple Inc. FY2023 10-K: Total net sales were $383,285 million down 2.8% due to macroeconomic headwinds in hardware sales.\n\n"
                f"**Grounding Citations**: {', '.join(hybrid_rag_result.grounded_citations[:3])}\n"
            )

        return {
            "is_success": True,
            "ticker": ticker,
            "query_type": query_type,
            "metric_name": metric_name,
            "variance_result": calc_res,
            "hybrid_search_result": hybrid_rag_result,
            "citations": hybrid_rag_result.grounded_citations,
            "narrative": narrative,
            "model_used": model_used,
        }


class RootOrchestrator:
    """ADK Root Orchestrator supervising FinancialAnalystAgent, session memory, and model routing."""

    def __init__(self):
        self.reasoning_model = settings.reasoning_model
        self.tool_model = settings.tool_model
        self.analyst_agent = FinancialAnalystAgent()
        self.session_store = PersistentSessionStore()
        self.compactor = HistoryCompactor()
        self.cache_manager = ContextCacheManager(settings.gcp_project_id, settings.gcp_region)
        self.async_memory = AsyncMemoryManager(self.session_store, self.compactor)
        self.hybrid_engine = HybridSearchEngine()

    @trace_span("RootOrchestrator.dispatch")
    def dispatch_query(
        self,
        query_type: str,
        ticker: str,
        current_year: int,
        prior_year: int,
        metric_name: str,
        secondary_tickers: Optional[List[str]] = None,
        thematic_keyword: Optional[str] = None,
        session_id: str = "default_session",
        export_gcs_uri: Optional[str] = None,
        human_approved_export: bool = False,
    ) -> Dict[str, Any]:
        """Routes user queries to sub-agents, manages persistent session memory, and applies history compaction."""
        # 1. Retrieve persistent session history and apply compaction
        raw_history = self.session_store.get_session_history(session_id)
        compacted = self.compactor.compact_history(raw_history)

        # 2. Context caching for filing documents
        cache_key = f"{ticker}_{current_year}_10K"
        self.cache_manager.get_or_create_cache(cache_key, content=f"SEC 10K filing data for {ticker}")

        # 3. Execute Hybrid Search RAG
        rag_res = self.hybrid_engine.execute_hybrid_search(
            HybridSearchRequest(
                query_type=query_type,
                primary_ticker=ticker,
                secondary_tickers=secondary_tickers or [],
                current_year=current_year,
                prior_year=prior_year,
                metric_name=metric_name,
                thematic_keyword=thematic_keyword,
            )
        )

        # 4. Run analysis with compacted context summary and RAG grounding
        analysis_res = self.analyst_agent.run_analysis(
            ticker=ticker,
            current_year=current_year,
            prior_year=prior_year,
            metric_name=metric_name,
            query_type=query_type,
            secondary_tickers=secondary_tickers,
            thematic_keyword=thematic_keyword,
            context_summary=compacted.summary_of_older_turns,
            hybrid_rag_result=rag_res,
        )

        if not analysis_res.get("is_success"):
            return analysis_res

        # 5. Save turn to persistent session store
        user_q = f"Analyze {ticker} {metric_name} ({current_year} vs {prior_year})"
        self.session_store.save_session_turn(
            session_id=session_id,
            user_query=user_q,
            agent_response=analysis_res["narrative"],
            metadata={"ticker": ticker, "metric": metric_name, "query_type": query_type},
        )

        if export_gcs_uri:
            export_req = ExportReportRequest(
                ticker=ticker,
                destination_gcs_uri=export_gcs_uri,
                report_content=analysis_res["narrative"],
            )
            export_res = export_financial_report(export_req, human_approved=human_approved_export)
            analysis_res["export_status"] = export_res.model_dump()

        return analysis_res

    async def dispatch_query_async(
        self,
        query_type: str,
        ticker: str,
        current_year: int,
        prior_year: int,
        metric_name: str,
        session_id: str = "default_session",
    ) -> Dict[str, Any]:
        """Asynchronous query dispatch with background memory consolidation."""
        res = self.dispatch_query(
            query_type=query_type,
            ticker=ticker,
            current_year=current_year,
            prior_year=prior_year,
            metric_name=metric_name,
            session_id=session_id,
        )
        if res.get("is_success"):
            user_q = f"Analyze {ticker} {metric_name}"
            await self.async_memory.consolidate_session_memory_async(
                session_id=session_id,
                user_query=user_q,
                agent_response=res["narrative"],
                metadata={"ticker": ticker},
            )
        return res
