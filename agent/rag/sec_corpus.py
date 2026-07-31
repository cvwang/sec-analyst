"""SEC 10-K Document Corpus Store for Item 7 MD&A and Item 1A Risk Factors disclosures.

Grounded in Google Cloud Storage (gs://sec-analyst-sec-reports/filings/).
"""

import os
import glob
from typing import List, Optional
from pydantic import BaseModel, Field

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "10k_filings")
GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME", "sec-analyst-sec-reports")
GCS_PREFIX = "filings/"


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


def parse_filename_to_chunk(filename: str, content: str, gcs_uri: str) -> Optional[SECDocumentChunk]:
    """Parses filename and content string into SECDocumentChunk with GCS URI grounding."""
    parts = filename.replace(".md", "").split("_")
    if len(parts) < 4:
        return None

    ticker = parts[0].upper()
    try:
        fiscal_year = int(parts[1])
    except ValueError:
        return None

    item_str = "_".join(parts[2:])
    section = "Item 7 - MD&A" if "Item7" in item_str else "Item 1A - Risk Factors"

    company_names = {
        "AAPL": "Apple Inc.",
        "MSFT": "Microsoft Corp",
        "NVDA": "NVIDIA Corp",
        "GOOGL": "Alphabet Inc.",
        "AMZN": "Amazon.com Inc.",
        "TSLA": "Tesla, Inc.",
        "META": "Meta Platforms, Inc.",
        "AMD": "Advanced Micro Devices",
        "JPM": "JPMorgan Chase & Co.",
        "WMT": "Walmart Inc.",
    }
    company_name = company_names.get(ticker, f"{ticker} Inc.")
    chunk_id = f"{ticker.lower()}_{fiscal_year}_{parts[2].lower()}"
    section_short = "Item 7 (MD&A)" if "Item7" in item_str else "Item 1A (Risk Factors)"
    citation = f"{company_name} FY{fiscal_year} 10-K {section_short} [{gcs_uri}]"

    keywords = [ticker, str(fiscal_year), section]
    if "AI" in content or "generative" in content or "copilot" in content.lower():
        keywords.append("AI")
    if "cloud" in content.lower() or "azure" in content.lower() or "aws" in content.lower():
        keywords.append("cloud")
    if "revenue" in content.lower() or "sales" in content.lower() or "income" in content.lower():
        keywords.append("revenue")

    return SECDocumentChunk(
        chunk_id=chunk_id,
        ticker=ticker,
        company_name=company_name,
        fiscal_year=fiscal_year,
        section=section,
        content=content,
        citation=citation,
        gcs_uri=gcs_uri,
        keywords=keywords,
    )


def load_markdown_corpus() -> List[SECDocumentChunk]:
    """Loads 10-K Markdown filing files, explicitly grounded in GCS bucket gs://sec-analyst-sec-reports/filings/."""
    chunks = []
    if not os.path.exists(DATA_DIR):
        return chunks

    md_files = glob.glob(os.path.join(DATA_DIR, "*.md"))
    for file_path in md_files:
        filename = os.path.basename(file_path)
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read().strip()
        gcs_uri = f"gs://{GCS_BUCKET_NAME}/{GCS_PREFIX}{filename}"
        chunk = parse_filename_to_chunk(filename, content, gcs_uri)
        if chunk:
            chunks.append(chunk)

    print(f"🚀 Loaded {len(chunks)} unabridged SEC 10-K Markdown chunks grounded in GCS (gs://{GCS_BUCKET_NAME}/{GCS_PREFIX})")
    return chunks


# Global SEC 10-K Markdown corpus instance
SEC_10K_CORPUS: List[SECDocumentChunk] = load_markdown_corpus()


from agent.rag.vertex_search import VertexAISearchClient


class SECCorpusStore:
    """Document corpus store managing unabridged SEC 10-K Markdown chunks grounded in GCP Vertex AI Search and GCS."""

    def __init__(self):
        self.corpus = load_markdown_corpus()
        self.vertex_search = VertexAISearchClient(datastore_id="sec-10k-filings-datastore")

    def search_chunks(
        self,
        ticker: Optional[str] = None,
        fiscal_year: Optional[int] = None,
        keyword: Optional[str] = None,
        requested_years: Optional[List[int]] = None,
    ) -> List[SECDocumentChunk]:
        """Searches document corpus chunks via Vertex AI Search DataStore with metadata corpus fallback."""
        target_years = requested_years if requested_years else ([fiscal_year] if fiscal_year else None)

        # 1. Attempt GCP Vertex AI Search DataStore query
        if ticker or keyword:
            q_terms = []
            if ticker:
                q_terms.append(ticker)
            if target_years:
                q_terms.extend([str(y) for y in target_years])
            if keyword:
                q_terms.append(keyword)
            query_str = " ".join(q_terms)

            try:
                vertex_results = self.vertex_search.search_filings(query_str, page_size=5)
                if vertex_results:
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
                    if v_chunks:
                        return v_chunks
            except Exception:
                pass

        # 2. Metadata-filtered corpus search fallback
        matches = []
        for chunk in self.corpus:
            if ticker and chunk.ticker.upper() != ticker.upper():
                continue
            if target_years and chunk.fiscal_year not in target_years:
                continue
            if keyword:
                kw_lower = keyword.lower()
                content_lower = chunk.content.lower()
                kw_match = any(kw_lower in k.lower() for k in chunk.keywords) or (kw_lower in content_lower)
                if not kw_match:
                    continue
            matches.append(chunk)
        return matches
