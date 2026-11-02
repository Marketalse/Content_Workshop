"""Thin wrapper around the Anthropic SDK.

Every committee member calls `LLM.ask(system, user, schema)` and gets back a validated
Pydantic object. Tests swap this class for a fake with the same method.
"""

from __future__ import annotations

import os
from typing import Protocol, TypeVar

import anthropic
from pydantic import BaseModel

from .config import Settings

T = TypeVar("T", bound=BaseModel)

FALLBACK_BETA = "server-side-fallback-2026-07-01"

# Models the owner can pick in Settings. Prices are per 1M tokens (input / output), Claude API.
MODELS = {
    "claude-haiku-5-5": {"name": "Claude Haiku 5.5", "price": "$0.10 / $0.50", "note": "Cheapest. Good for trying things out."},
    "claude-sonnet-5-5": {"name": "Claude Sonnet 5.5", "price": "$2 / $10", "note": "Middle option."},
    "claude-opus-5-5": {"name": "Claude Opus 5.5", "price": "$4 / $20", "note": "Strongest writing and dialect judgement."},
}


def supports_fallback(model: str) -> bool:
    """Server-side refusal fallback exists for Opus/Sonnet/Fable; Haiku 5.5 has none (sending it is an error)."""
    return not model.startswith("claude-haiku")


def _why(e: anthropic.APIStatusError) -> str:
    """The API's own one-line reason (e.g. 'invalid x-api-key'), without the raw JSON around it."""
    body = e.body if isinstance(e.body, dict) else {}
    return (body.get("error") or {}).get("message") or e.message


def verify_key(key: str) -> None:
    """Check a key with the Anthropic API before saving it (listing models is free).

    Raises ValueError with a plain explanation when the key is the wrong kind or is rejected.
    Network trouble is not treated as a bad key.
    """
    if key.startswith("sk-ant-admin"):
        raise ValueError("That's an Admin key, which can't write content. In console.anthropic.com go to "
                         "API Keys → Create Key and paste that one (it starts with sk-ant-api).")
    if key.startswith(("sk-ant-oat", "sk-ant-ort", "sk-ant-sid")):
        raise ValueError("That's a sign-in token from the Claude app or Claude Code, not an API key. In "
                         "console.anthropic.com go to API Keys → Create Key (it starts with sk-ant-api).")
    client = anthropic.Anthropic(api_key=key, max_retries=1, timeout=20)
    try:
        client.models.list(limit=1)
    except anthropic.AuthenticationError as e:
        raise ValueError(f"Anthropic rejected this key ({_why(e)}). Copy it again from console.anthropic.com "
                         "→ API Keys; a key that was deleted or disabled there stops working.") from e
    except anthropic.PermissionDeniedError as e:
        raise ValueError(f"This key isn't allowed to use the API ({_why(e)}).") from e
    except anthropic.APIConnectionError:
        return  # offline: can't tell; save it and let the first run say more


class SupportsAsk(Protocol):
    def ask(self, system: str, user: str, schema: type[T]) -> T: ...


class RefusalError(RuntimeError):
    """The model (and its server-side fallback) declined the request."""


class LLM:
    def __init__(self, settings: Settings | None = None, client: anthropic.Anthropic | None = None):
        self.settings = settings or Settings()
        # Only the saved key is used (never a sign-in token that happens to be in the environment).
        self.client = client or anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY") or None)
        self.usage: list[dict] = []

    def ask(self, system: str, user: str, schema: type[T]) -> T:
        s = self.settings
        extra = {}
        if supports_fallback(s.model):
            # If a request is declined, the API retries it on a fallback model in the same call.
            extra = {"betas": [FALLBACK_BETA], "fallbacks": "default"}
        try:
            response = self.client.beta.messages.parse(
                model=s.model,
                max_tokens=s.max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
                output_format=schema,
                thinking={"type": "adaptive"},
                output_config={"effort": s.effort},
                **extra,
            )
        except anthropic.RateLimitError as e:
            raise RuntimeError("Rate limited by the Anthropic API; try again shortly.") from e
        except anthropic.AuthenticationError as e:
            raise RuntimeError(f"Anthropic rejected the API key ({_why(e)}). Save a new key in Settings; "
                               "it's checked before it's saved.") from e
        except anthropic.APIStatusError as e:
            raise RuntimeError(f"Anthropic API error {e.status_code}: {_why(e)}") from e
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
