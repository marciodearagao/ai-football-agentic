from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class ModelPricing:
    input_per_million: Decimal
    output_per_million: Decimal


MODEL_PRICING: dict[str, ModelPricing] = {
    "qwen/qwen3.8-27b": ModelPricing(
        input_per_million=Decimal("0.80"),
        output_per_million=Decimal("4.00"),
    ),
}

TOKENS_PER_MILLION = Decimal("1000000")


def estimate_cost(
    model: str | None,
    input_tokens: int | None,
    output_tokens: int | None,
) -> Decimal | None:
    if model is None or input_tokens is None or output_tokens is None:
        return None
    pricing = MODEL_PRICING.get(model)
    if pricing is None:
        return None
    input_cost = Decimal(input_tokens) / TOKENS_PER_MILLION * pricing.input_per_million
    output_cost = (
        Decimal(output_tokens) / TOKENS_PER_MILLION * pricing.output_per_million
    )
    return input_cost + output_cost
