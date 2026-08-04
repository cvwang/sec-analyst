---
name: fsi-grounding-citation-pipeline
description: Best practices and mandatory guidelines for RAG retrieval, structured metadata extraction, and 100% grounded split-pane citation rendering in financial analyst applications.
---

# FSI Grounding & Citation Pipeline Skill

## Overview
This skill defines standard patterns for building financial domain RAG retrieval systems that demand 100% factual accuracy, zero math hallucinations, and precise document citation attribution.

## Key Design Patterns

### 1. Separation of Quantitative & Qualitative Engines
- **Quantitative Line Items (Revenue, Operating Income, Net Income)**: Derived exclusively from deterministic calculation engines or BigQuery structured metric tables (`sec_edgar_financials.financial_metrics`). Never permit LLMs to calculate financial deltas in prompt context.
- **Qualitative Disclosures (MD&A, Risk Factors)**: Retrieved via Vertex AI Search (`types.Retrieval`) querying unabridged 10-K document chunks stored in GCS.

### 2. Structured Metadata & Citation Payload
RAG search tools MUST return structured chunk objects rather than raw unformatted text strings. Every chunk MUST populate:
- `content`: Real unabridged filing snippet.
- `ticker`: Target company symbol (e.g. `TSLA`, `NVDA`).
- `fiscal_year`: Target filing fiscal year.
- `section`: SEC filing section (e.g., `Item 7 - MD&A`, `Item 1A - Risk Factors`).
- `gcs_uri`: Source Google Cloud Storage URI (`gs://sec-analyst-sec-reports/filings/...`).
- `citation`: Formatted citation string (`Vertex AI Search (sec-10k-filings-datastore) [gs://...]`).

### 3. Optimal Vertex AI Search Query Formulation
Formulate search queries combining **Metadata Anchors** + **Cleaned Natural Language Intent**:
- Format: `<Ticker> <Fiscal Period/Section> <Cleaned Natural Intent>`
- Example: `"TSLA 2023 Item 1A Risk Factors business operational challenges competition"`
- Preamble Stripping: Strip conversational noise (`"Can you please explain..."`, `"Tell me..."`) to preserve dense embedding vector similarity weights.

### 4. Focused Entity Tooling & Parallel Model Execution
- Design RAG tools with single-entity input signatures (`ticker: str`, `requested_years: List[int]`).
- Rely on Gemini's native parallel tool calling capability to execute concurrent searches for peer comparison queries across multiple entities.
