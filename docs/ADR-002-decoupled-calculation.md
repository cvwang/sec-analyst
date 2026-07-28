# ADR-002: Decoupled Deterministic Calculation Engine

## Status
**ACCEPTED** (June 13, 2026)

## Context
LLMs are probabilistic text predictors and frequently generate arithmetic errors (hallucinated math) when attempting to compute percentage variances or period-over-period differences in financial reports. Financial analysts require 100% numerical precision for Revenue, Operating Income, and Net Income.

## Decision
We decoupled all mathematical computations from the LLM narrative synthesis into a standalone, deterministic Python tool (`calculate_financial_variance`) enforced via strict Pydantic schemas (`VarianceRequest`, `VarianceResult`).

## Rationale
- **Zero Hallucination Tolerance**: Separating math from narrative synthesis guarantees 100% agreement between reported numbers and tool calculations.
- **Guided Error Recovery**: Pydantic wrappers catch division-by-zero or missing period data and return structured `recovery_instruction` hints.
- **Auditability**: All math outputs are logged with dual-stage intent/outcome traces in structured JSON logs.

## Consequences
- **Positive**: Achieved 100% accuracy on financial calculation evaluations against golden datasets.
- **Negative**: Adds a deterministic tool execution step in the agent workflow prior to LLM narrative generation.
