# LLM providers

Docomestria ships four providers. Pick by trade-off, not by familiarity.

## At a glance

| Feature                       | OpenRouter            | GeminiFlashLite       | Claude                  | OpenAINative            |
|-------------------------------|-----------------------|-----------------------|-------------------------|-------------------------|
| Setup                         | One API key           | One API key           | One API key             | One API key             |
| Models available              | 200+                  | Google only           | Anthropic only          | OpenAI only             |
| Fallback chains               | Built in              | Manual                | Manual                  | Manual                  |
| Cost reporting                | Actual (per response) | Estimated from table  | Estimated from table    | Estimated from table    |
| Latency                       | + small proxy hop     | Direct                | Direct                  | Direct                  |
| Vendor features (prompt cache | Limited               | Native context cache  | Native prompt cache     | Native APIs             |
| / context cache / etc.)       |                       |                       |                         |                         |
| Required extra                | `[openrouter]`        | `[gemini]`            | `[claude]`              | `[openai]`              |

## OpenRouter — recommended default

```python
from docomestria.pipeline.providers import OpenRouter

llm = OpenRouter(
    api_key=os.environ["OPENROUTER_API_KEY"],
    models=(
        "google/gemini-2.5-flash-lite",
        "anthropic/claude-haiku-4.5",
    ),
    route="fallback",   # walk the list locally on errors
)
```

Other `route` values:

- `"lowest-cost"` — let OpenRouter pick the cheapest model from the list.
- `"fastest"` — let OpenRouter pick the fastest model from the list.

The provider returns the actual USD cost in `LLMResponse.usd` (OpenRouter
populates `usage.cost` when `extra_body.usage.include=True`, which we set).

## Native Gemini

```python
from docomestria.pipeline.providers import GeminiFlashLite

llm = GeminiFlashLite(api_key=os.environ["GEMINI_API_KEY"])
# or any other Gemini model:
llm = GeminiFlashLite(api_key=..., model="gemini-2.5-pro")
```

Uses `google-genai`. Cost is estimated from the local pricing table.

## Native Claude

```python
from docomestria.pipeline.providers import Claude

llm = Claude(
    api_key=os.environ["ANTHROPIC_API_KEY"],
    model="claude-haiku-4.5",
)
```

Uses `anthropic`. Cost is estimated from the local pricing table.

## Native OpenAI

```python
from docomestria.pipeline.providers import OpenAINative

llm = OpenAINative(
    api_key=os.environ["OPENAI_API_KEY"],
    model="gpt-5-nano",
)
```

Uses `openai`. Cost is estimated from the local pricing table.

## Implementing your own

Any object with a `complete(system, user, *, response_format=None) -> LLMResponse`
method satisfies the `LLMProvider` protocol. The Pipeline only needs that.

```python
from docomestria.pipeline.providers import LLMResponse

class MyProvider:
    model = "my-model"
    def complete(self, system, user, *, response_format=None) -> LLMResponse:
        text = my_llm_call(system, user)
        return LLMResponse(
            text=text,
            model_used=self.model,
            tokens_in=0, tokens_out=0, usd=0.0,
        )
```
