# SEC EDGAR Natural Language Analyst - System Architecture

This document provides the complete, authoritative architectural specification for the **SEC EDGAR Natural Language Analyst**, detailing component interactions, grounded RAG retrieval pathways, model routing strategy, and execution sequences.

---

## 1. High-Level System Architecture Flowchart

```mermaid
flowchart TB
    %% Styling Rules
    classDef client fill:#1e293b,stroke:#38bdf8,stroke-width:2px,color:#f8fafc;
    classDef compute fill:#0f172a,stroke:#818cf8,stroke-width:2px,color:#f8fafc;
    classDef model fill:#1e1b4b,stroke:#c084fc,stroke-width:2px,color:#f8fafc;
    classDef data fill:#064e3b,stroke:#34d399,stroke-width:2px,color:#f8fafc;
    classDef obs fill:#451a03,stroke:#fb923c,stroke-width:2px,color:#f8fafc;

    subgraph ClientLayer ["🖥️ Presentation Layer (Client)"]
        UI["React 18 / TypeScript / Vite / Tailwind UI<br/>(Split-Pane Dashboard & Grounded Citation Viewer)"]:::client
    end

    subgraph BackendLayer ["⚡ Compute & Service Layer (Google Cloud Run / FastAPI)"]
        API["FastAPI REST Web Server<br/>(agent/main.py & agent/orchestrator.py)"]:::compute
        
        subgraph AgenticCore ["🧠 Agentic Control & Memory Core"]
            OR["RootOrchestrator<br/>(Intent Parser & Agent Dispatcher)"]:::compute
            Agent["FinancialAnalystAgent<br/>(Reasoning & Narrative Synthesis)"]:::compute
            CacheMgr["Context Cache Manager<br/>(agent/memory/cache_manager.py)"]:::compute
            MemStore["Persistent Session Store<br/>(agent_sessions.json / HistoryCompactor)"]:::compute
        end

        subgraph CalculationEngine ["🧮 Decoupled Deterministic Math Engine"]
            CE["Variance Engine Tool<br/>(agent/tools/calculation_engine.py)"]:::compute
        end

        subgraph GuardrailModule ["🛡️ Guardrails & Safety"]
            PII["PII Scrubber & Prompt Sanitizer<br/>(agent/guardrails/pii_scrubber.py → GCP Model Armor Roadmap)"]:::compute
        end
    end

    subgraph ModelRoutingLayer ["🤖 Model Routing & LLM Layer"]
        ProModel["Gemini 2.5 Pro<br/>(Financial Reasoning & Native Function Calling)"]:::model
    end

    subgraph RAGLayer ["🗄️ Hybrid Search RAG Layer"]
        BQ_Metric["BigQuery Structured Financial Store<br/>(agent/rag/bigquery_store.py)"]:::data
        DiscoveryEngine["Vertex AI Search Datastore<br/>(google-cloud-discoveryengine SDK Tool)"]:::data
        SEC_Corpus["SEC 10-K Corpus Store<br/>(120 Grounded Filings in gs://sec-analyst-sec-reports/filings/)"]:::data
    end

    subgraph ObservabilityLayer ["📊 Observability & Telemetry"]
        OTEL["OpenTelemetry Tracer<br/>(agent/observability/tracer.py)"]:::obs
        JSONLogs["Structured Event Logger<br/>(agent/observability/logging_config.py)"]:::obs
    end

    %% Flow Connections
    UI -->|"1. Submit Query / Ticker Prompt"| API
    API -->|"2. Intercept & Redact PII"| PII
    PII -->|"3. Parse Intent & Route Query"| OR
    
    OR -->|"4. Execute Hybrid Search RAG"| BQ_Metric
    OR -->|"4. Search 10-K Filings"| DiscoveryEngine
    DiscoveryEngine -.->|"Datastore Search / Corpus Retrieval"| SEC_Corpus
    
    OR -->|"5. Execute Deterministic Math Tool"| CE
    CE -->|"6. Return 100% Precise Variance Metrics"| OR
    
    OR -->|"7. Manage Multi-turn Session & Memory"| CacheMgr
    CacheMgr <-->|"Load/Save Session Turns"| MemStore
    
    OR -->|"8. Dispatch Prompt + RAG Context + Math"| ProModel
    ProModel -->|"9. Synthesize Executive Narrative + Citations"| Agent
    
    Agent -->|"10. Deliver Grounded Result JSON"| API
    API -->|"11. Render Split-Pane Dashboard"| UI
    
    API -.->|"Telemetry Spans"| OTEL
    API -.->|"Intent & Outcome Events"| JSONLogs
```

---

## 2. Step-by-Step Execution Sequence Diagram

