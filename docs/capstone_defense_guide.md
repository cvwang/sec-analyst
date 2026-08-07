# 🎓 FDE Capstone Technical Breakdown & Panel Defense Guide

**Project:** SEC EDGAR Natural Language Analyst  
**Architecture Framework:** GCP Agent Development Kit (ADK) + Vertex AI + BigQuery + Model Armor  

---

### 1. High-Level AI-Driven Development Narrative & Harness Setup

#### 🛠️ Harness Initialization Before Coding
Before generating application logic, the developer harness was anchored in authoritative specifications and rigid evaluation criteria:
- **Authoritative Specifications:** Requirements were frozen in [`FDE Onboarding Project.md`](file:///Users/cvwang/Documents/gcp/sec-edgar-analyst/FDE%20Onboarding%20Project.md), [`fsi_scoping.md`](file:///Users/cvwang/Documents/gcp/sec-edgar-analyst/fsi_scoping.md), and [`fsi_tdd.md`](file:///Users/cvwang/Documents/gcp/sec-edgar-analyst/fsi_tdd.md), defining strict data sources (GCS filings `gs://sec-analyst-sec-reports/filings/`, BigQuery golden tables).
- **System Constitution ([`agent/constitution.py`](file:///Users/cvwang/Documents/gcp/sec-edgar-analyst/agent/constitution.py)):** Established non-negotiable operational boundaries (100% numerical grounding, mandatory tool usage, zero conversational filler, and A2UI visual schema contracts).
- **Evaluation Harness ([`eval/test_eval_harness.py`](file:///Users/cvwang/Documents/gcp/sec-edgar-analyst/eval/test_eval_harness.py) & [`eval/run_benchmark.py`](file:///Users/cvwang/Documents/gcp/sec-edgar-analyst/eval/run_benchmark.py)):** Created a suite of tests and a dataset ([`eval/golden_dataset.json`](file:///Users/cvwang/Documents/gcp/sec-edgar-analyst/eval/golden_dataset.json)) targeting variance calculation precision, RAG retrieval accuracy, and guardrail interception before agent tool development began.

#### 🔄 "In-The-Loop" (Interactive Collaboration)
- **Tool Schema Co-Design:** Defined structured Pydantic input/output contracts for tools like [`calculate_financial_variance`](file:///Users/cvwang/Documents/gcp/sec-edgar-analyst/agent/tools/calculation_engine.py#L7-L50) to guarantee strong type checking.
- **Visual Protocol (A2UI):** Co-designed the A2UI dynamic visual component protocol specification in [`agent/constitution.py`](file:///Users/cvwang/Documents/gcp/sec-edgar-analyst/agent/constitution.py#L48-L128) (e.g., `MetricsChart`, `FinancialTable`, `MetricCard`) to decouple raw JSON UI definitions from backend text generation.
- **Prompt Tuning & Citations:** Refined grounding formats to enforce inline source citations `(Source: <Ticker> <Year> 10-K <Section>, <gcs_uri>)` across multi-turn sessions.

#### 🤖 "Outside-The-Loop" (Autonomous Execution Loops)
- **Goal-Driven Benchmark & Lint Loops:** AGY ran autonomous loops calling `pytest eval/` and benchmark evaluation suites ([`eval/run_benchmark.py`](file:///Users/cvwang/Documents/gcp/sec-edgar-analyst/eval/run_benchmark.py)) to test multi-step queries.
- **Automated Bug Patching:** When edge cases failed (e.g., division-by-zero in variance calculation or nested event-loop deadlocks in FastAPI), AGY traced stack traces, modified core agent logic, and re-ran tests until 100% assertion pass rate was achieved without human intervention.

---

### 2. Prompt Engineering & Prompting Process Nuances

#### ⚡ Critical Prompt Engineering Breakthroughs & Constraints
Defined in [`agent/constitution.py`](file:///Users/cvwang/Documents/gcp/sec-edgar-analyst/agent/constitution.py):
1. **100% Numerical Grounding Lock:** System instructions strictly forbid the LLM from performing mental arithmetic or extrapolating missing numbers. Pre-trained weights are overridden by deterministic outputs from [`query_bigquery_financial_metrics_tool`](file:///Users/cvwang/Documents/gcp/sec-edgar-analyst/agent/rag/bigquery_store.py) and [`calculate_financial_variance_tool`](file:///Users/cvwang/Documents/gcp/sec-edgar-analyst/agent/tools/calculation_engine.py#L150).
2. **Explicit 2025 Filing Datastore Notice:** Added an explicit prompt directive in [`agent/constitution.py`](file:///Users/cvwang/Documents/gcp/sec-edgar-analyst/agent/constitution.py#L16) and [`agent/subagents/search_subagent.py`](file:///Users/cvwang/Documents/gcp/sec-edgar-analyst/agent/subagents/search_subagent.py#L19) notifying the agent that fiscal year 2025 filings are fully indexed in Vertex AI Search, eliminating hallucinated refusals for 2025 queries.
3. **Granular Inline Source Citations:** Prompt rules enforce that *every* bullet point/disclosure sentence carries an explicit badge: `(Source: <Ticker> <Year> 10-K <Section>, <gcs_uri>)`.
4. **No Markdown Table Duplication & A2UI Rendering:** Prohibits raw HTML/Markdown table rendering in narrative responses. Tabular data must be emitted cleanly via JSON blocks marked with ```a2ui syntax.
5. **No Conversational Filler:** Mandates direct, immediate response delivery ("Jump directly into the grounded response"), stripping phrase preambles like "Sure, here is...".

#### 🧠 Multi-Turn Context Retention & Memory Compaction
- **Persistent Session State ([`agent/memory/session_store.py`](file:///Users/cvwang/Documents/gcp/sec-edgar-analyst/agent/memory/session_store.py)):** State is serialized to disk across user turns via [`PersistentSessionStore`](file:///Users/cvwang/Documents/gcp/sec-edgar-analyst/agent/memory/session_store.py).
- **Context Window Management:** Google ADK `Runner` retains full conversation context while sliding tool outputs to prevent context blowup or model drift during deep multi-turn analysis.

#### 🛡️ Prompt Injection & Jailbreak Defense
- **GCP Model Armor Screening ([`agent/guardrails/model_armor.py`](file:///Users/cvwang/Documents/gcp/sec-edgar-analyst/agent/guardrails/model_armor.py)):** Wrapped using `google-cloud-modelarmor` SDK client.
  - **Ingress Hook (`model_armor_before_model_callback`):** Intercepts prompt injection (e.g., `"ignore previous instructions"`, `"override system prompt"`) before sending to the model, returning an immediate `[MODEL_ARMOR_BLOCK:STAGE=INGRESS]` response.
  - **Egress Hook (`model_armor_after_model_callback`):** Sanitizes model output for unauthorized policy violations before rendering to the client.
- **Human-In-The-Loop (HITL) Gate:** External storage or report exports (`export_financial_report` in [`agent/orchestrator.py`](file:///Users/cvwang/Documents/gcp/sec-edgar-analyst/agent/orchestrator.py#L120)) return `PENDING_HUMAN_APPROVAL` until explicitly confirmed by the user.

---

### 3. System Design Evolutions & Architectural Nuances

```mermaid
flowchart TD
    User([User Prompt / UI]) --> API[FastAPI Server / ADK Runner]
    API --> ArmorIn[Model Armor Ingress Callback]
    ArmorIn -- Pass --> Orchestrator[Root Orchestrator - LlmAgent]
    ArmorIn -- Block --> UserBlock[Blocked Response]
    
    Orchestrator --> SQLTool[query_bigquery_financial_metrics_tool]
    Orchestrator --> MathTool[calculate_financial_variance_tool]
    Orchestrator --> SubAgent[Search Subagent - AgentTool]
    
    SQLTool --> BQ[(BigQuery Golden Tables)]
    SubAgent --> VertexRAG[search_sec_filing_chunks_tool]
    VertexRAG --> VertexSearch[(Vertex AI Search DataStore)]
    
    Orchestrator --> ArmorOut[Model Armor Egress Callback]
    ArmorOut --> Response[Grounded Response + A2UI Spec]
```

#### 🏗️ Prototype to Capstone Evolution
- Evolved from a simple single-prompt script into a modular ADK multi-agent architecture ([`agent/orchestrator.py`](file:///Users/cvwang/Documents/gcp/sec-edgar-analyst/agent/orchestrator.py)) featuring specialized sub-agents ([`agent/subagents/search_subagent.py`](file:///Users/cvwang/Documents/gcp/sec-edgar-analyst/agent/subagents/search_subagent.py)).

#### 🔀 Structured SQL vs. Unstructured RAG Fusion
- **Structured Data (BigQuery):** Quantitatively precise financial metrics (Revenue, Net Income, Operating Income) are retrieved via [`query_bigquery_financial_metrics_tool`](file:///Users/cvwang/Documents/gcp/sec-edgar-analyst/agent/rag/bigquery_store.py) from indexed BigQuery datasets (`sec_financial_metrics`).
- **Unstructured Data (Vertex AI Search):** Qualitative MD&A strategies and Risk Factors are queried from GCS markdown filings (`gs://sec-analyst-sec-reports/filings/`) via [`VertexAISearchClient`](file:///Users/cvwang/Documents/gcp/sec-edgar-analyst/agent/rag/vertex_search.py).

#### 🎯 Search Query Formulation & Grounded Highlighting
- **Query Formulation (`formulate_vertex_search_query` in [`agent/rag/sec_corpus.py`](file:///Users/cvwang/Documents/gcp/sec-edgar-analyst/agent/rag/sec_corpus.py#L169)):** Strips conversational preamble noise (e.g. "Can you please explain...") and combines metadata anchor terms (Ticker, Year) with core semantic keywords.
- **Bounded Token Window (`page_size=5`):** Retains top-ranked chunks to eliminate token bloat and context distraction.
- **Parallel LLM Sentence Highlighting (`annotate_grounded_highlights_with_llm` in [`agent/rag/sec_corpus.py`](file:///Users/cvwang/Documents/gcp/sec-edgar-analyst/agent/rag/sec_corpus.py#L65)):** Runs Gemini 2.5 Flash in parallel across retrieved chunks to wrap exact substantiating filing sentences inside `<mark>` tags for split-pane UI rendering.

---

### 4. Technical Design Decisions & Trade-Off Matrix

| Design Dimension | Selected Approach | Alternative Evaluated | Key Rationale & Strategic Trade-off |
| :--- | :--- | :--- | :--- |
| **1. Financial Math Engine** | **Decoupled Python Math Tool** ([`agent/tools/calculation_engine.py`](file:///Users/cvwang/Documents/gcp/sec-edgar-analyst/agent/tools/calculation_engine.py)) | Pure LLM In-Context Arithmetic | **Trade-off:** Zero tolerance for mathematical hallucinations vs. extra tool step. Python ensures 100% accuracy and handles division-by-zero edge cases deterministically. |
| **2. Retrieval Strategy** | **Hybrid Search** (BigQuery SQL + Vertex AI Search DataStore) | Naive Pure Vector Search | **Trade-off:** Dual-query latency vs. precision. SQL guarantees scalar value accuracy; Vector Search handles unstructured 10-K text retrieval cleanly without parsing tabular noise into vectors. |
| **3. Performance & Cost** | **Vertex AI Context Caching (CAG)** | Uncached Standard Prompts | **Trade-off:** Cache TTL management vs. latency/cost. CAG delivers a **75% input token cost reduction** and significantly lowers Time-To-First-Token (TTFT) for large system constitutions. |
| **4. Security & Secrets** | **GCP Secret Manager & ADC Service Accounts** | Hardcoded API Keys / `.env` in Prod | **Trade-off:** Initial IAM setup overhead vs. enterprise security. Prevents credential leaks and complies with GCP security standards. |
| **5. Architecture** | **Supervisor + Search Subagent Decoupling** ([`search_subagent.py`](file:///Users/cvwang/Documents/gcp/sec-edgar-analyst/agent/subagents/search_subagent.py)) | Monolithic Orchestrator | **Trade-off:** Slight orchestration overhead vs. modularity. Decoupling search logic into an `AgentTool` isolates retrieval prompt instructions and improves accuracy. |

---

### 5. Toughest Challenges & The Refinement Flywheel

#### 💣 Top 4 Engineering Challenges Solved

1. **Google ADK Event Loop Deadlock (`_exec_async` helper):**
   - *Problem:* ADK's `Runner` mixed synchronous execution with async coroutines, throwing `RuntimeError: This event loop is already running` inside FastAPI request handlers.
   - *Solution:* Implemented `_exec_async()` in [`agent/orchestrator.py`](file:///Users/cvwang/Documents/gcp/sec-edgar-analyst/agent/orchestrator.py#L92), using an isolated single-worker `ThreadPoolExecutor` to execute async coroutines safely when an active loop is detected.

2. **Model Armor Callback Integration (`model_armor_before_model_callback`):**
   - *Problem:* Wiring Model Armor directly inside tool bodies caused partial model executions and unhandled exceptions.
   - *Solution:* Created native ADK callbacks ([`agent/orchestrator.py`](file:///Users/cvwang/Documents/gcp/sec-edgar-analyst/agent/orchestrator.py#L35-L89)) that intercept requests/responses at the model boundary and cleanly short-circuit execution with `LlmResponse` error messages when policy violations occur.

3. **Grounding Alignment without Distorting Source Text:**
   - *Problem:* Naive regex replacement for text highlighting broke when Gemini slightly modified punctuation or word spacing in filing quotes.
   - *Solution:* Engineered a two-tier matching engine (`annotate_text_with_clauses` in [`agent/rag/sec_corpus.py`](file:///Users/cvwang/Documents/gcp/sec-edgar-analyst/agent/rag/sec_corpus.py#L34)) using verbatim matching first, falling back to sentence-level keyword overlap ratio matching (`>= 50%` word match).

4. **Async BigQuery Telemetry Streaming ([`agent/observability/telemetry_sink.py`](file:///Users/cvwang/Documents/gcp/sec-edgar-analyst/agent/observability/telemetry_sink.py)):**
   - *Problem:* Synchronous logging of token counts and tool execution latencies to BigQuery introduced visible latency penalties into user responses.
   - *Solution:* Built a non-blocking `BigQueryTelemetrySink` that batches telemetry events and streams them to BigQuery in background tasks.

#### 🔄 The Refinement Flywheel: Turning Failures into Constitution Rules

- **Incident 1: Hallucinated Refusals for 2025 Filings**
  - *Failure:* The model claimed 2025 SEC filings were missing because its internal knowledge cut-off was 2023.
  - *Fix:* Added **Operational Rule 16** in [`agent/constitution.py`](file:///Users/cvwang/Documents/gcp/sec-edgar-analyst/agent/constitution.py#L16), explicitly instructing the agent that 2025 filings are present in the datastore and requiring execution of `search_agent` before declaring data unavailable.

- **Incident 2: HTML Table Formatting Pollution**
  - *Failure:* The agent rendered raw HTML tables in narrative answers, causing broken UI layouts.
  - *Fix:* Created **Rule 8 (NO MARKDOWN TABLE DUPLICATION RULE)** in [`agent/constitution.py`](file:///Users/cvwang/Documents/gcp/sec-edgar-analyst/agent/constitution.py#L45), strictly requiring narrative text to use paragraphs/bullets and forcing tabular data into ```a2ui JSON blocks.

- **Incident 3: Verbose Conversational Filler**
  - *Failure:* The model began responses with generic conversational intros ("Sure! As an AI financial analyst...").
  - *Fix:* Created **Rule 6 (NO CONVERSATIONAL FILLER RULE)** in [`agent/constitution.py`](file:///Users/cvwang/Documents/gcp/sec-edgar-analyst/agent/constitution.py#L35), enforcing immediate, direct entry into grounded answers.

---

### Summary Checklist for Panel Defense Presentation
- [x] **Live Demo:** Demonstrate multi-turn query (e.g., "Compare Tesla 2022 vs 2023 Revenue and Operating Income"), showing A2UI dynamic chart rendering.
- [x] **Grounding Verification:** Highlight inline citation links leading directly to GCS filing URIs and highlighted `<mark>` text.
- [x] **Deterministic Accuracy:** Demonstrate zero math errors via [`calculate_financial_variance_tool`](file:///Users/cvwang/Documents/gcp/sec-edgar-analyst/agent/tools/calculation_engine.py).
- [x] **Security Proof:** Showcase Model Armor intercepting prompt injection attempts seamlessly.
- [x] **Evaluation Evidence:** Present benchmark test logs from [`eval/test_eval_harness.py`](file:///Users/cvwang/Documents/gcp/sec-edgar-analyst/eval/test_eval_harness.py).
