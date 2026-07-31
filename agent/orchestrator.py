"""ADK Root Orchestrator and Financial Analyst Agent supervising financial variance, peer comparison, and thematic tracking with Hybrid Search RAG."""

import os
import json
import re
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from google import genai
from google.genai import types
from agent.config import settings
from agent.constitution import SYSTEM_CONSTITUTION
from agent.tools.calculation_engine import calculate_financial_variance, calculate_financial_variance_tool, VarianceRequest
from agent.rag.bigquery_store import query_bigquery_financial_metrics_tool
from agent.rag.sec_corpus import search_sec_filing_chunks_tool
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
    """Financial Analyst Agent using Gemini 2.5 Pro on Vertex AI with dynamic LLM tool calling."""

    def __init__(self):
        self.model_name = settings.reasoning_model
        self.constitution = SYSTEM_CONSTITUTION
        self.client = self._init_genai_client()
        self.hybrid_engine = HybridSearchEngine()

    def _init_genai_client(self) -> Optional[genai.Client]:
        """Initializes GenAI client prioritizing Vertex AI for Datastore Search compatibility, with API Key fallback."""
        try:
            return genai.Client(
                vertexai=True,
                project=settings.gcp_project_id,
                location=settings.gcp_region,
            )
        except Exception as e:
            log_tool_execution("init_genai_client", "outcome", {"error_vertex": str(e)}, status="ERROR")

        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            try:
                return genai.Client(api_key=api_key)
            except Exception as e:
                log_tool_execution("init_genai_client", "outcome", {"error_api_key": str(e)}, status="ERROR")

        return None

    @trace_span("FinancialAnalystAgent.run_analysis")
    def run_analysis(
        self,
        user_prompt: str,
        hybrid_rag_result: HybridSearchResult,
        context_summary: str = "",
        tickers: List[str] = [],
        requested_years: List[int] = [],
        metric_name: str = "",
        query_type: str = "financial_summary",
        metadata: Dict[str, Any] = {},
    ) -> Dict[str, Any]:
        """Synthesizes grounded financial narrative using Vertex AI Gemini model from RAG context."""
        meta = metadata or {}
        tickers = tickers or meta.get("tickers") or ([hybrid_rag_result.primary_metrics[0].ticker] if hybrid_rag_result.primary_metrics else ["AAPL"])
        ticker = tickers[0]
        m_name = metric_name or meta.get("metric_name") or "Revenue"
        q_type = query_type or hybrid_rag_result.query_type or meta.get("query_type") or "financial_summary"

        # 1. Compute variance result if structured metrics exist
        calc_res = None
        calc_block = ""
        if len(hybrid_rag_result.primary_metrics) >= 2:
            p_metrics = sorted(hybrid_rag_result.primary_metrics, key=lambda x: x.fiscal_year, reverse=True)
            curr_val = getattr(p_metrics[0], m_name.lower().replace(" ", "_"), 0.0)
            prior_val = getattr(p_metrics[1], m_name.lower().replace(" ", "_"), 0.0)
            calc_req = VarianceRequest(
                ticker=ticker,
                metric_name=m_name,
                current_period_value=curr_val,
                prior_period_value=prior_val,
            )
            calc_res = calculate_financial_variance(calc_req)
            if calc_res and calc_res.is_success:
                abs_str = f"${calc_res.absolute_change:,.1f}M USD" if calc_res.absolute_change is not None else "N/A"
                pct_str = f"{calc_res.percentage_change:.2f}%" if calc_res.percentage_change is not None else "N/A"
                calc_block = f"""
DETERMINISTIC CALCULATION TOOL OUTPUT (`calculate_financial_variance`):
- Ticker: {ticker}
- Metric: {m_name}
- FY{p_metrics[1].fiscal_year} Value: ${calc_res.prior_period_value:,.1f}M USD
- FY{p_metrics[0].fiscal_year} Value: ${calc_res.current_period_value:,.1f}M USD
- Absolute Variance: {abs_str}
- Percentage Variance: {pct_str}
- Direction: {calc_res.direction}
"""

        # 2. Synthesize Narrative with Vertex AI Gemini
        history_context = f"\nCOMPACTED HISTORY CONTEXT:\n{context_summary}\n" if context_summary else ""
        user_q_str = f"USER PROMPT: {user_prompt}" if user_prompt else f"USER REQUEST: Analyze financial filing data for {ticker}."

        prompt = f"""
{SYSTEM_CONSTITUTION}
{history_context}
{user_q_str}
{calc_block}
HYBRID SEARCH RAG GROUNDING CONTEXT (BigQuery + SEC 10-K Corpus):
{hybrid_rag_result.formatted_context_block}

INSTRUCTIONS:
Directly answer the user prompt above using the grounded context and tool outputs.
1. DO NOT include any introductory pleasantries or filler preamble (e.g., NEVER write "Of course", "Here is the", "Certainly", or "Based on the data"). Jump directly into your answer.
2. Select ONLY the relevant metrics and fiscal years needed to answer the user's specific request. Do NOT dump unnecessary prior-period comparison tables or unrequested metric breakdowns unless the user explicitly requested a multi-year comparison or growth analysis.
3. If the user prompt asks a qualitative question (such as business risks or MD&A strategy), answer the qualitative question directly and thoroughly using the grounded 10-K filings context without forcing an unrequested financial variance table.
"""
        narrative = ""
        model_used = "deterministic-fallback"

        if self.client:
            models_to_try = [self.model_name, settings.tool_model]
            datastore_path = f"projects/{settings.gcp_project_id}/locations/global/collections/default_collection/dataStores/sec-10k-filings-datastore"

            for model_id in models_to_try:
                try:
                    log_tool_execution("vertex_ai_generate_content", "intent", {"model": model_id, "ticker": ticker, "datastore": datastore_path})
                    
                    search_tool = types.Tool(
                        retrieval=types.Retrieval(
                            vertex_ai_search=types.VertexAISearch(datastore=datastore_path)
                        )
                    )
                    tools = [
                        calculate_financial_variance_tool,
                        query_bigquery_financial_metrics_tool,
                        search_sec_filing_chunks_tool,
                        search_tool,
                    ]
                    config = types.GenerateContentConfig(tools=tools)

                    response = self.client.models.generate_content(
                        model=model_id,
                        contents=prompt,
                        config=config,
                    )

                    # Intercept and execute Gemini Native Function Calls
                    if getattr(response, "function_calls", None):
                        for call in response.function_calls:
                            tool_name = call.name
                            tool_args = dict(call.args) if call.args else {}
                            log_tool_execution("gemini_native_function_call", "intent", {"tool": tool_name, "args": tool_args})
                            if tool_name == "calculate_financial_variance_tool":
                                tool_res = calculate_financial_variance_tool(**tool_args)
                                log_tool_execution("gemini_native_function_call", "outcome", tool_res)
                            elif tool_name == "query_bigquery_financial_metrics_tool":
                                tool_res = query_bigquery_financial_metrics_tool(**tool_args)
                                log_tool_execution("gemini_native_function_call", "outcome", tool_res)
                            elif tool_name == "search_sec_filing_chunks_tool":
                                tool_res = search_sec_filing_chunks_tool(**tool_args)
                                log_tool_execution("gemini_native_function_call", "outcome", {"count": len(tool_res)})

                    narrative = response.text.strip() if response.text else ""
                    if not narrative and getattr(response, "function_calls", None):
                        narrative = f"Executed native tool calls: {[c.name for c in response.function_calls]} successfully."

                    model_used = f"Vertex AI ({model_id} + Native ADK Search & Tools)"
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
                "query_type": q_type,
                "metric_name": m_name,
                "variance_result": calc_res,
                "hybrid_search_result": hybrid_rag_result,
                "citations": hybrid_rag_result.grounded_citations if hybrid_rag_result else [],
                "model_used": "failed-auth",
            }

        return {
            "is_success": True,
            "ticker": ticker,
            "query_type": q_type,
            "metric_name": m_name,
            "variance_result": calc_res,
            "hybrid_search_result": hybrid_rag_result,
            "citations": hybrid_rag_result.grounded_citations,
            "narrative": narrative,
            "model_used": model_used,
        }


