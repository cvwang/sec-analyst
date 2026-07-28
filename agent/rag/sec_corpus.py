"""SEC 10-K Document Corpus Store for Item 7 MD&A and Item 1A Risk Factors disclosures."""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class SECDocumentChunk(BaseModel):
    """Chunk of SEC 10-K filing text with metadata."""

    chunk_id: str
    ticker: str
    company_name: str
    fiscal_year: int
    section: str = "Item 7 - MD&A"  # "Item 7 - MD&A" or "Item 1A - Risk Factors"
    content: str
    citation: str
    keywords: List[str] = Field(default_factory=list)


SEC_10K_CORPUS: List[SECDocumentChunk] = [
    # AAPL Filings
    SECDocumentChunk(
        chunk_id="aapl_2024_mda",
        ticker="AAPL",
        company_name="Apple Inc.",
        fiscal_year=2024,
        section="Item 7 - MD&A",
        content="Apple Inc. FY2024 10-K: Total net sales reached $391,035 million, up 2.0% year-over-year. Services revenue expanded to an all-time record of $96,169 million driven by App Store and Cloud subscriptions. Research and Development (R&D) investments increased to $31,370 million, focusing heavily on Apple Intelligence and generative AI on-device chips.",
        citation="Apple Inc. FY2024 10-K Item 7 (MD&A, Page 28)",
        keywords=["services", "AI", "R&D", "hardware", "Apple Intelligence"],
    ),
    SECDocumentChunk(
        chunk_id="aapl_2023_mda",
        ticker="AAPL",
        company_name="Apple Inc.",
        fiscal_year=2023,
        section="Item 7 - MD&A",
        content="Apple Inc. FY2023 10-K: Total net sales were $383,285 million down 2.8% due to macroeconomic headwinds in hardware sales. Services net sales reached $85,200 million. R&D spend increased to $29,915 million as investments in custom silicon and machine learning accelerated.",
        citation="Apple Inc. FY2023 10-K Item 7 (MD&A, Page 31)",
        keywords=["macroeconomic", "silicon", "hardware", "R&D", "machine learning"],
    ),
    SECDocumentChunk(
        chunk_id="aapl_2022_mda",
        ticker="AAPL",
        company_name="Apple Inc.",
        fiscal_year=2022,
        section="Item 7 - MD&A",
        content="Apple Inc. FY2022 10-K: Total net sales reached a record $394,328 million driven by iPhone 14 momentum. R&D expenses were $26,251 million.",
        citation="Apple Inc. FY2022 10-K Item 7 (MD&A, Page 33)",
        keywords=["iPhone", "record sales", "hardware", "R&D"],
    ),

    # MSFT Filings
    SECDocumentChunk(
        chunk_id="msft_2024_mda",
        ticker="MSFT",
        company_name="Microsoft Corp",
        fiscal_year=2024,
        section="Item 7 - MD&A",
        content="Microsoft Corp FY2024 10-K: Total revenue grew 15.7% to $245,122 million. Intelligent Cloud revenue surged 20% to $105,362 million, powered by Azure OpenAI integration and enterprise AI transformation.",
        citation="Microsoft Corp FY2024 10-K Item 7 (MD&A, Page 35)",
        keywords=["Azure", "OpenAI", "Cloud", "AI transformation", "enterprise"],
    ),
    SECDocumentChunk(
        chunk_id="msft_2023_mda",
        ticker="MSFT",
        company_name="Microsoft Corp",
        fiscal_year=2023,
        section="Item 7 - MD&A",
        content="Microsoft Corp FY2023 10-K: Revenue increased 7% to $211,915 million driven by Intelligent Cloud expansion. R&D expenses were $27,195 million.",
        citation="Microsoft Corp FY2023 10-K Item 7 (MD&A, Page 37)",
        keywords=["Intelligent Cloud", "Azure", "R&D", "cloud expansion"],
    ),

    # NVDA Filings
    SECDocumentChunk(
        chunk_id="nvda_2025_mda",
        ticker="NVDA",
        company_name="NVIDIA Corp",
        fiscal_year=2025,
        section="Item 7 - MD&A",
        content="NVIDIA Corp FY2025 10-K: Revenue reached $126,048 million, up 107% year-over-year. Data Center compute revenue soared driven by Blackwell architecture and hyperscale AI infrastructure deployments.",
        citation="NVIDIA Corp FY2025 10-K Item 7 (MD&A, Page 40)",
        keywords=["Blackwell", "Data Center", "hyperscale", "AI infrastructure"],
    ),
    SECDocumentChunk(
        chunk_id="nvda_2024_mda",
        ticker="NVDA",
        company_name="NVIDIA Corp",
        fiscal_year=2024,
        section="Item 7 - MD&A",
        content="NVIDIA Corp FY2024 10-K: Revenue skyrocketed 126% to $60,922 million. Data Center revenue reached $47,525 million driven by Hopper GPU AI demand.",
        citation="NVIDIA Corp FY2024 10-K Item 7 (MD&A, Page 42)",
        keywords=["Hopper", "Data Center", "GPU", "AI demand"],
    ),

    # Thematic Risk Factors Disclosures (Item 1A)
    SECDocumentChunk(
        chunk_id="aapl_2024_risk",
        ticker="AAPL",
        company_name="Apple Inc.",
        fiscal_year=2024,
        section="Item 1A - Risk Factors",
        content="Apple Inc. FY2024 Risk Factors: Rapid development of generative AI technologies exposes the company to risks regarding model accuracy, data privacy compliance, supply chain dependencies on high-performance chips, and evolving global AI regulations.",
        citation="Apple Inc. FY2024 10-K Item 1A (Risk Factors, Page 14)",
        keywords=["AI risk", "generative AI", "privacy", "regulation", "supply chain"],
    ),
    SECDocumentChunk(
        chunk_id="nvda_2024_risk",
        ticker="NVDA",
        company_name="NVIDIA Corp",
        fiscal_year=2024,
        section="Item 1A - Risk Factors",
        content="NVIDIA Corp FY2024 Risk Factors: Concentrated demand for AI accelerators creates supply constraints for CoWoS packaging, trade restrictions on advanced chip exports, and rapid competitive technological obsolescence.",
        citation="NVIDIA Corp FY2024 10-K Item 1A (Risk Factors, Page 18)",
        keywords=["supply constraint", "CoWoS", "export restriction", "AI accelerator"],
    ),
]


class SECCorpusStore:
    """Document corpus store managing unstructured SEC 10-K chunks."""

    def search_chunks(
        self,
        ticker: Optional[str] = None,
        fiscal_year: Optional[int] = None,
        keyword: Optional[str] = None,
    ) -> List[SECDocumentChunk]:
        """Searches document corpus chunks using metadata filtering and keyword search."""
        matches = []
        for chunk in SEC_10K_CORPUS:
            if ticker and chunk.ticker.upper() != ticker.upper():
                continue
            if fiscal_year and chunk.fiscal_year != fiscal_year:
                continue
            if keyword:
                kw_lower = keyword.lower()
                content_lower = chunk.content.lower()
                kw_match = any(kw_lower in k.lower() for k in chunk.keywords) or (kw_lower in content_lower)
                if not kw_match:
                    continue
            matches.append(chunk)
        return matches
