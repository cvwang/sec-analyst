"""Interactive Command Line Interface (CLI) supporting structured queries and natural language multi-turn chat."""

import re
from typing import Dict, Any
from agent.config import settings
from agent.orchestrator import RootOrchestrator


def print_banner():
    print("\n" + "=" * 70)
    print("      📊 SEC EDGAR NATURAL LANGUAGE ANALYST AGENT (Phase 1) 📊")
    print("=" * 70)
    print("Supports both Natural Language Prompts and Structured Inputs!")
    print("Example Prompts: 'Analyze Apple revenue 2023 vs 2022' or 'Check NVDA 2024'")
    print("-" * 70 + "\n")


def parse_natural_prompt(prompt: str) -> Dict[str, Any]:
    """Parses natural language prompt strings into structured query parameters."""
    text_lower = prompt.lower()

    # Determine Ticker
    ticker = "AAPL"
    if "msft" in text_lower or "microsoft" in text_lower:
        ticker = "MSFT"
    elif "nvda" in text_lower or "nvidia" in text_lower:
        ticker = "NVDA"
    elif "aapl" in text_lower or "apple" in text_lower:
        ticker = "AAPL"

    # Determine Financial Metric
    metric_name = "Revenue"
    if "operating" in text_lower or "operating income" in text_lower:
        metric_name = "Operating Income"
    elif "net income" in text_lower or "profit" in text_lower:
        metric_name = "Net Income"
    elif "revenue" in text_lower or "sales" in text_lower:
        metric_name = "Revenue"

    # Determine Fiscal Years
    current_year = 2023
    prior_year = 2022

    years = [int(y) for y in re.findall(r"\b(202[0-9])\b", prompt)]
    if len(years) >= 2:
        years.sort(reverse=True)
        current_year, prior_year = years[0], years[1]
    elif len(years) == 1:
        if years[0] == 2024:
            current_year, prior_year = 2024, 2023

    return {
        "ticker": ticker,
        "current_year": current_year,
        "prior_year": prior_year,
        "metric_name": metric_name,
    }


def run_cli_session():
    """Runs multi-turn chat session with persistent state and natural language parsing."""
    print_banner()

    orchestrator = RootOrchestrator()
    session_id = "user_session_001"

    while True:
        try:
            user_input = input("\n💬 User Query (e.g., 'Analyze Apple revenue 2023 vs 2022' or 'exit'): ").strip()
            if not user_input:
                continue

            if user_input.lower() in ("exit", "q", "quit"):
                print("\nExiting agent session. Goodbye!")
                break

            # Parse natural prompt or structured parameters
            params = parse_natural_prompt(user_input)

            print(f"\n🚀 Running Agent for session '{session_id}'...\n")

            # Dispatch Query with persistent session ID
            res = orchestrator.dispatch_query(
                prompt=user_input,
                session_id=session_id,
            )

            if not res.get("is_success"):
                print(f"❌ Analysis Error: {res.get('error')}")
                continue

            stored_history = orchestrator.session_store.get_session_history(session_id)

            # Output Report & Memory Info
            print("=" * 70)
            print(f"  AGENT ANALYSIS REPORT (Engine: {res.get('model_used', 'Unknown')})")
            print(f"  🧠 Memory State: Session '{session_id}' | Turns Stored: {len(stored_history)}")
            print("=" * 70)
            if res.get("model_used") == "deterministic-fallback":
                print("⚠️  Notice: Falling back to deterministic output because GCP OAuth token requires re-authentication.")
                print("   To enable live Vertex AI responses, run: gcloud auth application-default login\n")
            print(res["narrative"])
            print("=" * 70)

            # Check for GCS export request in prompt
            if "export" in user_input.lower() or "save" in user_input.lower():
                primary = res.get('tickers')[0] if res.get('tickers') else 'report'
                gcs_uri = f"gs://{settings.gcp_project_id}-sec-reports/{primary.lower()}_report.md"
                print(f"\n🔒 Requesting GCS export: {gcs_uri}")

                unapproved = orchestrator.dispatch_query(
                    prompt=user_input,
                    session_id=session_id,
                    export_gcs_uri=gcs_uri,
                    human_approved_export=False,
                )
                print(f"🛑 HITL Guardrail: Status={unapproved['export_status']['status']}")
                print(f"   Message: {unapproved['export_status']['message']}")

                confirm = input("\nGrant Human Approval for GCS Export? (y/n): ").strip().lower()
                if confirm in ("y", "yes"):
                    approved = orchestrator.dispatch_query(
                        prompt=user_input,
                        session_id=session_id,
                        export_gcs_uri=gcs_uri,
                        human_approved_export=True,
                    )
                    print(f"✅ Export Success: {approved['export_status']['message']}")

        except KeyboardInterrupt:
            print("\nExiting chat session.")
            break
        except Exception as e:
            print(f"❌ Error: {e}")


if __name__ == "__main__":
    run_cli_session()
