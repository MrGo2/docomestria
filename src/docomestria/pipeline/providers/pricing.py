"""Approximate per-million-token pricing for native providers.

OpenRouter returns the actual cost on each response, so this table is only
consulted by the native providers (`GeminiFlashLite`, `Claude`, `OpenAINative`).
Prices are USD per 1M tokens and reflect public list prices observed at
release time — they will drift. Override per call by passing explicit pricing.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelPrice:
    """USD per 1,000,000 input / output tokens."""

    input_per_million: float
    output_per_million: float

    def estimate(self, tokens_in: int, tokens_out: int) -> float:
        return (
            tokens_in * self.input_per_million / 1_000_000.0
            + tokens_out * self.output_per_million / 1_000_000.0
        )


# Approximate, may be stale. Pin a model variant where possible.
PRICING: dict[str, ModelPrice] = {
    # Google
    "gemini-2.5-flash-lite": ModelPrice(0.10, 0.40),
    "gemini-2.5-flash": ModelPrice(0.30, 2.50),
    "gemini-2.5-pro": ModelPrice(1.25, 10.0),
    # Anthropic
    "claude-haiku-4.5": ModelPrice(1.0, 5.0),
    "claude-sonnet-4.5": ModelPrice(3.0, 15.0),
    # OpenAI
    "gpt-5-nano": ModelPrice(0.05, 0.40),
    "gpt-5-mini": ModelPrice(0.25, 2.0),
    "gpt-5": ModelPrice(1.25, 10.0),
}


def estimate_usd(model: str, tokens_in: int, tokens_out: int) -> float:
    """Best-effort cost estimate; returns 0.0 if the model is unknown."""
    price = PRICING.get(model)
    if price is None:
        return 0.0
    return round(price.estimate(tokens_in, tokens_out), 8)


__all__ = ["PRICING", "ModelPrice", "estimate_usd"]
