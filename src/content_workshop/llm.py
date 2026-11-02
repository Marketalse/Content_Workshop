"""Thin wrapper around the Anthropic SDK.

Every committee member calls `LLM.ask(system, user, schema)` and gets back a validated
Pydantic object. Tests swap this class for a fake with the same method.
"""

from __future__ import annotations

from typing import Protocol, TypeVar

import anthropic
from pydantic import BaseModel

from .config import Settings

T = TypeVar("T", bound=BaseModel)

FALLBACK_BETA = "server-side-fallback-2026-07-01"


class SupportsAsk(Protocol):
    def ask(self, system: str, user: str, schema: type[T]) -> T: ...


class RefusalError(RuntimeError):
    """The model (and its server-side fallback) declined the request."""


class LLM:
    def __init__(self, settings: Settings | None = None, client: anthropic.Anthropic | None = None):
        self.settings = settings or Settings()
        self.client = client or anthropic.Anthropic()
        self.usage: list[dict] = []

    def ask(self, system: str, user: str, schema: type[T]) -> T:
        s = self.settings
        try:
            response = self.client.beta.messages.parse(
                model=s.model,
                max_tokens=s.max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
                output_format=schema,
                thinking={"type": "adaptive"},
                output_config={"effort": s.effort},
                # If a request is declined, the API retries it on a fallback model in the same call.
                betas=[FALLBACK_BETA],
                fallbacks="default",
            )
        except anthropic.RateLimitError as e:
            raise RuntimeError("Rate limited by the Anthropic API; try again shortly.") from e
        except anthropic.AuthenticationError as e:
            raise RuntimeError("ANTHROPIC_API_KEY is missing or invalid.") from e
        except anthropic.APIStatusError as e:
            raise RuntimeError(f"Anthropic API error {e.status_code}: {e.message}") from e
        except anthropic.APIConnectionError as e:
            raise RuntimeError("Could not reach the Anthropic API.") from e

        u = response.usage
        self.usage.append(
            {"schema": schema.__name__, "input_tokens": u.input_tokens, "output_tokens": u.output_tokens}
        )

        if response.stop_reason == "refusal":
            raise RefusalError(f"Request declined while producing {schema.__name__}.")
        if response.stop_reason == "max_tokens":
            raise RuntimeError(f"Output cut off while producing {schema.__name__}; raise max_tokens.")
        if response.parsed_output is None:
            raise RuntimeError(f"No structured output returned for {schema.__name__}.")
        return response.parsed_output
