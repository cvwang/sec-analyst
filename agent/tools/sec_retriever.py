"""SEC EDGAR context retriever tool for fetching 10-K financial metrics and filing excerpts."""

from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class SECContextRequest(BaseModel):
    """Input request parameters for retrieving SEC 10-K filing metrics."""

    ticker: str = Field(..., description="Ticker symbol (e.g. AAPL, MSFT, NVDA).")
    fiscal_year: int = Field(..., description="Fiscal year (e.g. 2023, 2022).")


class SECContextResult(BaseModel):
    """Structured filing context and financial metrics from SEC 10-K filings."""

    ticker: str
    fiscal_year: int
    revenue: Optional[float] = None
    operating_income: Optional[float] = None
    net_income: Optional[float] = None
    period_unit: str = "USD (Millions)"
    excerpt: str = ""
    is_success: bool = True
    error: Optional[str] = None


# Mock 10-K dataset based on actual SEC filings (in USD Millions)
SEC_10K_DATABASE: Dict[str, Dict[int, Dict[str, Any]]] = {
    "AAPL": {
        2023: {
            "revenue": 383285.0,
            "operating_income": 114301.0,
            "net_income": 96995.0,
            "excerpt": "Apple Inc. FY2023 10-K: Total net sales were $383,285 million down 2.8% due to macroeconomic headwinds in hardware.",
        },
        2022: {
            "revenue": 394328.0,
            "operating_income": 119437.0,
            "net_income": 99803.0,
            "excerpt": "Apple Inc. FY2022 10-K: Total net sales reached a record $394,328 million driven by iPhone 14 momentum.",
        },
    },
    "MSFT": {
        2023: {
            "revenue": 211915.0,
            "operating_income": 88523.0,
            "net_income": 72361.0,
            "excerpt": "Microsoft Corp FY2023 10-K: Revenue increased 7% driven by Intelligent Cloud expansion.",
        },
        2022: {
            "revenue": 198270.0,
            "operating_income": 83383.0,
            "net_income": 72738.0,
            "excerpt": "Microsoft Corp FY2022 10-K: Strong growth across Azure and commercial cloud services.",
        },
    },
    "NVDA": {
        2024: {
            "revenue": 60922.0,
            "operating_income": 32972.0,
            "net_income": 29760.0,
            "excerpt": "NVIDIA Corp FY2024 10-K: Data Center revenue skyrocketed driven by Hopper architecture AI demand.",
        },
        2023: {
            "revenue": 26974.0,
            "operating_income": 4224.0,
            "net_income": 4368.0,
            "excerpt": "NVIDIA Corp FY2023 10-K: Revenue was flat year-over-year amidst gaming market normalization.",
        },
    },
}


def fetch_sec_10k_context(request: SECContextRequest) -> SECContextResult:
    """Retrieves SEC 10-K financial metrics and narrative excerpt for a given ticker and year.

    Args:
        request: SECContextRequest containing ticker and fiscal_year.

    Returns:
        SECContextResult containing financial values, narrative excerpt, or error details.
    """
    ticker = request.ticker.strip().upper()
    year = request.fiscal_year

    if ticker not in SEC_10K_DATABASE:
        return SECContextResult(
            ticker=ticker,
            fiscal_year=year,
            is_success=False,
            error=f"Ticker '{ticker}' not found in SEC EDGAR retriever database.",
        )

    year_data = SEC_10K_DATABASE[ticker].get(year)
    if not year_data:
        return SECContextResult(
            ticker=ticker,
            fiscal_year=year,
            is_success=False,
            error=f"Fiscal year {year} not found for ticker '{ticker}'.",
        )

    return SECContextResult(
        ticker=ticker,
        fiscal_year=year,
        revenue=year_data["revenue"],
        operating_income=year_data["operating_income"],
        net_income=year_data["net_income"],
        excerpt=year_data["excerpt"],
        is_success=True,
    )
