# SEC EDGAR Natural Language Analyst (FDE Capstone Project)

An agentic financial analyst system designed to automate period-over-period financial variance analysis (Revenue, Operating Income, Net Income) and perform longitudinal thematic tracking across SEC 10-K filings.

## Architecture Overview
- **Orchestration:** Google Agent Development Kit (ADK) `RootOrchestrator` & `FinancialAnalystAgent`.
- **Model Routing:** Gemini 2.5 Pro (financial reasoning & synthesis) vs. Gemini 3.5 Flash (metric lookup, tool calling, evaluation).
- **Calculation Engine:** Deterministic variance calculation engine for quantitative accuracy.
- **Context & Memory:** Gemini Context Caching for 10-K filings and financial analyst system constitution.
- **Observability:** OpenTelemetry / Cloud Trace integration with structured JSON logging and PII scrubbing.
- **Evaluation & IaC:** Pytest test harness against a golden dataset (`golden_dataset.json`) and Terraform configurations.

---

## Folder Structure
```
.
├── README.md
├── SPECIFICATION.md
├── agent/
│   ├── __init__.py
│   ├── config.py
│   ├── constitution.py
│   ├── orchestrator.py
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── calculation_engine.py
│   │   └── sec_retriever.py
│   ├── memory/
│   │   └── cache_manager.py
│   ├── guardrails/
│   │   └── pii_scrubber.py
│   └── observability/
│       ├── logging_config.py
│       └── tracer.py
├── eval/
│   ├── golden_dataset.json
│   └── test_eval_harness.py
├── terraform/
│   ├── main.tf
│   └── variables.tf
├── .env.example
└── requirements.txt
```
