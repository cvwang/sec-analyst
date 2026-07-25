# Project Status & Pick-Up Notes: SEC EDGAR Analyst Agent

**Date**: July 24, 2026  
**Repository**: `ai-in-5-days`  
**GitHub Remote**: [cvwang/sec-analyst](https://github.com/cvwang/sec-analyst)  
**Target GCP Sandbox**: `fde-sec-edgar-sandbox-dev` (`us-central1`)

---

## 🚀 What We Have Accomplished (Phase 1 Complete)

1. **Calculation Engine & Tools** ([agent/tools/](file:///Users/cvwang/Documents/gcp/ai-in-5-days/agent/tools/)):
   - `calculate_financial_variance`: Deterministic calculation tool for Revenue, Operating Income, and Net Income with strict Pydantic schemas, 100% numerical precision, and error recovery guidance.
   - `fetch_sec_10k_context`: Retriever tool for SEC 10-K financial metrics and MD&A excerpts.

2. **System Constitution** ([agent/constitution.py](file:///Users/cvwang/Documents/gcp/ai-in-5-days/agent/constitution.py)):
   - Defines persona rules and strict 100% numerical grounding constraints (no unverified arithmetic or hallucinations).

3. **ADK Root Orchestrator & Strategic Model Routing** ([agent/orchestrator.py](file:///Users/cvwang/Documents/gcp/ai-in-5-days/agent/orchestrator.py)):
   - `RootOrchestrator` supervising `FinancialAnalystAgent`:
     - **Gemini 2.5 Pro** for deep financial reasoning & synthesis.
     - **Gemini 3.5 Flash** for tool execution and evaluation.
     - **Human-In-The-Loop Approval Stop**: Pauses external report exports (`export_financial_report`) until explicitly approved.

4. **Observability & Guardrails** ([agent/guardrails/](file:///Users/cvwang/Documents/gcp/ai-in-5-days/agent/guardrails/) & [agent/observability/](file:///Users/cvwang/Documents/gcp/ai-in-5-days/agent/observability/)):
   - `pii_scrubber.py`: Sanitizes SSNs, credit cards, bank accounts, API keys, and emails before logging/storage.
   - `logging_config.py`: Structured JSON logger capturing pre-execution `intent` and post-execution `outcome` events.
   - `tracer.py`: OpenTelemetry span instrumentation.

5. **Evaluation Harness** ([eval/](file:///Users/cvwang/Documents/gcp/ai-in-5-days/eval/)):
   - `golden_dataset.json`: 5 golden query-variance test cases.
   - `test_eval_harness.py`: Pytest suite passing 10/10 tests cleanly (`python3 -m pytest eval/test_eval_harness.py -v`).

6. **Terraform IaC** ([terraform/](file:///Users/cvwang/Documents/gcp/ai-in-5-days/terraform/)):
   - `main.tf`, `variables.tf`, and `terraform.tfvars.example` for Cloud Run, Secret Manager, and GCS buckets targeting `fde-sec-edgar-sandbox-dev`.

---

## 📌 Next Steps to Pick Up Later

### 1. Enable Vertex AI IAM Permissions in Argolis Sandbox
Run this command in terminal to grant your user account the Vertex AI User role in project `fde-sec-edgar-sandbox-dev`:
```bash
gcloud projects add-iam-policy-binding fde-sec-edgar-sandbox-dev \
  --member="user:$(gcloud config get-value account)" \
  --role="roles/aiplatform.user"
```

### 2. Run Live Vertex AI Connectivity Test
Once permissions are granted, test live Gemini model generation against Vertex AI:
```bash
python3 -m agent.test_vertex_live
```

### 3. Deploy Terraform Infrastructure
Apply the Terraform plan to provision Cloud Run, Secret Manager, and Cloud Storage resources:
```bash
cd terraform
terraform init
terraform plan
terraform apply
```

### 4. Build Interactive Web UI (Optional Phase 2)
Optionally create a FastAPI web backend + interactive dashboard (with variance charts, 10-K excerpt viewer, and Human-In-The-Loop approval modal).