```mermaid
sequenceDiagram
    autonumber
    actor Analyst as Financial Analyst
    participant UI as React 18 UI (Client)
    participant API as FastAPI Server (Cloud Run)
    participant PII as PII Scrubber Guardrail
    participant Orchestrator as RootOrchestrator
    participant RAG as Hybrid Search Engine (BQ + SEC 10-K)
    participant Math as Deterministic Math Engine
    participant LLM as Gemini 2.5 Pro Model

    Analyst->>UI: Submit Financial Prompt (e.g., "Analyze Meta risk factors disclosure")
    UI->>API: POST /api/v1/analyze (User Query)
    
    rect rgb(15, 23, 42)
        Note over API, PII: Phase 1: Security & Guardrail Interception
        API->>PII: Sanitize Prompt (Redact SSNs, Emails, API Keys)
        PII-->>API: Clean Prompt
    end

    rect rgb(30, 27, 75)
        Note over API, Orchestrator: Phase 2: Intent Parsing & Routing
        API->>Orchestrator: dispatch_query(user_prompt)
        Orchestrator->>Orchestrator: parse_natural_language_intent() → QueryType, Tickers, Years, Keywords
    end

    rect rgb(6, 78, 59)
        Note over Orchestrator, RAG: Phase 3: Grounded RAG & Tool Execution
        Orchestrator->>RAG: execute_hybrid_search(HybridSearchRequest)
        RAG->>RAG: Fetch BigQuery Golden Metrics & SEC 10-K Chunks
        RAG-->>Orchestrator: Grounded RAG Result (Bounded Chunks <= 10)
        
        opt Quantitative Variance Query
            Orchestrator->>Math: calculate_financial_variance_tool(ticker, metric, current, prior)
            Math-->>Orchestrator: Exact Variance Result (100% Precision)
        end
    end

    rect rgb(69, 26, 3)
        Note over Orchestrator, LLM: Phase 4: Gemini 2.5 Pro Narrative Synthesis
        Orchestrator->>LLM: generate_content(System Instructions + Grounded Context + Tools)
        LLM-->>Orchestrator: Synthesized Narrative + Citations + KPI Metrics
    end

    Orchestrator-->>API: Return Unified Dispatch Result JSON
    API-->>UI: Return HTTP 200 (Narrative, KPI Cards, Grounded SEC Citations)
    UI->>Analyst: Render Executive Report & Grounded 10-K Source Viewer
```

---

## 3. Subagent & Data Retrieval Pipeline

```mermaid
graph TD
    subgraph RequestPipeline ["📥 User Request Processing"]
        Query["User Query Prompt"] --> IntentParser["parse_natural_language_intent()"]
        IntentParser --> IntentType{"Query Intent Type"}
    end

    subgraph RAGRouting ["🔀 Hybrid RAG Data Routing"]
        IntentType -->|"variance_analysis"| BQ1["BigQuery Financial Store<br/>(Structured Metrics)"]
        IntentType -->|"peer_comparison"| BQ2["BigQuery Multi-Ticker Metrics"]
        IntentType -->|"thematic_tracking"| SECCorpus["SEC 10-K Corpus Store<br/>(Item 1A Risk & Item 7 MD&A)"]
    end

    subgraph DataSources ["🗄️ Storage & Grounding Layer"]
        BQ1 --> BQTable[("BigQuery Dataset<br/>sec_financial_analytics")]
        BQ2 --> BQTable
        SECCorpus --> DiscoveryTool["vertex_ai_search_datastore_tool"]
        DiscoveryTool --> GCSBucket[("GCS Bucket<br/>gs://sec-analyst-sec-reports/filings/")]
    end

    subgraph ContextAssembler ["🧩 Grounded Context Assembly"]
        BQTable --> ContextBlock["Formatted RAG Context Block<br/>(Metrics + Bounded Text Chunks <= 10)"]
        GCSBucket --> ContextBlock
    end

    subgraph Synthesis ["🧠 Reasoning & Narrative Generation"]
        ContextBlock --> AnalystAgent["FinancialAnalystAgent<br/>(Gemini 2.5 Pro)"]
        AnalystAgent --> FinalResponse["Structured Narrative Output<br/>+ Verified Math + Grounded Citations"]
    end
```

---

## 4. Key Architectural Component Descriptions

### 1. ADK Root Orchestrator (`agent/orchestrator.py`)
- **Intent Parsing**: Extracts target ticker symbols (`AAPL`, `MSFT`, `NVDA`, `GOOGL`, `AMZN`, `TSLA`, `META`, `AMD`, `JPM`, `WMT`), fiscal years, metric names, and thematic keywords.
- **Routing & Dispatch**: Directs incoming queries through the hybrid RAG engine and invokes `FinancialAnalystAgent`.

### 2. Financial Analyst Agent (`agent/orchestrator.py`)
- **Reasoning Model**: Utilizes **Gemini 2.5 Pro** exclusively for high-precision financial synthesis, multi-turn reasoning, and narrative generation.
- **Native Tool Calling**: Equipped with native function definitions (`calculate_financial_variance_tool`, `query_bigquery_financial_metrics_tool`, `search_sec_filing_chunks_tool`, `vertex_ai_search_datastore_tool`).

### 3. Decoupled Deterministic Calculation Engine (`agent/tools/calculation_engine.py`)
- Computes period-over-period financial variance (absolute change & percentage change) using Python floating-point precision.
- Eliminates LLM arithmetic hallucination by enforcing 100% deterministic calculation accuracy.

### 4. Hybrid Search RAG Layer (`agent/rag/`)
- **Structured Store (`agent/rag/bigquery_store.py`)**: Queries BigQuery for golden financial metrics (Revenue, Operating Income, Net Income).
- **Unstructured Store (`agent/rag/sec_corpus.py`)**: Searches 120 unabridged SEC 10-K filing disclosures grounded in Google Cloud Storage (`gs://sec-analyst-sec-reports/filings/`).
- **Token Window Bounding**: Enforces chunk capping (`<= 10` chunks) per query to ensure context size stays within optimal model window parameters.

### 5. Guardrails & Observability (`agent/guardrails/` & `agent/observability/`)
- **PII Scrubber**: Sanitizes sensitive user tokens (SSNs, emails, credit cards, API keys) prior to processing. (Roadmap: Transitioning to GCP Model Armor).
- **Telemetry & Traceability**: OpenTelemetry span instrumentation (`tracer.py`) and structured JSON intent/outcome event logging (`logging_config.py`).
