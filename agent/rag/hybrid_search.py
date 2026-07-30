"""Hybrid Search RAG Engine combining BigQuery structured metrics and SEC 10-K text retrieval."""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from agent.rag.bigquery_store import BigQueryFinancialStore, FinancialMetricRecord
from agent.rag.sec_corpus import SECCorpusStore, SECDocumentChunk
from agent.observability.logging_config import log_tool_execution


class HybridSearchRequest(BaseModel):
    """Input request for hybrid search RAG engine."""

    query_type: str = Field(..., description="'variance_analysis', 'peer_comparison', or 'thematic_tracking'")
    primary_ticker: str = Field(..., description="Primary ticker symbol (e.g., AAPL).")
    secondary_tickers: List[str] = Field(default_factory=list, description="Secondary tickers for multi-company comparisons.")
    current_year: int = Field(2023, description="Current fiscal year.")
    prior_year: int = Field(2022, description="Prior fiscal year.")
    requested_years: List[int] = Field(default_factory=list, description="List of fiscal years for multi-year range queries (e.g., [2022, 2023, 2024]).")
    metric_name: str = Field("Revenue", description="Financial metric to analyze.")
    thematic_keyword: Optional[str] = Field(None, description="Keyword for longitudinal tracking (e.g., 'AI', 'R&D', 'supply chain').")


class HybridSearchResult(BaseModel):
    """Result returned by hybrid search engine."""

    is_success: bool
    query_type: str
    primary_metrics: List[FinancialMetricRecord] = Field(default_factory=list)
    secondary_metrics: List[FinancialMetricRecord] = Field(default_factory=list)
    text_chunks: List[SECDocumentChunk] = Field(default_factory=list)
    grounded_citations: List[str] = Field(default_factory=list)
    formatted_context_block: str = ""
    error: Optional[str] = None


class HybridSearchEngine:
    """Unified Hybrid Search RAG Engine combining BigQuery and SEC 10-K Corpus."""

    def __init__(self):
        self.bq_store = BigQueryFinancialStore()
        self.sec_corpus = SECCorpusStore()

    def execute_hybrid_search(self, request: HybridSearchRequest) -> HybridSearchResult:
        """Executes metadata-filtered hybrid search combining structured metrics and unstructured text.

        Args:
            request: HybridSearchRequest containing query parameters.

        Returns:
            HybridSearchResult with grounded citations and formatted context block.
        """
        log_tool_execution(
            tool_name="execute_hybrid_search",
            stage="intent",
            payload=request.model_dump(),
        )

        try:
            primary_records = []
            secondary_records = []
            text_chunks = []
            citations = []

            # 1. Fetch Primary Company Metrics from BigQuery for all target years
            target_years = request.requested_years if request.requested_years else [request.current_year, request.prior_year]
            for yr in sorted(target_years, reverse=True):
                rec = self.bq_store.query_metrics(request.primary_ticker, yr)
                if rec and rec not in primary_records:
                    primary_records.append(rec)

            # 2. Fetch Secondary Company Metrics if peer comparison
            for sec_t in request.secondary_tickers:
                for yr in sorted(target_years, reverse=True):
                    sec_rec = self.bq_store.query_metrics(sec_t, yr)
                    if sec_rec and sec_rec not in secondary_records:
                        secondary_records.append(sec_rec)

            # 3. Fetch SEC Document Chunks from Corpus
            if request.query_type == "thematic_tracking":
                kw = request.thematic_keyword or "AI"
                chunks = self.sec_corpus.search_chunks(keyword=kw)
                text_chunks.extend(chunks)
            else:
                for yr in target_years:
                    p_chunks = self.sec_corpus.search_chunks(ticker=request.primary_ticker, fiscal_year=yr)
                    text_chunks.extend(p_chunks)

                for sec_t in request.secondary_tickers:
                    sec_chunks = self.sec_corpus.search_chunks(ticker=sec_t)
                    text_chunks.extend(sec_chunks)

            # Extract Citations
            citations = [c.citation for c in text_chunks if c.citation]

            # Build Formatted Context Block for LLM Narrative Synthesis
            context_lines = []
            context_lines.append(f"### STRUCTURED FINANCIAL METRICS (BigQuery):")
            for rec in primary_records + secondary_records:
                context_lines.append(
                    f"- {rec.company_name} ({rec.ticker}) FY{rec.fiscal_year}: "
                    f"Revenue={rec.revenue}M USD, Operating Income={rec.operating_income}M USD, Net Income={rec.net_income}M USD"
                )

            context_lines.append(f"\n### UNSTRUCTURED 10-K FILING DISCLOSURES (SEC Corpus):")
            for chunk in text_chunks:
                context_lines.append(f"[{chunk.citation}]\n\"{chunk.content}\"")

            formatted_block = "\n".join(context_lines)

            result = HybridSearchResult(
                is_success=True,
                query_type=request.query_type,
                primary_metrics=primary_records,
                secondary_metrics=secondary_records,
                text_chunks=text_chunks,
                grounded_citations=citations,
                formatted_context_block=formatted_block,
            )

            log_tool_execution(
                tool_name="execute_hybrid_search",
                stage="outcome",
                payload={"query_type": request.query_type, "primary_count": len(primary_records), "chunks_count": len(text_chunks)},
                status="SUCCESS",
            )
            return result

        except Exception as err:
            log_tool_execution("execute_hybrid_search", "outcome", {"error": str(err)}, status="ERROR")
            return HybridSearchResult(
                is_success=False,
                query_type=request.query_type,
                error=str(err),
            )
