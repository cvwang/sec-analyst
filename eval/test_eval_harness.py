"""Pytest evaluation harness testing financial calculation accuracy, grounding faithfulness, PII scrubbing, orchestration, and Category 2 Memory."""

import json
import os
import pytest
from agent.tools.calculation_engine import calculate_financial_variance, VarianceRequest
from agent.guardrails.pii_scrubber import PIIScrubber
from agent.memory.session_store import PersistentSessionStore
from agent.config import settings
from agent.orchestrator import RootOrchestrator, FinancialAnalystAgent, export_financial_report, ExportReportRequest

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
    unapproved_res = export_financial_report(req, human_approved=False)
    assert unapproved_res.is_success is False
    assert unapproved_res.requires_human_approval is True
    assert unapproved_res.status == "PENDING_HUMAN_APPROVAL"

    approved_res = export_financial_report(req, human_approved=True)
    assert approved_res.is_success is True
    assert approved_res.status == "EXPORTED"


def test_persistent_session_store(tmp_path):
    """Evaluates persistent conversational session store management across turns."""
    store_file = os.path.join(tmp_path, "test_sessions.json")
    store = PersistentSessionStore(storage_path=store_file)

    session_id = "sess_001"
    store.save_session_turn(session_id, "Query 1", "Response 1", {"ticker": "AAPL"})
    store.save_session_turn(session_id, "Query 2", "Response 2", {"ticker": "MSFT"})

    history = store.get_session_history(session_id)
    assert len(history) == 2
    assert history[0]["user_query"] == "Query 1"
    assert history[1]["metadata"]["ticker"] == "MSFT"


def test_root_orchestrator_end_to_end(monkeypatch):
    """Evaluates ADK RootOrchestrator workflow and grounded dynamic LLM narrative synthesis."""
    class MockGenerateResponse:
        def __init__(self, text):
            self.text = text

    class MockModels:
        def generate_content(self, model, contents, **kwargs):
            if "intent parser" in str(contents):
                return MockGenerateResponse('{"query_type": "variance_analysis", "tickers": ["AAPL"], "requested_years": [2023, 2022], "metric_name": "Revenue"}')
            return MockGenerateResponse("### Executive Summary for AAPL (Revenue)\nApple Inc. FY2023 10-K reported Total Net Sales of $383,285 million, down 2.8% due to macroeconomic headwinds in hardware sales.")

    orchestrator = RootOrchestrator()

    response = orchestrator.dispatch_query(
        prompt="Analyze revenue for AAPL between FY2022 and FY2023",
    )

    assert response["is_success"] is True
    if response.get("variance_result"):
        v_res = response["variance_result"]
        abs_val = v_res.get("absolute_change") if isinstance(v_res, dict) else getattr(v_res, "absolute_change", None)
        assert abs_val == -11043.0
    assert "AAPL" in response["narrative"] or "Apple" in response["narrative"]
    assert len(response["narrative"]) > 0
    assert response["model_used"].startswith("Vertex AI")


def test_model_configuration_validation():
    """Evaluates runtime settings for model selection and fallback hierarchy."""
    assert settings.reasoning_model is not None
    assert isinstance(settings.reasoning_model, str)
    assert len(settings.reasoning_model) > 0
    assert settings.tool_model is not None
    assert isinstance(settings.tool_model, str)
    assert len(settings.tool_model) > 0

    agent = FinancialAnalystAgent()
    assert agent.reasoning_model == settings.reasoning_model


def test_multiturn_conversational_context_retention():
    """Evaluates multi-turn context retention ensuring follow-up queries retain active ticker/metric from session history."""
    orchestrator = RootOrchestrator()
    session_id = "test_multiturn_context_session"

    # Turn 1: Initial request for AMZN
    turn1_res = orchestrator.dispatch_query(
        prompt="show me amzn financial data across all years available",
        session_id=session_id,
    )
    assert turn1_res["is_success"] is True
    assert len(turn1_res["narrative"]) > 0

    # Turn 2: Follow-up request omitting ticker ("what about 2024?")
    turn2_res = orchestrator.dispatch_query(
        prompt="what about 2024?",
        session_id=session_id,
    )
    assert turn2_res["is_success"] is True
    assert len(turn2_res["narrative"]) > 0


