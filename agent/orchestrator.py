"""ADK Root Orchestrator and Financial Analyst Agent supervising financial variance, peer comparison, and thematic tracking."""

import os
import re
import time
import uuid
import asyncio
import concurrent.futures
import logging
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from google.genai import types
from google.adk.agents.llm_agent import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.models import LlmRequest, LlmResponse
from agent.config import settings
from agent.constitution import SYSTEM_CONSTITUTION
from agent.tools.calculation_engine import calculate_financial_variance_tool
from agent.rag.bigquery_store import query_bigquery_financial_metrics_tool
from agent.rag.sec_corpus import reset_grounded_chunks, get_grounded_chunks, annotate_grounded_highlights_with_llm, search_sec_filing_chunks_tool
from agent.subagents.search_subagent import search_tool
from agent.memory.session_store import PersistentSessionStore
from agent.observability.logging_config import log_tool_execution
from agent.observability.tracer import trace_span
from agent.observability.cost_tracker import CostTracker
from agent.observability.telemetry_sink import BigQueryTelemetrySink, TelemetryEvent
from agent.guardrails.model_armor import model_armor_guard

logger = logging.getLogger(__name__)
telemetry_sink = BigQueryTelemetrySink()



def model_armor_before_model_callback(callback_context, llm_request: LlmRequest) -> Optional[LlmResponse]:
    """Sanitize user input prompt ingress via Model Armor before calling the LLM."""
    prompt_text = ""
    if llm_request and llm_request.contents:
        for content in reversed(llm_request.contents):
            if content.parts:
                for part in content.parts:
                    if getattr(part, "text", None):
                        prompt_text = part.text
                        break
            if prompt_text:
                break

    if not prompt_text:
        return None

    res = model_armor_guard.sanitize_user_prompt(prompt_text)
    if res.is_blocked:
        return LlmResponse(
            content=types.Content(
                role="model",
                parts=[
                    types.Part.from_text(
                        text=f"[MODEL_ARMOR_BLOCK:STAGE=INGRESS:CATEGORY={res.matched_filter}] {res.rejection_message}"
                    )
                ],
            )
        )
    return None


def model_armor_after_model_callback(callback_context, llm_response: LlmResponse) -> Optional[LlmResponse]:
    """Sanitize LLM model response egress via Model Armor before returning content to caller."""
    response_text = ""
    if llm_response and llm_response.content and llm_response.content.parts:
        for part in llm_response.content.parts:
            if getattr(part, "text", None):
                response_text += part.text

    if not response_text:
        return None

    res = model_armor_guard.sanitize_model_response(response_text)
    if res.is_blocked:
        return LlmResponse(
            content=types.Content(
                role="model",
                parts=[
                    types.Part.from_text(
                        text=f"[MODEL_ARMOR_BLOCK:STAGE=EGRESS:CATEGORY={res.matched_filter}] {res.rejection_message}"
                    )
                ],
            )
        )
    return None


def _exec_async(coro_fn):
    """Executes an async coroutine safely, supporting both sync contexts and active event loops."""
    try:
        return asyncio.run(coro_fn())
    except RuntimeError as e:
        if "running event loop" in str(e):
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                return executor.submit(lambda: asyncio.run(coro_fn())).result()
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
def consolidate_grounded_chunks(chunks: List[dict]) -> List[dict]:
    """Groups passages retrieved from the same GCS document section into a single unified context chunk."""
    if not chunks:
        return []

    merged_map: Dict[str, dict] = {}
    for c in chunks:
        key = c.get("gcs_uri") or f"{c.get('ticker')}_{c.get('fiscal_year')}_{c.get('section')}"
        if key in merged_map:
            existing = merged_map[key]
            new_content = c.get("content", "")
            if new_content and new_content not in existing["content"]:
                existing["content"] = f"{existing['content']}\n\n{new_content}"
            new_excerpt = c.get("highlight_excerpt", "")
            if new_excerpt and existing.get("highlight_excerpt") and new_excerpt not in existing.get("highlight_excerpt", ""):
                existing["highlight_excerpt"] = f"{existing['highlight_excerpt']}\n\n{new_excerpt}"
        else:
            merged_map[key] = dict(c)

    return list(merged_map.values())


