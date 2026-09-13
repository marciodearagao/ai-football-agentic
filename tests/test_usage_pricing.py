from decimal import Decimal

from app.usage.pricing import estimate_cost


def test_known_model_calculates_expected_cost() -> None:
    cost = estimate_cost("qwen/qwen3.8-27b", 1_000, 500)

    assert cost == Decimal("0.002800")


def test_unknown_model_returns_unavailable_cost() -> None:
    assert estimate_cost("unknown-model", 1_000, 500) is None


def test_zero_tokens_produce_zero_cost() -> None:
    assert estimate_cost("qwen/qwen3.8-27b", 0, 0) == Decimal("0")


def test_input_and_output_pricing_are_applied_independently() -> None:
    input_only = estimate_cost("qwen/qwen3.8-27b", 1_000_000, 0)
    output_only = estimate_cost("qwen/qwen3.8-27b", 0, 1_000_000)

    assert input_only == Decimal("0.80")
    assert output_only == Decimal("4.00")
