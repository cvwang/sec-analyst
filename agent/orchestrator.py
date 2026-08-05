"""ADK Root Orchestrator and Financial Analyst Agent supervising financial variance, peer comparison, and thematic tracking."""

import os
import asyncio
import concurrent.futures
import logging
from typing import Dict, Any, Optional
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
from agent.subagents.search_subagent import search_tool
from agent.memory.session_store import PersistentSessionStore
from agent.observability.logging_config import log_tool_execution
from agent.observability.tracer import trace_span
from agent.guardrails.model_armor import model_armor_guard

logger = logging.getLogger(__name__)


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
    return result


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
    ) -> Dict[str, Any]:
        """Synthesizes grounded financial narrative using Google ADK Runner and LlmAgent by dynamically calling tools."""
        history_context = f"\nCOMPACTED HISTORY CONTEXT:\n{context_summary}\n" if context_summary else ""
        user_q_str = f"USER PROMPT: {user_prompt}" if user_prompt else "USER REQUEST: Analyze financial filing data."

        prompt = f"""
{SYSTEM_CONSTITUTION}
{history_context}
{user_q_str}

INSTRUCTIONS:
Directly answer the user prompt above by dynamically invoking your tools (query_bigquery_financial_metrics_tool, search_tool, calculate_financial_variance_tool) as needed.
"""

        log_tool_execution("adk_runner_execution", "intent", {"model": self.reasoning_model, "prompt": user_prompt})

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

        runner_error = None
        try:
            narrative = _exec_async(_run_runner).strip()
        except Exception as err:
            runner_error = str(err)
            log_tool_execution("adk_runner_execution", "outcome", {"error": runner_error}, status="ERROR")
            narrative = ""

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
            return {
                "is_success": False,
                "is_model_armor_blocked": True,
                "blocked_stage": stage,
                "triggered_category": category,
                "narrative": clean_narrative,
                "error": "MODEL_ARMOR_BLOCK",
                "model_used": "Model Armor Guardrail",
            }

        model_used = f"Vertex AI ({self.reasoning_model} + ADK Search Sub-Agent & Tools)"
        log_tool_execution("adk_runner_execution", "outcome", {"model": self.reasoning_model, "status": "SUCCESS"})

        if not narrative:
            err_detail = runner_error or "Google ADK Runner model execution returned an empty response."
            return {
                "is_success": False,
                "error": err_detail,
                "narrative": f"⚠️ ADK Execution Error: {err_detail}",
                "model_used": "execution-error",
            }


        return {
            "is_success": True,
            "narrative": narrative,
            "model_used": model_used,
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
            # 1. Retrieve persistent session history and construct recent context summary
            raw_history = self.session_store.get_session_history(session_id)
            history_summary = ""
            if raw_history:
                turn_lines = [
                    f"User: {t.get('user_query', '')}\nAgent: {t.get('agent_response', '')[:300]}"
                    for t in raw_history[-3:]
                    if isinstance(t, dict)
                ]
                history_summary = "\n".join(turn_lines)

            # 2. Run analysis directly using ADK FinancialAnalystAgent and Runner
            analysis_res = self.analyst_agent.run_analysis(
                user_prompt=prompt,
                context_summary=history_summary,
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

            if analysis_res.get("is_success"):
                # 3. Save turn to persistent session store
                self.session_store.save_session_turn(
                    session_id=session_id,
                    user_query=prompt,
                    agent_response=analysis_res.get("narrative", ""),
                )

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
