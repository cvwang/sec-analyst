"""FastAPI Web Server for SEC EDGAR Natural Language Analyst agent."""

import os
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from agent.config import settings
from agent.orchestrator import RootOrchestrator, export_financial_report, ExportReportRequest
from agent.guardrails.pii_scrubber import PIIScrubber
from agent.observability.logging_config import log_tool_execution

app = FastAPI(
    title="SEC EDGAR Natural Language Analyst API",
    description="Agentic Financial Analyst API with Hybrid Search RAG, Memory, and HITL Guardrails.",
    version="2.0.0",
)

# Enable CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Instantiate ADK Root Orchestrator
orchestrator = RootOrchestrator()


class AnalysisApiRequest(BaseModel):
    """Input payload for financial analysis REST API."""

    prompt: Optional[str] = Field(None, description="Freeform natural language chat prompt.")
    query_type: str = Field("variance_analysis", description="'variance_analysis', 'peer_comparison', or 'thematic_tracking'")
    ticker: Optional[str] = Field(None, description="Primary ticker symbol.")
    current_year: Optional[int] = Field(None, description="Current fiscal year.")
    prior_year: Optional[int] = Field(None, description="Prior fiscal year.")
    metric_name: Optional[str] = Field(None, description="Financial metric name.")
    secondary_tickers: List[str] = Field(default_factory=list, description="Secondary tickers for peer comparison.")
    thematic_keyword: Optional[str] = Field(None, description="Thematic tracking keyword (e.g., 'AI', 'R&D').")
    session_id: str = Field("user_session_001", description="Persistent conversational session ID.")


class ExportApiRequest(BaseModel):
    """Input payload for report GCS export REST API."""

    ticker: str
    current_year: int = 2023
    destination_gcs_uri: str
    report_content: str
    human_approved: bool = False


@app.get("/api/v1/health")
def health_check():
    """Health check and readiness probe endpoint."""
    return {
        "status": "HEALTHY",
        "service": "sec-edgar-analyst",
        "project_id": settings.gcp_project_id,
        "region": settings.gcp_region,
        "reasoning_model": settings.reasoning_model,
    }


@app.post("/api/v1/analyze")
def analyze_financials(request: AnalysisApiRequest):
    """Executes financial variance analysis, peer comparison, or thematic tracking."""
    log_tool_execution(
        tool_name="api_analyze_financials",
        stage="intent",
        payload=request.model_dump(),
    )

    try:
        response = orchestrator.dispatch_query(
            prompt=request.prompt,
            query_type=request.query_type,
            ticker=request.ticker,
            current_year=request.current_year,
            prior_year=request.prior_year,
            metric_name=request.metric_name,
            secondary_tickers=request.secondary_tickers,
            thematic_keyword=request.thematic_keyword,
            session_id=request.session_id,
        )

        if not response.get("is_success"):
            raise HTTPException(status_code=400, detail=response.get("error"))

        # Scrub PII from outgoing response
        response["narrative"] = PIIScrubber.scrub_text(response["narrative"])

        log_tool_execution(
            tool_name="api_analyze_financials",
            stage="outcome",
            payload={"ticker": request.ticker, "status": "SUCCESS"},
            status="SUCCESS",
        )
        return response

    except Exception as e:
        log_tool_execution("api_analyze_financials", "outcome", {"error": str(e)}, status="ERROR")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/export")
def export_report(request: ExportApiRequest):
    """Exports generated financial report to GCS with Human-In-The-Loop guardrail enforcement."""
    export_req = ExportReportRequest(
        ticker=request.ticker,
        destination_gcs_uri=request.destination_gcs_uri,
        report_content=request.report_content,
    )
    res = export_financial_report(export_req, human_approved=request.human_approved)
    return res.model_dump()


@app.get("/api/v1/history")
def get_session_history(session_id: str = "user_session_001"):
    """Retrieves stored persistent session turns for a given session ID."""
    history = orchestrator.session_store.get_session_history(session_id)
    return {
        "session_id": session_id,
        "turns_stored": len(history),
        "history": history,
    }


# Mount Static Files for Split-Pane Web Dashboard UI
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
def serve_dashboard():
    """Serves the Split-Pane Web UI Dashboard index.html."""
    index_file = os.path.join(static_dir, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return JSONResponse(
        status_code=200,
        content={"message": "SEC EDGAR Analyst API running. Visit /api/v1/health or create agent/static/index.html"},
    )
