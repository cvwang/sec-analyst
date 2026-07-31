"""SEC 10-K Document Corpus Store for Item 7 MD&A and Item 1A Risk Factors disclosures.

Grounded exclusively in Google Cloud Storage (gs://sec-analyst-sec-reports/filings/) and GCP Vertex AI Search.
Zero local disk dependencies.
"""

import os
from typing import List, Optional
from pydantic import BaseModel, Field
from agent.rag.vertex_search import VertexAISearchClient

GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME", "sec-analyst-sec-reports")


class SECDocumentChunk(BaseModel):
    """Chunk of SEC 10-K filing text with GCS grounding metadata."""

    chunk_id: str
    ticker: str
    company_name: str
    fiscal_year: int
    section: str = "Item 7 - MD&A"  # "Item 7 - MD&A" or "Item 1A - Risk Factors"
    content: str
    citation: str
    gcs_uri: str
    keywords: List[str] = Field(default_factory=list)


class SECCorpusStore:
    """Document corpus store managing SEC 10-K disclosures grounded exclusively in GCP Vertex AI Search."""

    def __init__(self):
        self.vertex_search = VertexAISearchClient(datastore_id="sec-10k-filings-datastore")

    def search_chunks(
        self,
        ticker: Optional[str] = None,
        fiscal_year: Optional[int] = None,
        keyword: Optional[str] = None,
        requested_years: Optional[List[int]] = None,
    ) -> List[SECDocumentChunk]:
        """Searches document corpus chunks strictly via Vertex AI Search DataStore."""
        target_years = requested_years if requested_years else ([fiscal_year] if fiscal_year else None)

        q_terms = []
        if ticker:
            q_terms.append(ticker)
        if target_years:
            q_terms.extend([str(y) for y in target_years])
        if keyword:
            q_terms.append(keyword)
        query_str = " ".join(q_terms) if q_terms else "SEC 10-K filings"

        vertex_results = self.vertex_search.search_filings(query_str, page_size=5)
        v_chunks = []
        for vr in vertex_results:
            v_chunks.append(
                SECDocumentChunk(
                    chunk_id=vr.id,
                    ticker=ticker or "SEC",
                    company_name=f"{ticker or 'SEC'} Corp",
                    fiscal_year=fiscal_year or 2023,
                    section="Item 7 - MD&A",
                    content=vr.snippet,
                    citation=f"Vertex AI Search ({self.vertex_search.datastore_id}) [{vr.gcs_uri}]",
                    gcs_uri=vr.gcs_uri,
                )
            )
        return v_chunks


def search_sec_filing_chunks_tool(ticker: str = "", fiscal_year: int = 0, keyword: str = "") -> list:
    """Searches unstructured SEC 10-K filing disclosures (MD&A and Risk Factors) grounded in GCS for a given ticker, fiscal year, or keyword.

    Args:
        ticker: Ticker symbol (e.g. AAPL, MSFT, NVDA).
        fiscal_year: Target fiscal year (e.g. 2022, 2023, 2024).
        keyword: Keyword filter (e.g. 'AI', 'supply chain', 'inflation').
    """
    store = SECCorpusStore()
    yr = fiscal_year if fiscal_year > 0 else None
    chunks = store.search_chunks(ticker=ticker or None, fiscal_year=yr, keyword=keyword or None)
    return [c.model_dump() for c in chunks]
