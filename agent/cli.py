"""Interactive Command Line Interface (CLI) for running live SEC EDGAR Agent variance analysis queries."""

import sys
from typing import Optional
from agent.config import settings
from agent.orchestrator import RootOrchestrator


def print_banner():
    print("\n" + "=" * 70)
    print("      📊 SEC EDGAR NATURAL LANGUAGE ANALYST AGENT (Phase 1) 📊")
    print("=" * 70)
    print("Available Tickers in SEC DB : AAPL, MSFT, NVDA")
    print("Available Financial Metrics : Revenue, Operating Income, Net Income")
    print("-" * 70 + "\n")


def run_cli_session():
    """Runs interactive CLI session allowing live agent query execution."""
    print_banner()

    orchestrator = RootOrchestrator()

    while True:
        try:
            print("\nEnter Query Parameters (or type 'exit' / 'q' to quit):")
            ticker_input = input("  • Ticker Symbol (e.g., AAPL, MSFT, NVDA) [AAPL]: ").strip()
            if ticker_input.lower() in ("exit", "q", "quit"):
                print("\nExiting agent CLI. Goodbye!")
                break

            ticker = ticker_input.upper() if ticker_input else "AAPL"

            current_yr_in = input("  • Current Fiscal Year [2023]: ").strip()
            current_year = int(current_yr_in) if current_yr_in else 2023

            prior_yr_in = input("  • Prior Fiscal Year [2022]: ").strip()
            prior_year = int(prior_yr_in) if prior_yr_in else 2022

            metric_in = input("  • Metric Name (Revenue/Operating Income/Net Income) [Revenue]: ").strip()
            metric_name = metric_in.title() if metric_in else "Revenue"

            print(f"\n🚀 Running Financial Analyst Agent for {ticker} ({current_year} vs {prior_year} {metric_name})...\n")

            # Dispatch Query via ADK RootOrchestrator
            res = orchestrator.dispatch_query(
                query_type="variance_analysis",
                ticker=ticker,
                current_year=current_year,
                prior_year=prior_year,
                metric_name=metric_name,
            )

            if not res.get("is_success"):
                print(f"❌ Analysis Error: {res.get('error')}")
                continue

            # Output Formatted Results
            print("=" * 70)
            print(f"  AGENT ANALYSIS REPORT (Engine: {res.get('model_used', 'Unknown')})")
            print("=" * 70)
            if res.get("model_used") == "deterministic-fallback":
                print("⚠️  Notice: Falling back to deterministic output because GCP OAuth token requires re-authentication.")
                print("   To enable live Vertex AI responses, run: gcloud auth application-default login\n")
            print(res["narrative"])
            print("=" * 70)

            # Test Human-In-The-Loop Export Guardrail
            export_choice = input("\nDo you want to test Exporting this Report to Google Cloud Storage (GCS)? (y/n) [n]: ").strip().lower()
            if export_choice in ("y", "yes"):
                gcs_uri = f"gs://{settings.gcp_project_id}-sec-reports/{ticker.lower()}_{current_year}_report.md"
                print(f"\n🔒 Requesting export to: {gcs_uri}")

                # First call without approval (demonstrates HITL stop)
                unapproved_res = orchestrator.dispatch_query(
                    query_type="variance_analysis",
                    ticker=ticker,
                    current_year=current_year,
                    prior_year=prior_year,
                    metric_name=metric_name,
                    export_gcs_uri=gcs_uri,
                    human_approved_export=False,
                )
                print(f"🛑 HITL Guardrail Response: Status={unapproved_res['export_status']['status']}")
                print(f"   Message: {unapproved_res['export_status']['message']}")

                confirm = input("\nGrant Human Approval to execute GCS Export? (y/n): ").strip().lower()
                if confirm in ("y", "yes"):
                    approved_res = orchestrator.dispatch_query(
                        query_type="variance_analysis",
                        ticker=ticker,
                        current_year=current_year,
                        prior_year=prior_year,
                        metric_name=metric_name,
                        export_gcs_uri=gcs_uri,
                        human_approved_export=True,
                    )
                    print(f"✅ Export Execution Result: Status={approved_res['export_status']['status']}")
                    print(f"   Message: {approved_res['export_status']['message']}")
                else:
                    print("🚫 Export cancelled by user.")

        except KeyboardInterrupt:
            print("\nExiting CLI session.")
            break
        except Exception as e:
            print(f"❌ Error: {e}")


if __name__ == "__main__":
    run_cli_session()
