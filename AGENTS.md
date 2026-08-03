# Agent Guidelines & Workspace Rules

This repository defines workspace rules for AI agents operating on the **SEC EDGAR Natural Language Analyst** codebase.

Full detailed rules and behavioral guidelines are located in [.agents/rules/project_rules.md](file:///.agents/rules/project_rules.md).

## Quick Summary
1. **Deterministic Calculations**: Always use the deterministic calculation engine (`agent/tools/calculation_engine.py`) for quantitative financial calculations.
2. **ADK Framework**: Follow Google Agent Development Kit (ADK) patterns when creating or modifying orchestrators, sub-agents, and tools in `agent/`.
3. **Testing**: Run pytest (`pytest eval/`) to ensure no regressions against the evaluation harness and golden dataset.
4. **Secrets**: Use `.env` or environment configuration; never hardcode credentials.
5. **Git Commits**: Never commit code updates automatically. Only commit changes when explicitly instructed by the user.
