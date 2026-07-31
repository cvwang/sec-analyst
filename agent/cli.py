"""Interactive Command Line Interface (CLI) supporting natural language financial queries and multi-turn chat."""

import os
from typing import Dict, Any
from agent.config import settings
from agent.orchestrator import RootOrchestrator
from agent.guardrails.pii_scrubber import PIIScrubber


def print_banner():
    print("\n" + "=" * 70)
    print("      📊 SEC EDGAR NATURAL LANGUAGE ANALYST AGENT 📊")
    print("=" * 70)
    print("Dynamic LLM-Powered Agent for Financial Variance, Peer Comparison, & MD&A/Risk RAG!")
    print("Example Prompts:")
    print("  • 'Analyze Apple revenue 2023 vs 2022'")
    print("  • 'Compare Microsoft and Nvidia operating income for 2023'")
    print("  • 'What are the main AI risk disclosures for Meta in 2023?'")
    print("-" * 70 + "\n")


def run_cli_session():
    """Runs multi-turn chat session with persistent state and LLM intent parsing."""
    print_banner()

    orchestrator = RootOrchestrator()
    session_id = "user_session_001"

    while True:
        try:
            user_input = input("\n💬 User Query (or 'exit' to quit): ").strip()
            if not user_input:
                continue

            if user_input.lower() in ("exit", "q", "quit"):
                print("\nExiting agent session. Goodbye!")
                break

            print(f"\n🚀 Running Agent for session '{session_id}'...\n")

            # Dispatch Query directly to RootOrchestrator (LLM intent parsing)
            res = orchestrator.dispatch_query(
                prompt=user_input,
                session_id=session_id,
            )

            if not res.get("is_success"):
                print(f"❌ Analysis Error: {res.get('error')}")
                continue

            # Apply PII scrubbing guardrail to narrative output
            narrative = res.get("narrative", "")
            if narrative:
                narrative = PIIScrubber.scrub_text(narrative)

            stored_history = orchestrator.session_store.get_session_history(session_id)

            # Output Report & Memory Info
            print("=" * 70)
            print(f"  AGENT ANALYSIS REPORT (Engine: {res.get('model_used', 'Unknown')})")
            print(f"  🧠 Memory State: Session '{session_id}' | Turns Stored: {len(stored_history)}")
            print("=" * 70)
            print(narrative)
            print("=" * 70)

            # Check for GCS export request in prompt
            if "export" in user_input.lower() or "save" in user_input.lower():
                primary = res.get("tickers")[0] if res.get("tickers") else "report"
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
