"""SEC 10-K Document Corpus Store for Item 7 MD&A and Item 1A Risk Factors disclosures.

Grounded exclusively in Google Cloud Storage (gs://sec-analyst-sec-reports/filings/) and GCP Vertex AI Search.
Zero local disk dependencies.
"""

import os
import re
from typing import List, Optional
from pydantic import BaseModel, Field
from agent.rag.vertex_search import VertexAISearchClient

GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME", "sec-analyst-sec-reports")


def formulate_vertex_search_query(
    query: str = "",
    ticker: Optional[str] = None,
    requested_years: Optional[List[int]] = None,
    fiscal_year: Optional[int] = None,
    keyword: Optional[str] = None,
) -> str:
    """Formulates an optimized hybrid search query string combining metadata anchor terms and semantic intent."""
    terms = []
    if ticker:
        terms.append(ticker.upper())

    target_years = requested_years if requested_years else ([fiscal_year] if fiscal_year else None)
    if target_years:
        terms.extend([str(y) for y in target_years])

    clean_query = ""
    if query:
        # Strip conversational preamble noise (e.g. "Can you please explain to me what...", "Please show me...")
        clean_query = re.sub(
            r'^(?:can you|please|could you|explain|tell me|show me|what are|what is|how did|describe|to me|\s+)+',
            '',
            query.strip(),
            flags=re.IGNORECASE,
        ).strip()

    if clean_query:
        terms.append(clean_query)
    elif keyword:
        terms.append(keyword)

    return " ".join(terms) if terms else "SEC 10-K filings"


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
        query_str: str = "",
        ticker: Optional[str] = None,
        requested_years: Optional[List[int]] = None,
        fiscal_year: Optional[int] = None,
        keyword: Optional[str] = None,
    ) -> List[SECDocumentChunk]:
        """Searches document corpus chunks strictly via Vertex AI Search DataStore using formulated hybrid queries."""
        search_query = formulate_vertex_search_query(
            query=query_str,
            ticker=ticker,
            requested_years=requested_years,
            fiscal_year=fiscal_year,
            keyword=keyword,
        )

        vertex_results = self.vertex_search.search_filings(search_query, page_size=5)
        v_chunks = []
        target_years = requested_years if requested_years else ([fiscal_year] if fiscal_year else None)
        for vr in vertex_results:
            v_chunks.append(
                SECDocumentChunk(
                    chunk_id=vr.id,
                    ticker=ticker or "SEC",
                    company_name=f"{ticker or 'SEC'} Corp",
                    fiscal_year=target_years[0] if (target_years and len(target_years) > 0) else 2023,
                    section="Item 7 - MD&A",
                    content=vr.snippet,
                    citation=f"Vertex AI Search ({self.vertex_search.datastore_id}) [{vr.gcs_uri}]",
                    gcs_uri=vr.gcs_uri,
                )
            )
        return v_chunks


def search_sec_filing_chunks_tool(
    query: str = "",
    ticker: str = "",
    requested_years: List[int] = [],
) -> list:
    """Searches unstructured SEC 10-K filing disclosures (MD&A and Risk Factors) grounded in GCS using Vertex AI Search.

    Args:
        query: Topic, keywords, or natural language query (e.g., 'Tesla business risks', 'Nvidia AI R&D spend').
        ticker: Target ticker symbol (e.g. AAPL, MSFT, NVDA, TSLA).
        requested_years: List of target fiscal years (e.g., [2023] or [2022, 2023, 2024]).
    """
    store = SECCorpusStore()

    chunks = store.search_chunks(
        query_str=query,
        ticker=ticker or None,
        requested_years=requested_years or None,
    )
    return [c.model_dump() for c in chunks]
