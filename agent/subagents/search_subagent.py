"""Google ADK Search Sub-Agent specializing in SEC 10-K filing disclosures search."""

from google.adk.agents.llm_agent import LlmAgent
from google.adk.tools.agent_tool import AgentTool
from agent.config import settings
from agent.rag.sec_corpus import search_sec_filing_chunks_tool

search_agent = LlmAgent(
    name="search_agent",
    model=settings.reasoning_model,
    description=(
        "Searches SEC EDGAR filings (Item 7 MD&A and Item 1A Risk Factors disclosures) "
        "and related financial data sources. Given a natural-language request, returns "
        "synthesized excerpts, quotes, and sources."
    ),
    instruction=(
        "You are a search specialist for SEC 10-K disclosures. Given a search query, ticker, or requested years, "
        "use search_sec_filing_chunks_tool to retrieve relevant filing chunks and return a concise, accurate, "
        "sourced response including exact metrics and GCS URIs formatted strictly as `(Source: <Ticker> <Year> 10-K, <gcs_uri>)`."
    ),
    tools=[search_sec_filing_chunks_tool],
)

search_tool = AgentTool(
    agent=search_agent,
    skip_summarization=True,
)

__all__ = ["search_agent", "search_tool"]
