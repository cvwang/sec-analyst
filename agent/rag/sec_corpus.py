"""SEC 10-K Document Corpus Store for Item 7 MD&A and Item 1A Risk Factors disclosures.

Grounded exclusively in Google Cloud Storage (gs://sec-analyst-sec-reports/filings/) and GCP Vertex AI Search.
Zero local disk dependencies.
"""

import os
import re
import logging
from typing import List, Optional
from pydantic import BaseModel, Field
from agent.rag.vertex_search import VertexAISearchClient

GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME", "sec-analyst-sec-reports")

_request_grounded_chunks: List[dict] = []


def reset_grounded_chunks():
    global _request_grounded_chunks
    _request_grounded_chunks = []


def get_grounded_chunks() -> List[dict]:
    global _request_grounded_chunks
    return list(_request_grounded_chunks)


def add_grounded_chunks(chunks: List[dict]):
    global _request_grounded_chunks
    _request_grounded_chunks.extend(chunks)


def annotate_text_with_clauses(content: str, marked_clauses: list) -> str:
    """Wraps exact or matching sentence blocks in <mark> tags inside content."""
    if not content or not marked_clauses:
        return content

    annotated = content
    for clause in marked_clauses:
        clause_clean = clause.strip()
        if not clause_clean or len(clause_clean) < 8:
            continue

        if clause_clean in annotated:
            annotated = annotated.replace(clause_clean, f"<mark>{clause_clean}</mark>")
            continue

        # Try sentence-level matching if Gemini modified minor words
        sentences = re.split(r'(?<=[.!?])\s+', annotated)
        for s in sentences:
            s_clean = s.strip()
            if not s_clean or len(s_clean) < 15 or "<mark>" in s:
                continue

            words = [w for w in re.findall(r'\b[A-Za-z0-9\$\.]+\b', clause_clean) if len(w) > 3]
            match_count = sum(1 for w in words if w in s_clean)
            if words and (match_count / len(words)) >= 0.5:
                annotated = annotated.replace(s_clean, f"<mark>{s_clean}</mark>")
                break

    return annotated


def annotate_grounded_highlights_with_llm(chunks: List[dict], narrative: str) -> List[dict]:
    """Uses Vertex AI (Gemini Flash) in parallel to identify exact supporting sentence blocks and wrap them in <mark> tags."""
    if not chunks or not narrative:
        return chunks

    import concurrent.futures

    try:
        from google import genai
        from agent.config import settings

        client = genai.Client()
        fast_model = getattr(settings, "fast_model", "gemini-2.5-flash")

        def _annotate_single_chunk(chunk: dict) -> dict:
            raw_text = chunk.get("content", "")
            if not raw_text:
                return chunk

            prompt = f"""You are an SEC filing grounding specialist. Given the following SEC 10-K filing excerpt and an AI Analyst Narrative response, identify the exact 1-3 key sentence blocks or verbatim clauses from the SEC 10-K filing excerpt that directly substantiate or ground the claims in the narrative.

Return the SEC 10-K filing excerpt with those exact supporting sentence blocks enclosed inside <mark> and </mark> tags. Do not alter any words in the filing text. Return ONLY the annotated excerpt text.

SEC 10-K FILING EXCERPT:
{raw_text[:2500]}

ANALYST NARRATIVE:
{narrative[:1500]}
"""

            try:
                response = client.models.generate_content(
                    model=fast_model,
                    contents=prompt,
                )

                if response and response.text:
                    annotated = response.text.strip()
                    if "<mark>" in annotated:
                        chunk["highlight_excerpt"] = annotated
                        # Annotate full content so highlights persist in expanded view
                        marked_clauses = re.findall(r'<mark>(.*?)</mark>', annotated, flags=re.DOTALL)
                        chunk["content"] = annotate_text_with_clauses(chunk["content"], marked_clauses)
                    else:
                        chunk["highlight_excerpt"] = f"<mark>{annotated[:350]}</mark>"
            except Exception as e:
                logging.warning(f"Single chunk annotation error: {e}")
                if not chunk.get("highlight_excerpt"):
                    chunk["highlight_excerpt"] = raw_text[:350]

            return chunk

        with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(chunks), 5)) as executor:
            annotated_chunks = list(executor.map(_annotate_single_chunk, chunks))

        return annotated_chunks
    except Exception as err:
        logging.warning(f"LLM grounded highlighting fallback: {err}")
        for chunk in chunks:
            if not chunk.get("highlight_excerpt"):
                chunk["highlight_excerpt"] = chunk.get("content", "")[:350]

    return chunks


