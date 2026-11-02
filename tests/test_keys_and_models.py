import os

import pytest

from content_workshop import llm
from content_workshop.config import Settings
from content_workshop.schemas import DialectReport

from test_dashboard import app  # noqa: F401  (fixture)


def test_key_is_cleaned_checked_and_saved(app, monkeypatch):  # noqa: F811
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    seen = []
    app.verify_key = seen.append
    app.save_key('  ANTHROPIC_API_KEY="sk-ant-api03-abc\ndef"  ')
    assert seen == ["sk-ant-api03-abcdef"]
    assert "ANTHROPIC_API_KEY=sk-ant-api03-abcdef" in app.env_path.read_text(encoding="utf-8")
    assert os.environ["ANTHROPIC_API_KEY"] == "sk-ant-api03-abcdef"


def test_rejected_key_is_not_saved(app, monkeypatch):  # noqa: F811
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    def reject(key):
        raise ValueError("Anthropic rejected this key")
    app.verify_key = reject
    with pytest.raises(ValueError, match="rejected"):
        app.save_key("sk-ant-api03-bad")
    assert not app.env_path.exists() and "ANTHROPIC_API_KEY" not in os.environ


@pytest.mark.parametrize("key,word", [("sk-ant-admin01-x", "Admin key"), ("sk-ant-oat01-x", "sign-in token")])
def test_wrong_kind_of_key_is_explained(key, word):
    with pytest.raises(ValueError, match=word):
        llm.verify_key(key)


def test_pick_model(app, monkeypatch):  # noqa: F811
    monkeypatch.delenv("CW_MODEL", raising=False)
    assert Settings().model == "claude-haiku-5-5"
    st = app.save_model("claude-opus-5-5")
    assert st["model"] == "claude-opus-5-5" and Settings().model == "claude-opus-5-5"
    assert "CW_MODEL=claude-opus-5-5" in app.env_path.read_text(encoding="utf-8")
    with pytest.raises(ValueError):
        app.save_model("gpt-4")


class FakeClient:
    def __init__(self):
        self.calls = []
        self.beta = self
        self.messages = self

    def parse(self, **kw):
        self.calls.append(kw)

        class Usage:
            input_tokens = output_tokens = 1

        class Resp:
            usage, stop_reason = Usage(), "end_turn"
            parsed_output = DialectReport(score=9, issues=[])
        return Resp()


@pytest.mark.parametrize("model,fallback", [("claude-haiku-5-5", False), ("claude-opus-5-5", True),
                                            ("claude-sonnet-5-5", True)])
def test_fallback_only_where_supported(model, fallback):
    client = FakeClient()
    llm.LLM(Settings(model=model), client=client).ask("s", "u", DialectReport)
    assert ("fallbacks" in client.calls[0]) is fallback
