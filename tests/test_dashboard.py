import json
import threading
import time
import urllib.error
import urllib.request

import pytest

from content_workshop import dashboard
from content_workshop.committee import Committee
from content_workshop.config import Settings

from test_committee_and_log import FakeLLM


@pytest.fixture
def app(tmp_path):
    sheet = tmp_path / "sheet.csv"
    sheet.write_text("#,Iraqi,Arabic\n1,شكال,قال\n", encoding="utf-8")
    return dashboard.App(
        output_dir=tmp_path / "output", log_path=tmp_path / "log.jsonl", sheet_path=sheet,
        pending_path=tmp_path / "pending.csv", env_path=tmp_path / ".env",
        make_committee=lambda wpm, progress: Committee(FakeLLM(), Settings(max_revisions=2), wpm=wpm,
                                                       progress=progress, queue_words=False),
    )


@pytest.fixture
def server(app):
    port = 18765
    httpd = dashboard.ThreadingHTTPServer(("127.0.0.1", port), dashboard.make_handler(app, port))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{port}", app
    httpd.shutdown()
    httpd.server_close()


def call(base, path, body=None, token=None):
    req = urllib.request.Request(base + path, data=None if body is None else json.dumps(body).encode(),
                                 headers={"X-CW-Token": token or "", "Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


def test_generate_then_library_and_tracking(app):
    job = app.start_generate("موضوع", ["short_video"], ["simple"], 140)
    for _ in range(100):
        if app.job(job["id"])["state"] != "running":
            break
        time.sleep(0.05)
    j = app.job(job["id"])
    assert j["state"] == "done", j["error"]
    assert j["log"] and j["run"]

    runs = app.runs()
    assert runs[0]["topic"] == "موضوع" and runs[0]["drafts"] == 1
    run = app.run(runs[0]["name"])
    draft = run["drafts"][0]
    assert draft["plain_text"]

    res = app.log_edited(draft["id"], draft["plain_text"], 0)
    assert res["edit_ratio"] == 0.0 and res["light"]
    app.log_metrics(draft["id"], {"views": "1200", "retention": "41"})
    tracked = app.drafts()[0]
    assert tracked["edited"]["edit_ratio"] == 0.0
    assert tracked["metrics"] == {"views": 1200.0, "retention": 0.41}
    assert app.report()["reviewed"] == 1


def test_run_name_cannot_escape_output(app):
    with pytest.raises(KeyError):
        app.run("../log")


def test_words_queue(app):
    assert app.add_word("كلش", "جداً", "كلش حلو")["queued"]
    assert not app.add_word("شكال", "قال", "")["queued"]  # already in the sheet
    assert [w["Iraqi"] for w in app.words()] == ["كلش"]
    rows = app.decide_words(["كلش"], approve=True)["rows"]
    assert rows == [["2", "كلش", "جداً"]]
    assert app.words() == []


def test_save_key(app, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(ValueError):
        app.save_key("not-a-key")
    app.env_path.write_text("CW_EFFORT=high\nANTHROPIC_API_KEY=old\n", encoding="utf-8")
    assert app.save_key("sk-ant-api-123456789")["api_key_set"]
    assert app.env_path.read_text(encoding="utf-8") == "CW_EFFORT=high\nANTHROPIC_API_KEY=sk-ant-api-123456789\n"


def test_http_needs_token(server):
    base, app = server
    page = urllib.request.urlopen(base + "/").read().decode()
    assert app.token in page and "__CW_TOKEN__" not in page
    with pytest.raises(urllib.error.HTTPError) as e:
        call(base, "/api/status")
    assert e.value.code == 403
    status = call(base, "/api/status", token=app.token)
    assert "short_video" in status["formats"]
    res = call(base, "/api/check", {"text": "شكال", "wpm": 140}, token=app.token)
    assert res["seconds"] > 0
