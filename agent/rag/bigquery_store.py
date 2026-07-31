"""BigQuery Data Store for structured SEC financial metrics querying GCP BigQuery live."""

from typing import List, Optional
from pydantic import BaseModel
from google.cloud import bigquery
from agent.config import settings
from agent.observability.logging_config import log_tool_execution


class FinancialMetricRecord(BaseModel):
    """Structured financial metric record in BigQuery."""

    ticker: str
    fiscal_year: int
    company_name: str
    sector: str = "Technology"
    revenue: float
    operating_income: float
    net_income: float
    period_unit: str = "USD (Millions)"
    source: str = "GCP BigQuery"


class BigQueryFinancialStore:
    """BigQuery Data Store client for structured financial metrics using official google.cloud.bigquery Python SDK."""

    def __init__(self, project_id: Optional[str] = None):
        self.project_id = project_id or settings.gcp_project_id
        self.dataset_id = "sec_edgar_financials"
        self.table_id = "financial_metrics"
        try:
            self.client = bigquery.Client(project=self.project_id)
        except Exception:
            self.client = None

    def query_metrics(self, ticker: str, fiscal_year: int) -> Optional[FinancialMetricRecord]:
        """Queries structured financial metrics directly from GCP BigQuery table sec_edgar_financials.financial_metrics using BigQuery Python SDK."""
        ticker_clean = ticker.strip().upper()
        log_tool_execution(
            tool_name="bigquery_query_metrics",
            stage="intent",
            payload={"project_id": self.project_id, "ticker": ticker_clean, "fiscal_year": fiscal_year},
        )

        if not self.client:
            log_tool_execution("bigquery_query_metrics", "outcome", {"status": "CLIENT_NOT_INITIALIZED"}, status="ERROR")
            return None

        try:
            query_sql = f"""
            SELECT ticker, company_name, fiscal_year, revenue, operating_income, net_income
            FROM `{self.project_id}.{self.dataset_id}.{self.table_id}`
            WHERE UPPER(ticker) = '{ticker_clean}' AND fiscal_year = {fiscal_year}
            LIMIT 1
            """
            query_job = self.client.query(query_sql)
            rows = list(query_job.result())

            if rows:
                row = rows[0]
                record = FinancialMetricRecord(
                    ticker=str(row.ticker),
                    company_name=str(row.company_name),
                    fiscal_year=int(row.fiscal_year),
                    revenue=float(row.revenue or 0.0),
                    operating_income=float(row.operating_income or 0.0),
                    net_income=float(row.net_income or 0.0),
                    source=f"GCP BigQuery ({self.project_id}.{self.dataset_id}.{self.table_id})",
                )
                log_tool_execution("bigquery_query_metrics", "outcome", record.model_dump(), status="SUCCESS")
                return record
        except Exception as e:
            log_tool_execution("bigquery_query_metrics", "outcome", {"error": str(e)}, status="ERROR")
            return None

        log_tool_execution("bigquery_query_metrics", "outcome", {"status": "NOT_FOUND"}, status="ERROR")
        return None

    def query_multi_company_metrics(
        self,
        tickers: List[str],
        start_year: int,
        end_year: int,
    ) -> List[FinancialMetricRecord]:
        return results


def query_bigquery_financial_metrics_tool(ticker: str, fiscal_year: int) -> dict:
    """Queries structured financial metrics (Revenue, Operating Income, Net Income) directly from GCP BigQuery for a given ticker and fiscal year.

    Args:
        ticker: Ticker symbol (e.g. AAPL, MSFT, NVDA).
        fiscal_year: Target fiscal year (e.g. 2022, 2023, 2024).
    """
    store = BigQueryFinancialStore()
    rec = store.query_metrics(ticker=ticker, fiscal_year=fiscal_year)
    return rec.model_dump() if rec else {"error": f"No BigQuery financial metrics found for {ticker} FY{fiscal_year}"}