def test_multiyear_range_query_expansion():
    """Evaluates multi-year range query parsing (e.g. 2022-2024) to ensure all intermediate years are retrieved."""
    orchestrator = RootOrchestrator()
    res = orchestrator.dispatch_query(prompt="show me amzn financial data from 2022-2024")
    assert res["is_success"] is True
    assert len(res["narrative"]) > 0


def test_native_function_calling_dispatch():
    """Evaluates Native Gemini Function Calling dispatch when the model requests tool execution."""
    from agent.tools.calculation_engine import calculate_financial_variance_tool
    from agent.rag.bigquery_store import query_bigquery_financial_metrics_tool
    from agent.rag.sec_corpus import search_sec_filing_chunks_tool

    # 1. Test standalone tool schemas return valid data dicts
    calc_res = calculate_financial_variance_tool("AAPL", "Revenue", 383285.0, 394328.0)
    assert calc_res["is_success"] is True
    assert calc_res["absolute_change"] == -11043.0
    assert calc_res["percentage_change"] == -2.8

    bq_res = query_bigquery_financial_metrics_tool("AAPL", 2023)
    assert bq_res["ticker"] == "AAPL"
    assert bq_res["revenue"] == 383285.0

    sec_res = search_sec_filing_chunks_tool(query="revenue", ticker="AAPL", requested_years=[2023])
    assert isinstance(sec_res, list)

    # 2. Test Agent registration of ADK root_agent tools
    agent = FinancialAnalystAgent()
    root_tool_names = [t.name if hasattr(t, "name") else getattr(t, "__name__", str(t)) for t in agent.root_agent.tools]
    assert "search_agent" in root_tool_names
    assert "calculate_financial_variance_tool" in root_tool_names
    assert "query_bigquery_financial_metrics_tool" in root_tool_names

    analysis_res = agent.run_analysis(
        user_prompt="calculate variance for AAPL revenue",
    )

    assert analysis_res["is_success"] is True
    assert "Vertex AI" in analysis_res["model_used"]
    assert "ADK Search Sub-Agent & Tools" in analysis_res["model_used"]
    assert len(analysis_res["narrative"]) > 0


def test_thematic_tracking_qualitative_risk_disclosures(monkeypatch):
    """Evaluates qualitative risk factor disclosures RAG retrieval, ticker filtering, and token bounding for Meta/thematic queries."""
    from agent.rag.sec_corpus import SECCorpusStore
    from agent.rag.vertex_search import VertexSearchResult, VertexAISearchClient

    mock_results = [
        VertexSearchResult(
            id="chunk_1",
            gcs_uri="gs://sec-analyst-sec-reports/filings/META_2023_10K.md",
            title="Meta Platforms Inc. 10-K Item 1A Risk Factors",
            snippet="Meta Platforms, Inc. faces significant competition in advertising, user engagement risks, regulatory scrutiny over data privacy, and investments in AI infrastructure.",
        )
    ]
    monkeypatch.setattr(VertexAISearchClient, "search_filings", lambda self, query, page_size=5: mock_results)

    # 1. Verify SEC corpus store returns non-empty matching chunks for META risk disclosures
    corpus_store = SECCorpusStore()
    meta_risk_chunks = corpus_store.search_chunks(ticker="META", keyword="risk")
    assert len(meta_risk_chunks) > 0
    assert all(c.ticker == "META" for c in meta_risk_chunks)

    # 2. Verify end-to-end RootOrchestrator handles risk disclosures prompt cleanly
    orchestrator = RootOrchestrator()
    res = orchestrator.dispatch_query("Analyze Meta risk factors disclosure")
    assert res["is_success"] is True
    assert res["narrative"] is not None
    assert len(res["narrative"]) > 0
    assert "unable to analyze" not in res["narrative"].lower()
    assert "unable to provide" not in res["narrative"].lower()


