"""Cost tracking and Gemini token pricing model for GCP Vertex AI usage."""

import logging
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class CostBreakdown(BaseModel):
    """Detailed breakdown of token counts, USD costs, and context caching savings."""

    model_name: str
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    standard_input_cost_usd: float = 0.0
    cached_input_cost_usd: float = 0.0
    output_cost_usd: float = 0.0
    total_cost_usd: float = 0.0
    cached_savings_usd: float = 0.0
    is_pricing_known: bool = True
    warning: Optional[str] = None


# Pricing per 1,000,000 tokens (USD)
MODEL_PRICING: Dict[str, Dict[str, float]] = {
    "gemini-2.5-pro": {
        "input_per_m": 1.25,
        "cached_input_per_m": 0.3125,
        "output_per_m": 5.00,
    },
    "gemini-3.5-flash": {
        "input_per_m": 0.075,
        "cached_input_per_m": 0.01875,
        "output_per_m": 0.30,
    },
    "gemini-2.5-flash": {
        "input_per_m": 0.075,
        "cached_input_per_m": 0.01875,
        "output_per_m": 0.30,
    },
}


class CostTracker:
    """Calculates LLM token usage cost and context caching discount savings."""

    @staticmethod
    def calculate_cost(
        model_name: str,
        input_tokens: int,
        output_tokens: int,
        cached_tokens: int = 0,
    ) -> CostBreakdown:
        """Calculates itemized USD costs and context caching savings for a given model invocation.

        If the model is not recognized in the pricing catalog, returns cost 0.0 with is_pricing_known=False
        and logs an explicit warning rather than guessing rates with arbitrary default fallbacks.

        Args:
            model_name: Name of the Gemini model used.
            input_tokens: Total non-cached input tokens.
            output_tokens: Total generated output tokens.
            cached_tokens: Number of input tokens served from Vertex AI Context Cache.

        Returns:
            CostBreakdown object with calculated financial metrics.
        """
        normalized_model = model_name.lower().strip() if model_name else ""
        pricing: Optional[Dict[str, float]] = None

        for key, rate in MODEL_PRICING.items():
            if key in normalized_model:
                pricing = rate
                break

        if not pricing:
            warn_msg = f"UNRECOGNIZED_MODEL_PRICING: Model '{model_name}' is not listed in MODEL_PRICING catalog. Setting estimated cost to 0.0 USD."
            logger.warning(warn_msg)
            return CostBreakdown(
                model_name=model_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cached_tokens=cached_tokens,
                standard_input_cost_usd=0.0,
                cached_input_cost_usd=0.0,
                output_cost_usd=0.0,
                total_cost_usd=0.0,
                cached_savings_usd=0.0,
                is_pricing_known=False,
                warning=warn_msg,
            )

        input_rate = pricing["input_per_m"] / 1_000_000.0
        cached_rate = pricing["cached_input_per_m"] / 1_000_000.0
        output_rate = pricing["output_per_m"] / 1_000_000.0

        standard_input_cost = round(input_tokens * input_rate, 6)
        cached_input_cost = round(cached_tokens * cached_rate, 6)
        output_cost = round(output_tokens * output_rate, 6)

        # Savings = what cached tokens would have cost at standard input rate minus actual cached input cost
        cached_savings = round((cached_tokens * input_rate) - cached_input_cost, 6)
        total_cost = round(standard_input_cost + cached_input_cost + output_cost, 6)

        return CostBreakdown(
            model_name=model_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_tokens=cached_tokens,
            standard_input_cost_usd=standard_input_cost,
            cached_input_cost_usd=cached_input_cost,
            output_cost_usd=output_cost,
            total_cost_usd=total_cost,
            cached_savings_usd=max(0.0, cached_savings),
            is_pricing_known=True,
            warning=None,
        )
