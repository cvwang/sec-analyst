"""FastAPI Web Server for SEC EDGAR Natural Language Analyst agent."""

import os
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from agent.config import settings
from agent.orchestrator import RootOrchestrator, export_financial_report, ExportReportRequest
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

    prompt: str = Field("", description="Freeform natural language chat prompt.")
    tickers: List[str] = Field(default_factory=list, description="Target ticker symbols for analysis (e.g. ['AAPL'], ['AAPL', 'MSFT']).")
    requested_years: List[int] = Field(default_factory=list, description="List of fiscal years for analysis.")
    metric_name: str = Field("", description="Financial metric name.")
    query_type: str = Field("financial_summary", description="'variance_analysis', 'peer_comparison', or 'thematic_tracking'")
    thematic_keyword: str = Field("", description="Thematic tracking keyword (e.g., 'AI', 'R&D').")
    session_id: str = Field("user_session_001", description="Persistent conversational session ID.")


class ExportApiRequest(BaseModel):
    """Input payload for report GCS export REST API."""

    ticker: str
    current_year: int = 2023
    destination_gcs_uri: str
    report_content: str
    human_approved: bool = False


class CreateSessionRequest(BaseModel):
    """Payload for creating a new conversation thread."""
    title: Optional[str] = Field(None, description="Optional custom title for the conversation thread.")

class UpdateSessionRequest(BaseModel):
    """Payload for updating session metadata."""
    title: str = Field(..., description="New title for the conversation thread.")


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


@app.get("/api/v1/sessions")
def list_sessions():
    """Lists all persistent conversation thread summaries."""
    sessions = orchestrator.session_store.list_sessions()
    return {"sessions": sessions}


@app.post("/api/v1/sessions")
def create_session(request: Optional[CreateSessionRequest] = None):
    """Creates a new conversation thread."""
    title = request.title if request else None
    meta = orchestrator.session_store.create_session(title=title)
    return meta


@app.get("/api/v1/sessions/{session_id}")
def get_session(session_id: str):
    """Retrieves full details for a session thread including turns history and last response payload."""
    session = orchestrator.session_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")
    return session


@app.patch("/api/v1/sessions/{session_id}")
def update_session(session_id: str, request: UpdateSessionRequest):
    """Updates custom display title for a conversation thread."""
    meta = orchestrator.session_store.update_session_title(session_id, request.title)
    if not meta:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")
    return meta


@app.delete("/api/v1/sessions")
def clear_all_sessions():
    """Clears all persistent conversation session threads in memory and on disk."""
    orchestrator.session_store.clear_all_sessions()
    return {"status": "SUCCESS", "message": "All session history cleared."}


@app.delete("/api/v1/sessions/{session_id}")
def delete_session(session_id: str):
    """Deletes a conversation session thread."""
    success = orchestrator.session_store.delete_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")
    return {"status": "SUCCESS", "message": f"Session '{session_id}' deleted."}


def _get_metrics_for_year(ticker: str, year: int) -> dict:
    from agent.rag.bigquery_store import BigQueryFinancialStore

    ticker_u = ticker.strip().upper()
    yr_i = int(year)

    store = BigQueryFinancialStore()
    rec = store.query_metrics(ticker=ticker_u, fiscal_year=yr_i)
    if rec:
        rev = rec.revenue * 1e6 if rec.revenue < 1e6 else rec.revenue
        op = rec.operating_income * 1e6 if abs(rec.operating_income) < 1e6 else rec.operating_income
        ni = rec.net_income * 1e6 if abs(rec.net_income) < 1e6 else rec.net_income
        return {"revenue": rev, "operating_income": op, "net_income": ni}

    raise HTTPException(
        status_code=404,
        detail=f"No financial metrics found in GCP BigQuery for ticker {ticker_u} FY{yr_i}.",
    )


