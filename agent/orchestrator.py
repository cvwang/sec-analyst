"""ADK Root Orchestrator and Financial Analyst Agent supervising financial variance, peer comparison, and thematic tracking with Hybrid Search RAG."""

import os
import json
import re
import time
import asyncio
import concurrent.futures
import google.auth
from google.cloud import discoveryengine_v1 as discoveryengine
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from google import genai
from google.genai import types
from google.adk.agents.llm_agent import LlmAgent
from google.adk.tools.agent_tool import AgentTool
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from agent.config import settings
from agent.constitution import SYSTEM_CONSTITUTION
from agent.tools.calculation_engine import calculate_financial_variance, calculate_financial_variance_tool, VarianceRequest
from agent.rag.bigquery_store import query_bigquery_financial_metrics_tool
from agent.subagents.search_subagent import search_tool, search_agent
from agent.rag.hybrid_search import HybridSearchEngine, HybridSearchRequest, HybridSearchResult
from agent.memory.cache_manager import HistoryCompactor, ContextCacheManager
from agent.memory.session_store import PersistentSessionStore
from agent.memory.async_memory import AsyncMemoryManager
from agent.observability.logging_config import log_tool_execution
from agent.observability.tracer import trace_span


def _exec_async(coro_fn):
    """Executes an async coroutine safely, supporting both sync contexts and active event loops."""
    try:
        return asyncio.run(coro_fn())
    except RuntimeError as e:
        if "running event loop" in str(e):
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                return executor.submit(lambda: asyncio.run(coro_fn())).result()
        raise e


