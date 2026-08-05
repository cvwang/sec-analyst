# Rule: Strict Zero-Fallback Policy

## Principle
Never insert silent default fallbacks, synthetic text fallbacks, or dummy values when RAG retrieval or API queries fail or return empty results. If data is missing, invalid, or unavailable, the query/operation must fail explicitly with clear error reporting.

## Guidelines
1. **No Silent Pre-Calculations / Defaults**:
   - Do NOT default function arguments or query parameters to arbitrary hardcoded types (e.g. `query_type: str = "financial_summary"`) just to satisfy tests if the prompt or conversation does not warrant it.
   - Do NOT return synthetic ungrounded LLM text when RAG search returns 0 chunks.

2. **Explicit Errors Over Masked Symptoms**:
   - Never swallow exceptions in silent `try/except` blocks that return 0-byte fallbacks or default static text.
   - Trace and log the exact root cause of runtime failures.

3. **Strict Grounding Enforcement**:
   - All financial claims, variance narratives, and qualitative explanations must be strictly grounded in authoritative data sources (BigQuery metrics and Vertex AI Search filing chunks).

4. **No Silent Pricing or Catalog Guesses**:
   - Do NOT insert silent default pricing rates or arbitrary baseline cost estimates when an entity (e.g., model name, SKU, or service tier) is unrecognized.
   - Flag unknown entities explicitly (`is_pricing_known = False`, `cost = 0.0`) and log an explicit warning/alert rather than masking them with silent rate guesses.

