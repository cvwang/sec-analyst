---
name: sec-edgar-analyst-requirements
description: Authoritative project requirements and architectural specification sources of truth for the SEC EDGAR Natural Language Analyst project.
---

# SEC EDGAR Analyst Project Requirements & Sources of Truth

Whenever analyzing requirements, evaluating proposed features, creating implementation plans, or refactoring code for this codebase, the agent MUST treat the following files as the absolute sources of truth:

1. [`FDE Onboarding Project.md`](file:///Users/cvwang/Documents/gcp/sec-edgar-analyst/FDE%20Onboarding%20Project.md): Project overview, core evaluation criteria, and sprint milestone deliverables.
2. [`fsi_scoping.md`](file:///Users/cvwang/Documents/gcp/sec-edgar-analyst/fsi_scoping.md): Financial Services Industry (FSI) scoping document detailing data sources (BigQuery + Vertex AI Search RAG), user personas, and target UI user journey.
3. [`fsi_tdd.md`](file:///Users/cvwang/Documents/gcp/sec-edgar-analyst/fsi_tdd.md): Technical Design Document (TDD) defining the agentic architecture, Google ADK supervisor pattern, security guardrails, OpenTelemetry tracing, and evaluation standards.

## Rule Guidelines
- All architectural decisions must align with Google Agent Development Kit (ADK) standards.
- Quantitative calculations must be performed deterministically via `agent/tools/calculation_engine.py`.
- Grounding citations must trace to SEC 10-K filing chunks and GCS URIs.
