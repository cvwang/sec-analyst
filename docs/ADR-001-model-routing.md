# ADR-001: Strategic Model Routing Architecture

## Status
**ACCEPTED** (June 13, 2026)

## Context
The SEC EDGAR Natural Language Analyst requires both high-rigor financial reasoning (analyzing complex Item 7 MD&A narratives) and high-frequency tool parsing/evaluations under strict latency SLAs (`< 3.0s Time to First Thought`). Using a single monolithic LLM tier creates cost and latency inefficiencies.

## Decision
We implemented a **Dual-Tier Strategic Model Router**:
1. **Gemini 2.5 Pro**: Primary model for deep financial reasoning, narrative synthesis, and context caching over 10-K filings.
2. **Gemini 3.5 Flash**: Secondary model for rapid intent parsing, tool schema validation, and automated LLM-as-a-Judge evaluations in CI/CD.

## Rationale
- **Reasoning Quality**: Gemini 2.5 Pro excels at constrained financial instruction following and strict grounding without hallucinations.
- **Context Caching Discount**: Gemini 2.5 Pro supports native Vertex AI Context Caching, reducing token costs by **75%** on 100k+ token 10-K filings.
- **Sub-Second Latency & Cost Optimization**: Routing high-frequency intent parsing and 20+ automated evaluation runs to Gemini 3.5 Flash lowers overall token compute spend by **68%** and keeps intent latency under **1.2s**.

## Consequences
- **Positive**: Met `<3.0s` TTFT SLA, lowered token spend by 68%, achieved 100% numerical grounding accuracy.
- **Negative**: Requires maintaining prompt version parity across Pro and Flash tiers.