def safe_generate_content(client, model, contents, config=None, retries=3, delay=2):
    """Executes model.generate_content with exponential backoff retry for 429 rate limit quota spikes."""
    for attempt in range(retries):
        try:
            return client.models.generate_content(model=model, contents=contents, config=config)
        except Exception as e:
            if ("429" in str(e) or "RESOURCE_EXHAUSTED" in str(e)) and attempt < retries - 1:
                time.sleep(delay * (attempt + 1))
                continue
            raise e


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
    """Financial Analyst Agent using Google ADK LlmAgent and Runner for financial reasoning and dynamic tool calling."""

    def __init__(self):
        self.model_name = settings.reasoning_model
        self.reasoning_model = settings.reasoning_model
        self.constitution = SYSTEM_CONSTITUTION
        self.client = self._init_genai_client()
        self.hybrid_engine = HybridSearchEngine()

        os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "true")
        os.environ.setdefault("GOOGLE_CLOUD_PROJECT", settings.gcp_project_id)
        os.environ.setdefault("GOOGLE_CLOUD_LOCATION", settings.gcp_region)

        self.root_agent = LlmAgent(
            name="root_analyst_agent",
            model=self.reasoning_model,
            instruction=SYSTEM_CONSTITUTION,
            tools=[
                search_tool,
                calculate_financial_variance_tool,
                query_bigquery_financial_metrics_tool,
            ],
        )
        self.session_service = InMemorySessionService()
        self.runner = Runner(
            app_name="sec_analyst",
            agent=self.root_agent,
            session_service=self.session_service,
        )

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
    ) -> Dict[str, Any]:
        """Synthesizes grounded financial narrative using Google ADK Runner and LlmAgent from RAG context."""
        history_context = f"\nCOMPACTED HISTORY CONTEXT:\n{context_summary}\n" if context_summary else ""
        user_q_str = f"USER PROMPT: {user_prompt}" if user_prompt else "USER REQUEST: Analyze financial filing data."

        prompt = f"""
{SYSTEM_CONSTITUTION}
{history_context}
{user_q_str}
HYBRID SEARCH RAG GROUNDING CONTEXT (BigQuery + SEC 10-K Corpus):
{hybrid_rag_result.formatted_context_block}

INSTRUCTIONS:
Directly answer the user prompt above using the grounded context and tool outputs.
1. DO NOT include any introductory pleasantries or filler preamble (e.g., NEVER write "Of course", "Here is the", "Certainly", or "Based on the data"). Jump directly into your answer.
2. Select ONLY the relevant metrics and fiscal years needed to answer the user's specific request. Do NOT dump unnecessary prior-period comparison tables or unrequested metric breakdowns unless the user explicitly requested a multi-year comparison or growth analysis.
3. If the user prompt asks a qualitative question (such as business risks or MD&A strategy), answer the qualitative question directly and thoroughly using the grounded 10-K filings context without forcing an unrequested financial variance table.
"""

        datastore_path = f"projects/{settings.gcp_project_id}/locations/global/collections/default_collection/dataStores/sec-10k-filings-datastore"
        log_tool_execution("adk_runner_execution", "intent", {"model": self.reasoning_model, "datastore": datastore_path})

        async def _run_runner():
            session = await self.session_service.create_session(
                app_name="sec_analyst", user_id="analyst_user"
            )
            content = types.Content(role="user", parts=[types.Part.from_text(text=prompt)])
            final_text = ""
            async for event in self.runner.run_async(
                user_id="analyst_user", session_id=session.id, new_message=content
            ):
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if part.text:
                            final_text = part.text
            return final_text

        try:
            narrative = _exec_async(_run_runner).strip()
        except Exception as err:
            log_tool_execution("adk_runner_execution", "outcome", {"error": str(err)}, status="ERROR")
            narrative = ""

        model_used = f"Vertex AI ({self.reasoning_model} + ADK Search Sub-Agent & Tools)"
        log_tool_execution("adk_runner_execution", "outcome", {"model": self.reasoning_model, "status": "SUCCESS"})

        if not narrative:
            return {
                "is_success": False,
                "error": "Google ADK Runner model execution failed. Please verify GCP ADC authentication (`gcloud auth application-default login`).",
                "narrative": "⚠️ Unable to generate dynamic LLM response. Please run `gcloud auth application-default login` to re-authenticate with Google Cloud.",
                "model_used": "failed-auth",
            }

        return {
            "is_success": True,
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
        if history:
            turn_lines = [
                f"User: {t.get('user_query')}\nAgent: {t.get('agent_response', '')[:200]}"
                for t in history[-3:]
                if isinstance(t, dict)
            ]
            recent_turns_summary = "\n".join(turn_lines)

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
3. Identify requested_years, metric_name, and thematic_keyword (e.g., 'risk', 'AI', 'supply chain', 'R&D', 'cybersecurity'). If the query asks about risks or business disclosures, set thematic_keyword to 'risk'.

Return ONLY valid JSON matching this schema:
{{
  "query_type": "thematic_tracking" | "peer_comparison" | "variance_analysis" | "financial_summary",
  "tickers": ["TICKER1", "TICKER2"],
  "requested_years": [2023],
  "metric_name": "Revenue" | "Operating Income" | "Net Income",
  "thematic_keyword": "risk" | "AI" | "supply chain" | "R&D" | "cybersecurity" | ""
}}
"""
        resp = safe_generate_content(
            self.analyst_agent.client,
            model=self.tool_model,
            contents=intent_prompt,
        )
        cleaned_text = resp.text.strip().replace("```json", "").replace("```", "").strip()
        json_match = re.search(r'\{.*\}', cleaned_text, re.DOTALL)
        if json_match:
            cleaned_text = json_match.group(0)
        parsed = json.loads(cleaned_text)
        raw_tickers = parsed["tickers"] if "tickers" in parsed else []
        tickers = [t.upper() for t in raw_tickers if t]
        if not tickers:
            raise ValueError(f"Unable to identify target ticker symbol for prompt: '{prompt}'")
        requested_years = parsed["requested_years"] if "requested_years" in parsed else []

        return {
            "query_type": parsed["query_type"],
            "tickers": tickers,
            "requested_years": requested_years,
            "metric_name": parsed.get("metric_name", ""),
            "thematic_keyword": parsed.get("thematic_keyword", ""),
        }

    @trace_span("RootOrchestrator.dispatch")
    def dispatch_query(
        self,
        prompt: str,
        session_id: str = "default_session",
        export_gcs_uri: str = "",
        human_approved_export: bool = False,
    ) -> Dict[str, Any]:
        """Routes user queries to sub-agents, manages persistent session memory, and applies history compaction."""
        if not prompt:
            raise ValueError("No query prompt provided.")

        try:
            parsed = self.parse_natural_language_intent(prompt, session_id=session_id)
            query_type = parsed["query_type"]
            tickers = [t.upper() for t in parsed["tickers"] if t]
            metric_name = parsed["metric_name"]
            thematic_keyword = parsed["thematic_keyword"]
            requested_years = parsed["requested_years"]

            if not tickers:
                raise ValueError("No target ticker symbol provided for analysis.")
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
                    metric_name=metric_name or "",
                    thematic_keyword=thematic_keyword or "",
                )
            )

            # 4. Run analysis with compacted context summary and RAG grounding
            analysis_res = self.analyst_agent.run_analysis(
                user_prompt=prompt,
                hybrid_rag_result=rag_res,
                context_summary=compacted.summary_of_older_turns,
            )

            export_status_dict = None
            if export_gcs_uri and analysis_res.get("is_success"):
                export_req = ExportReportRequest(
                    ticker=primary_ticker,
                    destination_gcs_uri=export_gcs_uri,
                    report_content=analysis_res.get("narrative", ""),
                )
                export_res = export_financial_report(export_req, human_approved=human_approved_export)
                export_status_dict = export_res.model_dump()

            if analysis_res.get("is_success"):
                # 5. Save turn to persistent session store with query_type metadata
                self.session_store.save_session_turn(
                    session_id=session_id,
                    user_query=prompt,
                    agent_response=analysis_res.get("narrative", ""),
                    metadata={"tickers": tickers, "metric_name": metric_name, "query_type": query_type},
                )

            return {
                "is_success": analysis_res.get("is_success", False),
                "narrative": analysis_res.get("narrative", ""),
                "model_used": analysis_res.get("model_used", ""),
                "tickers": tickers,
                "query_type": query_type,
                "metric_name": metric_name,
                "thematic_keyword": thematic_keyword,
                "requested_years": requested_years,
                "hybrid_search_result": rag_res,
                "citations": rag_res.grounded_citations if rag_res else [],
                "export_status": export_status_dict,
            }
        except Exception as e:
            err_msg = str(e)
            if "Reauthentication is needed" in err_msg or "RefreshError" in err_msg or "401" in err_msg:
                narrative = "⚠️ GCP Authentication Expired: Reauthentication is needed. Please run `gcloud auth application-default login` in your terminal to re-authenticate with Google Cloud."
            else:
                narrative = f"⚠️ Query execution failed: {err_msg}"

            log_tool_execution("dispatch_query", "outcome", {"error": err_msg}, status="ERROR")
            return {
                "is_success": False,
                "error": err_msg,
                "narrative": narrative,
                "model_used": "failed-auth",
            }
