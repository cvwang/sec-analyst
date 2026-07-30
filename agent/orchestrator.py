"""ADK Root Orchestrator and Financial Analyst Agent supervising financial variance, peer comparison, and thematic tracking with Hybrid Search RAG."""

import os
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from google import genai
from agent.config import settings
from agent.constitution import SYSTEM_CONSTITUTION
from agent.tools.calculation_engine import calculate_financial_variance, VarianceRequest
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
            except Exception as e:
                log_tool_execution("init_genai_client", "outcome", {"error_api_key": str(e)}, status="ERROR")

        try:
            return genai.Client(
                vertexai=True,
                project=settings.gcp_project_id,
                location=settings.gcp_region,
            )
        except Exception as e:
            log_tool_execution("init_genai_client", "outcome", {"error_vertex": str(e)}, status="ERROR")
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
        user_prompt: Optional[str] = None,
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

        abs_str = f"{calc_res.absolute_change:+}" if calc_res.absolute_change is not None else "N/A"
        pct_str = f"{calc_res.percentage_change:+}%" if calc_res.percentage_change is not None else "N/A"
        user_q_str = f"EXPACT USER PROMPT: {user_prompt}" if user_prompt else f"USER REQUEST: Analyze financial data for {ticker} ({metric_name}) between FY{prior_year} and FY{current_year}."

        prompt = f"""
{SYSTEM_CONSTITUTION}
{history_context}
{user_q_str}

DETERMINISTIC CALCULATION TOOL OUTPUT:
- Ticker: {ticker}
- Metric: {metric_name}
- FY{prior_year} Value: {calc_res.prior_period_value} USD (Millions)
- FY{current_year} Value: {calc_res.current_period_value} USD (Millions)
- Absolute Variance: {abs_str} USD (Millions)
- Percentage Variance: {pct_str}
- Direction: {calc_res.direction}

HYBRID SEARCH RAG GROUNDING CONTEXT (BigQuery + SEC 10-K Corpus):
{hybrid_rag_result.formatted_context_block}

INSTRUCTIONS:
Directly answer the user prompt above using the grounded context and tool outputs.
1. DO NOT include any introductory pleasantries or filler preamble (e.g., NEVER write "Of course", "Here is the", "Certainly", or "Based on the data"). Jump directly into your answer.
2. Select ONLY the relevant metrics and fiscal years needed to answer the user's specific request. Do NOT dump unnecessary prior-period comparison tables or unrequested metric breakdowns unless the user explicitly requested a multi-year comparison or growth analysis.
"""
        narrative = ""
        model_used = "deterministic-fallback"

        if self.client:
            models_to_try = [self.model_name, settings.tool_model]
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
            return {
                "is_success": False,
                "error": "Vertex AI Gemini model execution failed. Please verify GCP ADC authentication (`gcloud auth application-default login`).",
                "narrative": "⚠️ Unable to generate dynamic LLM response. Please run `gcloud auth application-default login` to re-authenticate with Google Cloud.",
                "ticker": ticker,
                "query_type": query_type,
                "metric_name": metric_name,
                "variance_result": calc_res,
                "hybrid_search_result": hybrid_rag_result,
                "citations": hybrid_rag_result.grounded_citations if hybrid_rag_result else [],
                "model_used": "failed-auth",
            }

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

    def parse_natural_language_intent(self, prompt: str, session_id: str = "default_session") -> Dict[str, Any]:
        """Uses Gemini 3.5 Flash (tool_model) with regex heuristic fallback to parse freeform user chat prompts into structured entities."""
        # 1. Attempt LLM Intent Parsing with tool_model (Gemini 3.5 Flash)
        if self.analyst_agent and self.analyst_agent.client:
            try:
                log_tool_execution("intent_classification_tool_model", "intent", {"model": self.tool_model, "prompt": prompt})
                intent_prompt = f"""
Extract financial query intent as JSON with keys: query_type, primary_ticker, secondary_tickers, current_year, prior_year, requested_years, metric_name.
Allowed query_type values: "variance_analysis", "peer_comparison", "thematic_tracking", "financial_summary".
Allowed metric_name values: "Revenue", "Operating Income", "Net Income".

User Query: "{prompt}"
Return ONLY valid JSON matching this schema without markdown code blocks.
"""
                resp = self.analyst_agent.client.models.generate_content(
                    model=self.tool_model,
                    contents=intent_prompt,
                )
                import json
                cleaned_text = resp.text.strip().replace("```json", "").replace("```", "").strip()
                parsed_json = json.loads(cleaned_text)
                log_tool_execution("intent_classification_tool_model", "outcome", parsed_json, status="SUCCESS")
                return {
                    "query_type": parsed_json.get("query_type", "financial_summary"),
                    "ticker": parsed_json.get("primary_ticker", "AAPL").upper(),
                    "secondary_tickers": parsed_json.get("secondary_tickers", []),
                    "current_year": int(parsed_json.get("current_year", 2023)),
                    "prior_year": int(parsed_json.get("prior_year", 2022)),
                    "requested_years": [int(y) for y in parsed_json.get("requested_years", [])],
                    "metric_name": parsed_json.get("metric_name", "Revenue"),
                }
            except Exception as err:
                log_tool_execution("intent_classification_tool_model", "outcome", {"error": str(err)}, status="ERROR")

        # 2. Fallback Regex Heuristic Parsing
        prompt_upper = prompt.upper()

        # Known ticker mappings
        ticker_map = {
            "APPLE": "AAPL", "AAPL": "AAPL",
            "MICROSOFT": "MSFT", "MSFT": "MSFT",
            "NVIDIA": "NVDA", "NVDA": "NVDA",
            "GOOGLE": "GOOGL", "ALPHABET": "GOOGL", "GOOGL": "GOOGL",
            "AMAZON": "AMZN", "AMZN": "AMZN",
            "TESLA": "TSLA", "TSLA": "TSLA",
            "META": "META", "FACEBOOK": "META",
            "AMD": "AMD", "JPMORGAN": "JPM", "JPM": "JPM",
            "WALMART": "WMT", "WMT": "WMT"
        }

        found_tickers = []
        for word, symbol in ticker_map.items():
            if word in prompt_upper and symbol not in found_tickers:
                found_tickers.append(symbol)

        # Context-aware ticker fallback: inspect recent session history if prompt omits ticker
        primary_ticker = None
        if found_tickers:
            primary_ticker = found_tickers[0]
        else:
            history = self.session_store.get_session_history(session_id)
            for turn in reversed(history):
                meta = turn.get("metadata") if isinstance(turn, dict) else getattr(turn, "metadata", None)
                if meta and isinstance(meta, dict) and meta.get("ticker"):
                    primary_ticker = meta["ticker"].upper()
                    break

        primary_ticker = primary_ticker or "AAPL"
        secondary_tickers = found_tickers[1:] if len(found_tickers) > 1 else []

        # Metric parsing
        metric_name = "Revenue"
        if "OPERATING INCOME" in prompt_upper or "OPERATING MARGIN" in prompt_upper or "OPERATING PROFIT" in prompt_upper:
            metric_name = "Operating Income"
        elif "NET INCOME" in prompt_upper or "NET PROFIT" in prompt_upper or "EARNINGS" in prompt_upper:
            metric_name = "Net Income"
        else:
            # Check recent session history for metric if not explicitly mentioned
            history = self.session_store.get_session_history(session_id)
            for turn in reversed(history):
                meta = turn.get("metadata") if isinstance(turn, dict) else getattr(turn, "metadata", None)
                if meta and isinstance(meta, dict) and meta.get("metric"):
                    metric_name = meta["metric"]
                    break

        # Years parsing
        import re
        years_found = sorted([int(y) for y in re.findall(r'\b(202[0-9])\b', prompt_upper)])
        requested_years = []
        if len(years_found) >= 2:
            min_y, max_y = years_found[0], years_found[-1]
            requested_years = list(range(min_y, max_y + 1))
            current_year, prior_year = max_y, min_y
        elif len(years_found) == 1:
            requested_years = [years_found[0]]
            current_year, prior_year = years_found[0], years_found[0] - 1
        else:
            requested_years = [2023, 2022]
            current_year, prior_year = 2023, 2022

        # Query type classification
        if secondary_tickers or "COMPARE" in prompt_upper or ("VS" in prompt_upper and len(found_tickers) > 1):
            query_type = "peer_comparison"
        elif "RISK" in prompt_upper or "THEMATIC" in prompt_upper or "AI" in prompt_upper:
            query_type = "thematic_tracking"
        elif "VARIANCE" in prompt_upper or "GROWTH" in prompt_upper or "CHANGE" in prompt_upper or "VS" in prompt_upper or "INCREASE" in prompt_upper or "DECREASE" in prompt_upper:
            query_type = "variance_analysis"
        else:
            query_type = "financial_summary"

        return {
            "query_type": query_type,
            "ticker": primary_ticker,
            "secondary_tickers": secondary_tickers,
            "current_year": current_year,
            "prior_year": prior_year,
            "requested_years": requested_years,
            "metric_name": metric_name,
        }

    @trace_span("RootOrchestrator.dispatch")
    def dispatch_query(
        self,
        query_type: Optional[str] = None,
        ticker: Optional[str] = None,
        current_year: Optional[int] = None,
        prior_year: Optional[int] = None,
        metric_name: Optional[str] = None,
        prompt: Optional[str] = None,
        secondary_tickers: Optional[List[str]] = None,
        thematic_keyword: Optional[str] = None,
        session_id: str = "default_session",
        export_gcs_uri: Optional[str] = None,
        human_approved_export: bool = False,
    ) -> Dict[str, Any]:
        """Routes user queries to sub-agents, manages persistent session memory, and applies history compaction."""
        # 0. If freeform natural language prompt provided, parse intent automatically with session context
        requested_years = []
        if prompt and (not ticker or not current_year or not prior_year or not metric_name):
            parsed = self.parse_natural_language_intent(prompt, session_id=session_id)
            query_type = query_type or parsed["query_type"]
            ticker = ticker or parsed["ticker"]
            current_year = current_year or parsed["current_year"]
            prior_year = prior_year or parsed["prior_year"]
            metric_name = metric_name or parsed["metric_name"]
            secondary_tickers = secondary_tickers or parsed["secondary_tickers"]
            requested_years = parsed.get("requested_years", [])

        query_type = query_type or "variance_analysis"
        ticker = (ticker or "AAPL").upper()
        current_year = current_year or 2023
        prior_year = prior_year or 2022
        metric_name = metric_name or "Revenue"
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
                requested_years=requested_years,
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
            user_prompt=prompt,
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
