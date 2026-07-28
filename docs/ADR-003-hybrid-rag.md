# ADR-003: Hybrid Search RAG Architecture

## Status
**ACCEPTED** (June 13, 2026)

## Context
Analysts need to execute natural language queries across both structured financial metrics (Revenue, Operating Income, Net Income over 2020-2026) and unstructured SEC 10-K text disclosures (Item 7 MD&A and Item 1A Risk Factors) for longitudinal thematic tracking (e.g. AI risk disclosures).

## Decision
We implemented a unified **Hybrid RAG Layer** combining **BigQuery** (for structured SQL metric filtering) and **Vertex AI Search / SEC Corpus** (for unstructured document chunk retrieval with metadata filtering).

## Rationale
- **Unified Retrieval**: Combines quantitative grounding facts from BigQuery with qualitative narrative excerpts from 10-K filings.
- **Architectural Efficiency**: Avoided redundant low-level raw Vector Search index maintenance by leveraging Vertex AI Search's managed hybrid search engine.
- **Precision Citation**: Every retrieved text chunk carries explicit metadata (`citation`), allowing inline source links in the split-pane frontend.

## Consequences
- **Positive**: Supported multi-company peer comparisons and multi-period thematic tracking with full citation traceability.
- **Negative**: Requires maintaining metadata schema synchronization between BigQuery metric tables and SEC text chunk stores.
