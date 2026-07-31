"""Deterministic calculation engine for SEC EDGAR period-over-period financial variance analysis."""

from typing import Optional, Union
from pydantic import BaseModel, Field, field_validator


class VarianceRequest(BaseModel):
    """Input parameters for calculating period-over-period financial variance."""

    ticker: str = Field(
        ...,
        description="Ticker symbol for the company (e.g., AAPL, MSFT, NVDA).",
    )
    metric_name: str = Field(
        ...,
        description="Name of financial metric: 'Revenue', 'Operating Income', or 'Net Income'.",
    )
    current_period_value: Union[float, int, str] = Field(
        ...,
        description="Financial metric value for the current period.",
    )
    prior_period_value: Union[float, int, str] = Field(
        ...,
        description="Financial metric value for the prior comparison period.",
    )
    period_unit: str = Field(
        default="USD (Millions)",
        description="Unit of measurement for the financial values.",
    )

    @field_validator("ticker", "metric_name")

    def sanitize_strings(cls, v: str) -> str:
        return v.strip()


class VarianceResult(BaseModel):
    """Output results of deterministic financial variance calculation."""

    ticker: str
    metric_name: str
    current_period_value: float
    prior_period_value: float
    absolute_change: Optional[float] = None
    percentage_change: Optional[float] = None
    direction: str
    formatted_summary: str
    is_success: bool = True
    error: Optional[str] = None
    recovery_instruction: Optional[str] = None


def calculate_financial_variance(request: VarianceRequest) -> VarianceResult:
    """Calculates deterministic variance between current and prior financial period metrics.

    Calculates absolute change (current - prior) and percentage change
    (((current - prior) / prior) * 100) for financial metrics such as Revenue,
    Operating Income, and Net Income.

    Args:
        request: VarianceRequest schema containing metric values and ticker.

    Returns:
        VarianceResult containing calculated changes, directional summary, or error
        recovery guidance.
    """
    ticker = request.ticker.upper()
    metric_name = request.metric_name.strip()

    # Parse numerical values securely
    try:
        current_val = float(request.current_period_value)
    except (ValueError, TypeError):
        return VarianceResult(
            ticker=ticker,
            metric_name=metric_name,
            current_period_value=0.0,
            prior_period_value=0.0,
            direction="Error",
            formatted_summary=f"Invalid numerical input for current_period_value: '{request.current_period_value}'",
            is_success=False,
            error=f"Cannot parse current_period_value '{request.current_period_value}' as float.",
            recovery_instruction="Ensure current_period_value is a valid numeric float or integer before calling calculate_financial_variance.",
        )

    try:
        prior_val = float(request.prior_period_value)
    except (ValueError, TypeError):
        return VarianceResult(
            ticker=ticker,
            metric_name=metric_name,
            current_period_value=current_val,
            prior_period_value=0.0,
            direction="Error",
            formatted_summary=f"Invalid numerical input for prior_period_value: '{request.prior_period_value}'",
            is_success=False,
            error=f"Cannot parse prior_period_value '{request.prior_period_value}' as float.",
            recovery_instruction="Ensure prior_period_value is a valid numeric float or integer before calling calculate_financial_variance.",
        )

    # Handle division by zero
    if prior_val == 0.0:
        abs_change = round(current_val - prior_val, 4)
        return VarianceResult(
            ticker=ticker,
            metric_name=metric_name,
            current_period_value=current_val,
            prior_period_value=prior_val,
            absolute_change=abs_change,
            percentage_change=None,
            direction="Undefined (Prior Period is 0)",
            formatted_summary=(
                f"{ticker} {metric_name} changed from {prior_val} to {current_val} {request.period_unit} "
                f"(Absolute change: {abs_change:+} {request.period_unit}, % change undefined due to zero prior period)."
            ),
            is_success=False,
            error="Division by zero: Prior period value is 0.0.",
            recovery_instruction="Prior period value is zero. Use absolute change instead of percentage change for analysis narrative.",
        )

    # Perform deterministic calculations
    abs_change = round(current_val - prior_val, 4)
    pct_change = round(((current_val - prior_val) / abs(prior_val)) * 100.0, 2)

    if abs_change > 0:
        direction = "Increase"
    elif abs_change < 0:
        direction = "Decrease"
    else:
        direction = "Unchanged"

    formatted_summary = (
        f"{ticker} {metric_name}: {current_val} {request.period_unit} vs prior {prior_val} {request.period_unit}. "
        f"Variance: {abs_change:+} {request.period_unit} ({pct_change:+}% {direction.lower()})."
    )

    return VarianceResult(
        ticker=ticker,
        metric_name=metric_name,
        current_period_value=current_val,
        prior_period_value=prior_val,
        absolute_change=abs_change,
        percentage_change=pct_change,
        direction=direction,
        formatted_summary=formatted_summary,
        is_success=True,
    )


def calculate_financial_variance_tool(
    ticker: str,
    metric_name: str,
    current_period_value: float,
    prior_period_value: float,
) -> dict:
    """Calculates absolute change ($) and percentage change (%) variance between current and prior period financial metrics.

    Args:
        ticker: Ticker symbol (e.g. AAPL, MSFT, NVDA).
        metric_name: Name of metric (e.g. Revenue, Operating Income, Net Income).
        current_period_value: Metric value in current period.
        prior_period_value: Metric value in prior comparison period.
    """
    req = VarianceRequest(
        ticker=ticker,
        metric_name=metric_name,
        current_period_value=current_period_value,
        prior_period_value=prior_period_value,
    )
    res = calculate_financial_variance(req)
    return res.model_dump()