@app.get("/api/v1/metrics")
@app.get("/api/metrics")
def get_financial_metrics(ticker: str, start_year: str, end_year: str):
    """Calculates deterministic start/end period financial metrics and YoY variances for charts and tables."""
    try:
        s_yr = int(start_year)
        e_yr = int(end_year)
        ticker_clean = ticker.strip().upper()

        start_m = _get_metrics_for_year(ticker_clean, s_yr)
        end_m = _get_metrics_for_year(ticker_clean, e_yr)

        start_rev = start_m["revenue"]
        start_op = start_m["operating_income"]
        start_ni = start_m["net_income"]
        start_margin = round((start_op / start_rev) * 100.0, 2) if start_rev > 0 else 0.0

        end_rev = end_m["revenue"]
        end_op = end_m["operating_income"]
        end_ni = end_m["net_income"]
        end_margin = round((end_op / end_rev) * 100.0, 2) if end_rev > 0 else 0.0

        rev_change_pct = round(((end_rev - start_rev) / abs(start_rev)) * 100.0, 2) if start_rev != 0 else 0.0
        op_change_pct = round(((end_op - start_op) / abs(start_op)) * 100.0, 2) if start_op != 0 else 0.0
        ni_change_pct = round(((end_ni - start_ni) / abs(start_ni)) * 100.0, 2) if start_ni != 0 else 0.0
        margin_change_bps = round((end_margin - start_margin) * 100.0, 1)

        return {
            "ticker": ticker_clean,
            "start_year": str(start_year),
            "end_year": str(end_year),
            "metrics": {
                "start_period": {
                    "revenue": start_rev,
                    "operating_income": start_op,
                    "net_income": start_ni,
                    "operating_margin": start_margin,
                },
                "end_period": {
                    "revenue": end_rev,
                    "operating_income": end_op,
                    "net_income": end_ni,
                    "operating_margin": end_margin,
                },
                "variances": {
                    "revenue_yoy_change_percent": rev_change_pct,
                    "operating_income_yoy_change_percent": op_change_pct,
                    "net_income_yoy_change_percent": ni_change_pct,
                    "operating_margin_yoy_change_bps": margin_change_bps,
                },
            },
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to calculate metrics: {str(e)}")


@app.get("/api/v1/peer_metrics")
@app.get("/api/peer_metrics")
def get_peer_metrics(ticker: str, peer_ticker: str, year: str):
    """Calculates side-by-side financial metrics for two companies in a specific fiscal year."""
    try:
        yr_i = int(year)
        t1_u = ticker.strip().upper()
        t2_u = peer_ticker.strip().upper()

        m1 = _get_metrics_for_year(t1_u, yr_i)
        m2 = _get_metrics_for_year(t2_u, yr_i)

        rev1, rev2 = m1["revenue"], m2["revenue"]
        op1, op2 = m1["operating_income"], m2["operating_income"]
        ni1, ni2 = m1["net_income"], m2["net_income"]

        margin1 = round((op1 / rev1) * 100.0, 2) if rev1 else 0.0
        margin2 = round((op2 / rev2) * 100.0, 2) if rev2 else 0.0

        return {
            "ticker": t1_u,
            "peer_ticker": t2_u,
            "year": str(yr_i),
            "primary": {
                "ticker": t1_u,
                "revenue": rev1,
                "operating_income": op1,
                "net_income": ni1,
                "operating_margin": margin1,
            },
            "peer": {
                "ticker": t2_u,
                "revenue": rev2,
                "operating_income": op2,
                "net_income": ni2,
                "operating_margin": margin2,
            },
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch peer metrics: {str(e)}")




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
            session_id=request.session_id,
        )

        # Save last response payload to restore split-pane source drawer on thread switch
        orchestrator.session_store.save_last_response(request.session_id, response)

        log_tool_execution(
            tool_name="api_analyze_financials",
            stage="outcome",
            payload={"tickers": request.tickers, "status": "SUCCESS" if response.get("is_success") else "FAILURE"},
            status="SUCCESS" if response.get("is_success") else "ERROR",
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
    assets_dir = os.path.join(static_dir, "assets")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")


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