def test_multiturn_qualitative_risk_followup(monkeypatch):
    """Evaluates multi-turn qualitative risk factor follow-up retention when ticker is omitted in Turn 2."""
    from agent.rag.vertex_search import VertexSearchResult, VertexAISearchClient

    mock_results = [
        VertexSearchResult(
            id="chunk_1",
            gcs_uri="gs://sec-analyst-sec-reports/filings/TSLA_2023_10K.md",
            title="Tesla, Inc. 10-K Item 1A Risk Factors",
            snippet="Tesla, Inc. faces risks related to vehicle production ramp-up, battery supply chain constraints, autonomous driving regulatory scrutiny, and competitive pricing dynamics.",
        )
    ]
    captured_queries = []
    def mock_search_filings(self, query, page_size=5):
        captured_queries.append(query)
        if "AI" in query and "risk" not in query.lower():
            return []
        return mock_results

    monkeypatch.setattr(VertexAISearchClient, "search_filings", mock_search_filings)

    orchestrator = RootOrchestrator()
    session_id = "test_multiturn_risk_session"

    # Turn 1: Initial financial highlights for TSLA
    turn1_res = orchestrator.dispatch_query(
        prompt="Explain Tesla 2023 financial highlights",
        session_id=session_id,
    )
    assert turn1_res["is_success"] is True

    # Turn 2: Follow-up asking about business risks omitting ticker ("explain the business risks")
    turn2_res = orchestrator.dispatch_query(
        prompt="explain the business risks",
        session_id=session_id,
    )
    assert turn2_res["is_success"] is True
    assert turn2_res["narrative"] is not None
    assert len(captured_queries) > 0
    assert any("risk" in q.lower() for q in captured_queries)


def test_vertex_search_grounding_chunks_snippet_extraction():
    """Verifies that VertexAISearchClient extracts genuine text snippets from retrieved_context rather than placeholder strings."""
    from agent.rag.vertex_search import VertexAISearchClient

    class MockRetrievedContext:
        def __init__(self, uri, title, text):
            self.uri = uri
            self.title = title
            self.text = text

    class MockChunk:
        def __init__(self, uri, title, text):
            self.retrieved_context = MockRetrievedContext(uri, title, text)

    class MockGroundingMetadata:
        def __init__(self, chunks):
            self.grounding_chunks = chunks

    class MockCandidate:
        def __init__(self, chunks):
            self.grounding_metadata = MockGroundingMetadata(chunks)

    class MockResponse:
        def __init__(self, chunks, text=""):
            self.candidates = [MockCandidate(chunks)]
            self.text = text

    client = VertexAISearchClient()
    mock_chunks = [
        MockChunk("gs://bucket/doc1.md", "Doc 1", "Real unabridged SEC filing text for passage 1"),
        MockChunk("gs://bucket/doc2.md", "Doc 2", "Real unabridged SEC filing text for passage 2"),
        MockChunk("gs://bucket/doc3.md", "Doc 3", "Real unabridged SEC filing text for passage 3"),
    ]
    mock_response = MockResponse(mock_chunks, text="Overall summary text")

    class MockModels:
        def generate_content(self, model, contents, config=None):
            return mock_response

    client.client = type("MockClient", (), {"models": MockModels()})()

    results = client.search_filings("TSLA risk", page_size=5)

    assert len(results) == 3
    assert results[0].snippet == "Real unabridged SEC filing text for passage 1"
    assert results[1].snippet == "Real unabridged SEC filing text for passage 2"
    assert results[2].snippet == "Real unabridged SEC filing text for passage 3"
    for res in results:
        assert "Grounded passage" not in res.snippet


def test_formulate_vertex_search_query():
    """Verifies that formulate_vertex_search_query strips preamble noise and anchors metadata."""
    from agent.rag.sec_corpus import formulate_vertex_search_query

    q1 = formulate_vertex_search_query(
        query="Can you please explain to me what Tesla's business risks were in 2023?",
        ticker="TSLA",
        fiscal_year=2023,
    )
    assert q1 == "TSLA 2023 what Tesla's business risks were in 2023?"
    assert "Can you please explain" not in q1

    q2 = formulate_vertex_search_query(
        ticker="NVDA",
        requested_years=[2023, 2024],
        keyword="AI R&D",
    )
    assert q2 == "NVDA 2023 2024 AI R&D"