def extract_relevant_excerpt(raw_content: str, query_context: str = "") -> str:
    """Extracts a focused 200-350 character relevant snippet around key financial/risk terms."""
    if not raw_content:
        return ""

    # Clean out heavy SEC headers and GCS file preambles
    clean = re.sub(r'#+\s*(?:REAL UNABRIDGED|Source URL|Section:)[^\n]*\n?', '', raw_content)
    clean = re.sub(r'https?://[^\s]+', '', clean)
    clean = re.sub(r'&\#\d+;', ' ', clean)
    clean = re.sub(r'\s+', ' ', clean).strip()

    if len(clean) <= 300:
        return clean

    # Look for sentences containing financial/analytical terms
    keywords = ["revenue", "margin", "gross", "operating", "expense", "r&d", "sg&a", "risk", "increase", "decrease", "profit", "cash"]
    if query_context:
        extra_terms = [w.lower() for w in re.findall(r'\b[A-Za-z]{3,}\b', query_context) if w.lower() not in ["the", "and", "for", "with", "that", "this"]]
        keywords.extend(extra_terms)

    sentences = re.split(r'(?<=[.!?])\s+', clean)
    best_sentences = []
    current_len = 0

    for s in sentences:
        s_lower = s.lower()
        if any(k in s_lower for k in keywords):
            best_sentences.append(s)
            current_len += len(s)
            if current_len >= 250:
                break

    if best_sentences:
        return " ".join(best_sentences)[:400]

    # Fallback to first 300 characters of cleaned text
    return clean[:300] + "..."


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
    highlight_excerpt: str = ""
    citation: str
    gcs_uri: str
    keywords: List[str] = Field(default_factory=list)


def clean_sec_document_text(raw_text: str) -> str:
    """Strips redundant header preambles, section banners, URLs, and HTML entities while preserving paragraph breaks."""
    if not raw_text:
        return ""

    text = raw_text

    # 1. Decode HTML entities
    text = re.sub(r'&\#8212;', ' — ', text)
    text = re.sub(r'&\#8211;', ' – ', text)
    text = re.sub(r'&\#8220;', '"', text)
    text = re.sub(r'&\#8221;', '"', text)
    text = re.sub(r'&\#8217;', "'", text)
    text = re.sub(r'&\#\d+;', ' ', text)
    text = re.sub(r'&amp;', '&', text)

    # 2. Strip dataset markdown headers and URLs
    text = re.sub(r'#+\s*REAL UNABRIDGED SEC EDGAR FILING:[^#\n]*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'#+\s*Source URL:\s*https?://[^\s]*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'#+\s*Section:\s*Item[^\n]*?(?=(?:ITEM\s+[0-9A-Z]+|The\s+following|You\s+should|[A-Z][a-z]+))', '', text, flags=re.IGNORECASE)

    # 3. Strip redundant section title banners
    text = re.sub(r'ITEM\s+7\.\s+MANAGEMENT\'S\s+DISCUSSION\s+AND\s+ANALYSIS(?:\s+OF\s+FINANCIAL\s+CONDITION\s+AND\s+RESULTS\s+OF\s+OPERATIONS)?', '', text, flags=re.IGNORECASE)
    text = re.sub(r'Management\'s\s+Discussion\s+and\s+Analysis(?:\s+\([^\)]*\))?', '', text, flags=re.IGNORECASE)
    text = re.sub(r'ITEM\s+1A\.\s+RISK\s+FACTORS', '', text, flags=re.IGNORECASE)

    # 4. 100% Generic paragraph boundary separation (separate period-to-capital concatenations)
    text = re.sub(r'([.!?])([A-Z][a-z]{2,})', r'\1\n\n\2', text)

    # 5. Normalize newlines: collapse 3+ newlines to double newline
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'^\s*[#\s\-:=]+', '', text).strip()
    return text


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
            uri_match = re.search(r'/([A-Z0-9]+)_(\d{4})_', vr.gcs_uri)
            extracted_ticker = ticker or (uri_match.group(1) if uri_match else "SEC")
            extracted_year = (target_years[0] if (target_years and len(target_years) > 0) else None) or (int(uri_match.group(2)) if uri_match else 2023)

            doc_meta_lower = (vr.gcs_uri + " " + vr.title).lower()
            if "item1a" in doc_meta_lower or "item 1a" in doc_meta_lower or "item1a_risk" in doc_meta_lower:
                sec_section = "Item 1A - Risk Factors"
            elif "item7" in doc_meta_lower or "item 7" in doc_meta_lower or "item7_mda" in doc_meta_lower:
                sec_section = "Item 7 - MD&A"
            elif "risk" in doc_meta_lower:
                sec_section = "Item 1A - Risk Factors"
            else:
                sec_section = "Item 7 - MD&A"

            cleaned_content = clean_sec_document_text(vr.snippet)
            excerpt = extract_relevant_excerpt(cleaned_content, query_str)

            v_chunks.append(
                SECDocumentChunk(
                    chunk_id=vr.id,
                    ticker=extracted_ticker,
                    company_name=f"{extracted_ticker} Corp",
                    fiscal_year=extracted_year,
                    section=sec_section,
                    content=cleaned_content,
                    highlight_excerpt=excerpt,
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
    dumped = [c.model_dump() for c in chunks]
    add_grounded_chunks(dumped)
    return dumped