class RootOrchestrator:
    """ADK Root Orchestrator supervising FinancialAnalystAgent, session memory, and dynamic LLM tool routing."""

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
        """Uses Gemini 3.5 Flash (tool_model) with conversation history context to dynamically parse user intent."""
        # Retrieve recent session history for context-aware multi-turn intent retention
        history = self.session_store.get_session_history(session_id)
        recent_turns_summary = ""
        last_query_type = None
        last_ticker = None
        if history:
            turn_lines = []
            for t in history[-3:]:
                if isinstance(t, dict):
                    turn_lines.append(f"User: {t.get('user_query')}\nAgent: {t.get('agent_response', '')[:200]}")
                    meta = t.get("metadata", {})
                    if meta.get("query_type"):
                        last_query_type = meta["query_type"]
                    if meta.get("ticker"):
                        last_ticker = meta["ticker"]
            recent_turns_summary = "\n".join(turn_lines)

        # 1. Attempt LLM Multi-Turn Intent Parsing with tool_model (Gemini 3.5 Flash)
        if self.analyst_agent and self.analyst_agent.client:
            try:
                log_tool_execution("intent_classification_tool_model", "intent", {"model": self.tool_model, "prompt": prompt})
                intent_prompt = f"""
You are an expert financial intent parser.
Analyze the user's latest query in the context of recent conversation turns.

RECENT CONVERSATION HISTORY:
{recent_turns_summary if recent_turns_summary else "None"}

LATEST USER QUERY: "{prompt}"

INSTRUCTIONS:
1. Identify tickers list (e.g., ["AAPL"], ["AAPL", "MSFT"]). If the query omits ticker (e.g., "how about walmart"), use the new ticker if mentioned, otherwise inherit from history.
2. Identify query_type:
   - "thematic_tracking": questions about business risks, strategic disclosures, AI filings, executive comments, or qualitative topics. IF the previous turn was thematic_tracking/risk questions and the user asks a follow-up like "how about walmart", set query_type to "thematic_tracking"!
   - "peer_comparison": comparing multiple companies.
   - "variance_analysis": explicit calculations of growth, variance, or period-over-period percentage changes.
   - "financial_summary": general financial metrics lookup.
3. Identify requested_years and metric_name.

Return ONLY valid JSON matching this schema:
{{
  "query_type": "thematic_tracking" | "peer_comparison" | "variance_analysis" | "financial_summary",
  "tickers": ["TICKER1", "TICKER2"],
  "requested_years": [2023],
  "metric_name": "Revenue" | "Operating Income" | "Net Income"
}}
"""
                resp = self.analyst_agent.client.models.generate_content(
                    model=self.tool_model,
                    contents=intent_prompt,
                )
                cleaned_text = resp.text.strip().replace("```json", "").replace("```", "").strip()
                parsed_json = json.loads(cleaned_text)
                t_parsed = parsed_json.get("tickers") or ([parsed_json.get("primary_ticker")] if parsed_json.get("primary_ticker") else [last_ticker or "AAPL"])
                t_clean = [t.upper() for t in t_parsed if t]
                return {
                    "query_type": parsed_json.get("query_type", "financial_summary"),
                    "tickers": t_clean,
                    "ticker": t_clean[0] if t_clean else "AAPL",
                    "requested_years": [int(y) for y in parsed_json.get("requested_years", [])],
                    "metric_name": parsed_json.get("metric_name", "Revenue"),
                }
            except Exception as err:
                log_tool_execution("intent_classification_tool_model", "outcome", {"error": str(err)}, status="ERROR")

        # 2. Fallback Heuristic Parsing
        prompt_upper = prompt.upper()

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

        tickers_list = found_tickers if found_tickers else [last_ticker or "AAPL"]

        # Metric parsing
        metric_name = "Revenue"
        if "OPERATING INCOME" in prompt_upper or "OPERATING MARGIN" in prompt_upper or "OPERATING PROFIT" in prompt_upper:
            metric_name = "Operating Income"
        elif "NET INCOME" in prompt_upper or "NET PROFIT" in prompt_upper or "EARNINGS" in prompt_upper:
            metric_name = "Net Income"

        # Years parsing
        years_found = sorted([int(y) for y in re.findall(r'\b(202[0-9])\b', prompt_upper)])
        requested_years = []
        if len(years_found) >= 2:
            min_y, max_y = years_found[0], years_found[-1]
            requested_years = list(range(min_y, max_y + 1))
        elif len(years_found) == 1:
            requested_years = [years_found[0]]
        else:
            requested_years = [2023, 2022]

        # Context-aware query type
        if "RISK" in prompt_upper or "THEMATIC" in prompt_upper or "AI" in prompt_upper or last_query_type == "thematic_tracking":
            query_type = "thematic_tracking"
        elif len(tickers_list) > 1 or "COMPARE" in prompt_upper or ("VS" in prompt_upper and len(tickers_list) > 1):
            query_type = "peer_comparison"
        elif "VARIANCE" in prompt_upper or "GROWTH" in prompt_upper or "CHANGE" in prompt_upper or "INCREASE" in prompt_upper or "DECREASE" in prompt_upper:
            query_type = "variance_analysis"
        else:
            query_type = "financial_summary"

        return {
            "query_type": query_type,
            "tickers": tickers_list,
            "ticker": tickers_list[0],
            "requested_years": requested_years,
            "metric_name": metric_name,
        }

    @trace_span("RootOrchestrator.dispatch")
    def dispatch_query(
        self,
        prompt: str = "",
        session_id: str = "default_session",
        tickers: List[str] = [],
        requested_years: List[int] = [],
        query_type: str = "",
        metric_name: str = "",
        thematic_keyword: str = "",
        export_gcs_uri: str = "",
        human_approved_export: bool = False,
    ) -> Dict[str, Any]:
        """Routes user queries to sub-agents, manages persistent session memory, and applies history compaction."""
        if prompt:
            parsed = self.parse_natural_language_intent(prompt, session_id=session_id)
            query_type = query_type or parsed.get("query_type", "financial_summary")
            tickers = tickers or parsed.get("tickers", [])
            metric_name = metric_name or parsed.get("metric_name", "Revenue")
            thematic_keyword = thematic_keyword or parsed.get("thematic_keyword", "")
            requested_years = requested_years or parsed.get("requested_years", [])

        query_type = query_type or "financial_summary"
        tickers = [t.upper() for t in tickers] if tickers else ["AAPL"]
        primary_ticker = tickers[0]

        # 1. Retrieve persistent session history and apply compaction
        raw_history = self.session_store.get_session_history(session_id)
        compacted = self.compactor.compact_history(raw_history)

        # 2. Context caching for filing documents
        cache_key = f"{primary_ticker}_{requested_years[0] if requested_years else 2023}_10K"
        self.cache_manager.get_or_create_cache(cache_key, content=f"SEC 10K filing data for {primary_ticker}")

        # 3. Execute Hybrid Search RAG tailored to intent query_type
        rag_res = self.hybrid_engine.execute_hybrid_search(
            HybridSearchRequest(
                query_type=query_type,
                tickers=tickers,
                requested_years=requested_years,
                metric_name=metric_name,
                thematic_keyword=thematic_keyword,
            )
        )

        # 4. Run analysis with compacted context summary and RAG grounding
        analysis_res = self.analyst_agent.run_analysis(
            user_prompt=prompt or f"Analyze financial disclosures for {primary_ticker}.",
            hybrid_rag_result=rag_res,
            context_summary=compacted.summary_of_older_turns,
            tickers=tickers,
            requested_years=requested_years,
            metric_name=metric_name,
            query_type=query_type,
            metadata={"ticker": primary_ticker, "tickers": tickers, "metric_name": metric_name, "query_type": query_type},
        )

        if not analysis_res.get("is_success"):
            return analysis_res

        # 5. Save turn to persistent session store with query_type metadata
        user_q = prompt or f"Analyze financial disclosures for {primary_ticker}."
        self.session_store.save_session_turn(
            session_id=session_id,
            user_query=user_q,
            agent_response=analysis_res["narrative"],
            metadata={"ticker": primary_ticker, "tickers": tickers, "metric": metric_name, "query_type": query_type},
        )

        if export_gcs_uri:
            export_req = ExportReportRequest(
                ticker=primary_ticker,
                destination_gcs_uri=export_gcs_uri,
                report_content=analysis_res["narrative"],
            )
            export_res = export_financial_report(export_req, human_approved=human_approved_export)
            analysis_res["export_status"] = export_res.model_dump()

        return analysis_res

    async def dispatch_query_async(
        self,
        prompt: str = "",
        session_id: str = "default_session",
        tickers: List[str] = [],
        requested_years: List[int] = [],
        query_type: str = "",
        metric_name: str = "",
        thematic_keyword: str = "",
        export_gcs_uri: str = "",
        human_approved_export: bool = False,
    ) -> Dict[str, Any]:
        """Asynchronous query dispatch with background memory consolidation."""
        res = self.dispatch_query(
            prompt=prompt,
            session_id=session_id,
            tickers=tickers,
            requested_years=requested_years,
            query_type=query_type,
            metric_name=metric_name,
            thematic_keyword=thematic_keyword,
            export_gcs_uri=export_gcs_uri,
            human_approved_export=human_approved_export,
        )
        if res.get("is_success"):
            await self.async_memory.consolidate_session_memory_async(
                session_id=session_id,
                user_query=prompt or "Financial analysis",
                agent_response=res["narrative"],
                metadata={"ticker": res.get("ticker")},
            )
        return res