class FinancialAnalystAgent:
    """Financial Analyst Agent using Google ADK LlmAgent and Runner for financial reasoning and dynamic tool calling."""

    def __init__(self):
        self.reasoning_model = settings.reasoning_model

        os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "true")
        os.environ.setdefault("GOOGLE_CLOUD_PROJECT", settings.gcp_project_id)
        os.environ.setdefault("GOOGLE_CLOUD_LOCATION", settings.gcp_region)

        self.root_agent = LlmAgent(
            name="root_analyst_agent",
            model=self.reasoning_model,
            instruction=SYSTEM_CONSTITUTION,
            before_model_callback=model_armor_before_model_callback,
            after_model_callback=model_armor_after_model_callback,
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

    @trace_span("FinancialAnalystAgent.run_analysis")
    def run_analysis(
        self,
        user_prompt: str,
        context_summary: str = "",
        session_id: str = "default_session",
    ) -> Dict[str, Any]:
        """Synthesizes grounded financial narrative using Google ADK Runner and LlmAgent by dynamically calling tools."""
        start_time = time.perf_counter()
        history_context = f"\nCOMPACTED HISTORY CONTEXT:\n{context_summary}\n" if context_summary else ""
        user_q_str = f"USER PROMPT: {user_prompt}" if user_prompt else "USER REQUEST: Analyze financial filing data."

        prompt = f"""
{SYSTEM_CONSTITUTION}
{history_context}
{user_q_str}

INSTRUCTIONS:
1. Directly answer the user prompt above by dynamically invoking your tools (query_bigquery_financial_metrics_tool, search_tool, calculate_financial_variance_tool) as needed.
2. Determine dynamically if visual UI components (charts, metrics, tables) add value for this response. If visual representation is helpful, include an ```a2ui JSON block using supported catalog components. If visuals are not appropriate (e.g. general disclosures, policy questions, or unavailable data), respond purely with grounded text and citations.
"""

        log_tool_execution("adk_runner_execution", "intent", {"model": self.reasoning_model, "prompt": user_prompt})

        reset_grounded_chunks()
        captured_tool_result = None
        async def _run_runner():
            nonlocal captured_tool_result
            try:
                session = await self.session_service.get_session(
                    app_name="sec_analyst", user_id="analyst_user", session_id=session_id
                )
            except Exception:
                session = None

            if not session:
                session = await self.session_service.create_session(
                    app_name="sec_analyst", user_id="analyst_user", session_id=session_id
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
                        fn_resp = getattr(part, "function_response", None)
                        if fn_resp and getattr(fn_resp, "name", None) == "calculate_financial_variance_tool":
                            resp_dict = getattr(fn_resp, "response", {})
                            if isinstance(resp_dict, dict):
                                captured_tool_result = resp_dict.get("result", resp_dict)
            return final_text

        runner_error = None
        try:
            narrative = _exec_async(_run_runner).strip()
        except Exception as err:
            runner_error = str(err)
            log_tool_execution("adk_runner_execution", "outcome", {"error": runner_error}, status="ERROR")
            narrative = ""

        # Retrieve grounded RAG chunks collected during execution
        raw_chunks = get_grounded_chunks()
        seen_gcs = set()
        unique_chunks = []
        for chunk in raw_chunks:
            g_uri = chunk.get("gcs_uri") or chunk.get("citation") or chunk.get("chunk_id")
            if g_uri not in seen_gcs:
                seen_gcs.add(g_uri)
                unique_chunks.append(chunk)

        # Extract cited GCS URIs or filenames directly from the model narrative
        cited_gcs_uris = set(re.findall(r'gs://[^\s\)\>\]\*\,\"\']+', narrative))
        cited_filenames = set(re.findall(r'\b[A-Z0-9]+_\d{4}_Item[0-9A-Z_]+(?:\.md)?\b', narrative))

        # Filter chunks to ONLY those explicitly cited/referenced by the agent model response
        cited_chunks = []
        seen_cited_gcs = set()
        if cited_gcs_uris or cited_filenames:
            for chunk in unique_chunks:
                g_uri = chunk.get("gcs_uri", "")
                filename = os.path.basename(g_uri)
                if g_uri in cited_gcs_uris or filename in cited_filenames or any(fn in g_uri for fn in cited_filenames):
                    if g_uri not in seen_cited_gcs:
                        seen_cited_gcs.add(g_uri)
                        cited_chunks.append(chunk)

        # Fallback: If model narrative did not print explicit gs:// links, filter candidate hits by prompt ticker & requested year(s)
        if not cited_chunks and unique_chunks:
            prompt_years = [int(y) for y in re.findall(r'\b(202[0-9])\b', user_prompt)]
            prompt_tickers = [c.get("ticker") for c in unique_chunks if c.get("ticker") and c.get("ticker") in user_prompt.upper()]
            
            for chunk in unique_chunks:
                g_uri = chunk.get("gcs_uri", "")
                match_yr = not prompt_years or (chunk.get("fiscal_year") in prompt_years)
                match_tk = not prompt_tickers or (chunk.get("ticker") in prompt_tickers)
                if match_yr and match_tk and g_uri not in seen_cited_gcs:
                    seen_cited_gcs.add(g_uri)
                    cited_chunks.append(chunk)

        grounded_chunks = consolidate_grounded_chunks(cited_chunks if cited_chunks else unique_chunks)
        if narrative and grounded_chunks:
            grounded_chunks = annotate_grounded_highlights_with_llm(grounded_chunks, narrative)

        citations = [c["citation"] for c in grounded_chunks if c.get("citation")]

        # Extract tickers & fiscal years dynamically from user prompt, grounded RAG chunks, tool outputs, and citations
        tickers = []
        years = [int(y) for y in re.findall(r'\b(202[0-9])\b', user_prompt)]

        # 1. From grounded RAG chunks
        for c in grounded_chunks:
            tk = c.get("ticker")
            if tk and tk != "SEC" and tk not in tickers:
                tickers.append(tk)
            fy = c.get("fiscal_year")
            if fy and fy not in years:
                years.append(fy)

        # 2. From structured calculation / metric tool output
        if isinstance(captured_tool_result, dict):
            tk = captured_tool_result.get("ticker")
            if tk and tk != "SEC" and tk not in tickers:
                tickers.append(tk)

        # 3. From GCS URIs cited in narrative
        for gcs_uri in cited_gcs_uris:
            m = re.search(r'/([A-Z0-9]+)_(\d{4})_', gcs_uri)
            if m:
                tk, yr = m.group(1), int(m.group(2))
                if tk != "SEC" and tk not in tickers:
                    tickers.append(tk)
                if yr not in years:
                    years.append(yr)

        primary_ticker = tickers[0] if tickers else "SEC"
        if not years:
            years = [2023]

        # Determine query_type dynamically based on retrieved artifacts and tools executed
        if grounded_chunks:
            is_risk = any("Item 1A" in c.get("section", "") for c in grounded_chunks)
            query_type = "peer_comparison" if len(tickers) > 1 else ("thematic_tracking" if is_risk else "financial_summary")
        elif captured_tool_result:
            query_type = "variance_analysis"
        else:
            query_type = "financial_summary"

        hybrid_search_result = {
            "text_chunks": grounded_chunks,
            "grounded_citations": citations,
            "query_type": query_type,
        }

        latency_ms = (time.perf_counter() - start_time) * 1000.0

        # Estimate token usage and calculate costs
        input_tokens = int(len(prompt.split()) * 1.3)
        output_tokens = int(len(narrative.split()) * 1.3)
        cached_tokens = int(len(SYSTEM_CONSTITUTION.split()) * 1.3) if history_context else 0

        cost = CostTracker.calculate_cost(
            model_name=self.reasoning_model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_tokens=cached_tokens,
        )

        trace_id = f"trace-{uuid.uuid4().hex[:12]}"

        # Intercept Model Armor hard-fail block responses
        if "[MODEL_ARMOR_BLOCK:" in narrative:
            stage = "ingress" if "STAGE=INGRESS" in narrative else "egress"
            category = "SECURITY_POLICY"
            if "CATEGORY=" in narrative:
                try:
                    category = narrative.split("CATEGORY=")[1].split("]")[0]
                except IndexError:
                    category = "SECURITY_POLICY"

            clean_narrative = narrative
            if "]" in narrative:
                clean_narrative = narrative.split("]", 1)[1].strip()

            log_tool_execution(
                "adk_runner_execution",
                "outcome",
                {"model_armor_blocked": True, "stage": stage, "category": category},
                status="BLOCKED",
            )

            telemetry_sink.log_event(
                TelemetryEvent(
                    trace_id=trace_id,
                    session_id=session_id,
                    event_type="query_execution",
                    model_name=self.reasoning_model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cached_tokens=cached_tokens,
                    latency_ms=latency_ms,
                    estimated_cost_usd=cost.total_cost_usd,
                    cached_savings_usd=cost.cached_savings_usd,
                    status="BLOCKED",
                    error=f"MODEL_ARMOR_BLOCK:{stage}:{category}",
                )
            )

            return {
                "is_success": False,
                "is_model_armor_blocked": True,
                "blocked_stage": stage,
                "triggered_category": category,
                "narrative": clean_narrative,
                "error": "MODEL_ARMOR_BLOCK",
                "model_used": "Model Armor Guardrail",
                "ticker": primary_ticker,
                "tickers": tickers,
                "requested_years": years,
                "query_type": query_type,
                "citations": citations,
                "hybrid_search_result": hybrid_search_result,
                "telemetry": {
                    "trace_id": trace_id,
                    "latency_ms": latency_ms,
                    "cost_usd": cost.total_cost_usd,
                    "cached_savings_usd": cost.cached_savings_usd,
                },
            }

        model_used = f"Vertex AI ({self.reasoning_model} + ADK Search Sub-Agent & Tools)"
        log_tool_execution("adk_runner_execution", "outcome", {"model": self.reasoning_model, "status": "SUCCESS"})

        if not narrative:
            err_detail = runner_error or "Google ADK Runner model execution returned an empty response."

            telemetry_sink.log_event(
                TelemetryEvent(
                    trace_id=trace_id,
                    session_id=session_id,
                    event_type="query_execution",
                    model_name=self.reasoning_model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cached_tokens=cached_tokens,
                    latency_ms=latency_ms,
                    estimated_cost_usd=cost.total_cost_usd,
                    cached_savings_usd=cost.cached_savings_usd,
                    status="ERROR",
                    error=err_detail,
                )
            )

            return {
                "is_success": False,
                "error": err_detail,
                "narrative": f"⚠️ ADK Execution Error: {err_detail}",
                "model_used": "execution-error",
                "ticker": primary_ticker,
                "tickers": tickers,
                "requested_years": years,
                "query_type": query_type,
                "citations": citations,
                "hybrid_search_result": hybrid_search_result,
                "telemetry": {
                    "trace_id": trace_id,
                    "latency_ms": latency_ms,
                    "cost_usd": cost.total_cost_usd,
                },
            }

        telemetry_sink.log_event(
            TelemetryEvent(
                trace_id=trace_id,
                session_id=session_id,
                event_type="query_execution",
                model_name=self.reasoning_model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cached_tokens=cached_tokens,
                latency_ms=latency_ms,
                estimated_cost_usd=cost.total_cost_usd,
                cached_savings_usd=cost.cached_savings_usd,
                status="SUCCESS",
            )
        )

        return {
            "is_success": True,
            "narrative": narrative,
            "model_used": model_used,
            "ticker": primary_ticker,
            "tickers": tickers,
            "requested_years": years,
            "query_type": query_type,
            "citations": citations,
            "hybrid_search_result": hybrid_search_result,
            "tool_result": captured_tool_result,
            "telemetry": {
                "trace_id": trace_id,
                "latency_ms": latency_ms,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cached_tokens": cached_tokens,
                "cost_usd": cost.total_cost_usd,
                "cached_savings_usd": cost.cached_savings_usd,
            },
        }



class RootOrchestrator:
    """ADK Root Orchestrator supervising FinancialAnalystAgent and persistent session memory."""

    def __init__(self):
        self.reasoning_model = settings.reasoning_model
        self.analyst_agent = FinancialAnalystAgent()
        self.session_store = PersistentSessionStore()

    @trace_span("RootOrchestrator.dispatch")
    def dispatch_query(
        self,
        prompt: str,
        session_id: str = "default_session",
        export_gcs_uri: str = "",
        human_approved_export: bool = False,
    ) -> Dict[str, Any]:
        """Routes user queries directly to ADK FinancialAnalystAgent and manages persistent session memory."""
        if not prompt:
            raise ValueError("No query prompt provided.")

        try:
            # 1. Retrieve persistent session history and construct recent context summary with target company propagation
            raw_history = self.session_store.get_session_history(session_id)
            history_summary = ""
            recent_ticker = ""
            if raw_history:
                turn_lines = []
                for t in raw_history[-4:]:
                    if isinstance(t, dict):
                        u_q = t.get("user_query", "")
                        a_r = t.get("agent_response", "")[:300]
                        turn_lines.append(f"User: {u_q}\nAgent: {a_r}")
                        last_resp = t.get("metadata", {}).get("last_response", {})
                        past_tk = last_resp.get("ticker")
                        if past_tk and past_tk != "SEC":
                            recent_ticker = past_tk

                history_summary = "\n".join(turn_lines)
                if recent_ticker:
                    history_summary += f"\nACTIVE CONVERSATION CONTEXT: The primary target company currently discussed in this thread is '{recent_ticker}'. If the user prompt is a follow-up question without an explicit ticker (e.g. 'company risks', 'operating margin', 'revenue'), assume the target company is '{recent_ticker}'."

            # 2. Run analysis directly using ADK FinancialAnalystAgent and Runner
            analysis_res = self.analyst_agent.run_analysis(
                user_prompt=prompt,
                context_summary=history_summary,
                session_id=session_id,
            )

            export_status_dict = None
            if export_gcs_uri and analysis_res.get("is_success"):
                export_req = ExportReportRequest(
                    ticker="REPORT",
                    destination_gcs_uri=export_gcs_uri,
                    report_content=analysis_res.get("narrative", ""),
                )
                export_res = export_financial_report(export_req, human_approved=human_approved_export)
                export_status_dict = export_res.model_dump()

            if analysis_res.get("narrative"):
                # 3. Save turn to persistent session store with full response payload metadata
                self.session_store.save_session_turn(
                    session_id=session_id,
                    user_query=prompt,
                    agent_response=analysis_res.get("narrative", ""),
                    metadata={"last_response": analysis_res},
                )
                self.session_store.save_last_response(session_id, analysis_res)

            analysis_res["export_status"] = export_status_dict
            return analysis_res
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
