"""Local dashboard: `content-workshop dashboard` opens the workshop in your browser.

Standard library only (no extra installs). The server listens on 127.0.0.1, so only this computer
can reach it, and every API call must carry a per-session token that is embedded in the page.
Nothing is ever posted anywhere: the dashboard writes the same files the command line does.
"""

from __future__ import annotations

import json
import os
import secrets
import subprocess
import sys
import threading
import traceback
import uuid
import webbrowser
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable

from . import checks, dialect, logbook
from .config import DATA_DIR, ENV_FILE, FORMATS, INSTALLED, LEVELS, OUTPUT_DIR, Settings
from .schemas import CommitteeResult, Script
from .updater import Updater

PAGE = Path(__file__).resolve().parent / "web" / "dashboard.html"


def _default_committee(wpm: float, progress: Callable[[str], None]):
    from .committee import Committee
    from .llm import LLM

    settings = Settings()
    return Committee(LLM(settings), settings, wpm=wpm, progress=progress)


@dataclass
class App:
    """Everything the API touches, so tests can point it at temporary folders and a fake model."""

    output_dir: Path = OUTPUT_DIR
    log_path: Path = logbook.LOG
    sheet_path: Path = dialect.SHEET
    pending_path: Path = dialect.PENDING
    env_path: Path = ENV_FILE
    data_dir: Path = DATA_DIR
    updater: Updater = field(default_factory=Updater)
    on_restart: Callable | None = None   # set by serve(): restart into the updated program
    on_shutdown: Callable | None = None  # set by serve(): stop the dashboard
    make_committee: Callable = _default_committee
    token: str = field(default_factory=lambda: secrets.token_urlsafe(24))
    jobs: dict = field(default_factory=dict)
    lock: threading.Lock = field(default_factory=threading.Lock)

    # -- status & key ------------------------------------------------------------------------

    def status(self) -> dict:
        key = os.environ.get("ANTHROPIC_API_KEY", "")
        return {
            "api_key_set": bool(key),
            "api_key_hint": f"…{key[-4:]}" if len(key) > 8 else "",
            "model": Settings().model,
            "formats": list(FORMATS),
            "levels": list(LEVELS),
            "default_wpm": checks.DEFAULT_WPM,
            "pending_words": len(dialect.pending(self.pending_path)),
            "running": self._running(),
            "version": self.updater.current(),
            "installed": INSTALLED,
            "can_open_folders": INSTALLED and sys.platform == "darwin",
            "folders": {"drafts": str(self.output_dir), "data": str(self.data_dir)},
        }

    def _running(self) -> list[str]:
        return [j["id"] for j in self.jobs.values() if j["state"] == "running"]

    # -- updates, folders, stop --------------------------------------------------------------

    def update_check(self) -> dict:
        return self.updater.check()

    def update_apply(self) -> dict:
        if self._running():
            raise ValueError("Wait until the current drafts are finished, then update.")
        res = self.updater.apply()
        if res.get("updated") and self.on_restart:
            threading.Timer(0.6, self.on_restart).start()
            res["restarting"] = True
        return res

    def open_folder(self, which: str) -> dict:
        path = {"drafts": self.output_dir, "data": self.data_dir}.get(which)
        if path is None:
            raise ValueError("Unknown folder.")
        if sys.platform != "darwin":
            raise ValueError(f"Open this folder yourself: {path}")
        path.mkdir(parents=True, exist_ok=True)
        subprocess.run(["open", str(path)], check=False)
        return {"opened": str(path)}

    def stop(self) -> dict:
        if self._running():
            raise ValueError("Drafts are still being written. Stop after they finish.")
        if self.on_shutdown:
            threading.Timer(0.3, self.on_shutdown).start()
        return {"stopping": True}

    def save_key(self, key: str) -> dict:
        key = key.strip()
        if not key.startswith("sk-ant-") or any(c.isspace() for c in key):
            raise ValueError("That doesn't look like an Anthropic API key (it starts with sk-ant-).")
        lines = self.env_path.read_text(encoding="utf-8").splitlines() if self.env_path.exists() else []
        lines = [ln for ln in lines if not ln.strip().startswith("ANTHROPIC_API_KEY=")]
        lines.append(f"ANTHROPIC_API_KEY={key}")
        self.env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        try:
            os.chmod(self.env_path, 0o600)
        except OSError:
            pass
        os.environ["ANTHROPIC_API_KEY"] = key
        return self.status()

    # -- generate ----------------------------------------------------------------------------

    def start_generate(self, topic: str, formats: list[str], levels: list[str], wpm: float) -> dict:
        topic = topic.strip()
        if not topic:
            raise ValueError("Write a topic first.")
        formats = [f for f in formats if f in FORMATS]
        levels = [lv for lv in levels if lv in LEVELS]
        if not formats or not levels:
            raise ValueError("Pick at least one format and one level.")
        if not os.environ.get("ANTHROPIC_API_KEY") and self.make_committee is _default_committee:
            raise ValueError("Add your Anthropic API key first (Settings).")
        job = {"id": uuid.uuid4().hex[:10], "state": "running", "topic": topic, "log": [],
               "total_steps": 2 + 3 * len(formats) * len(levels), "run": None, "error": None}
        with self.lock:
            self.jobs[job["id"]] = job
        threading.Thread(target=self._run, args=(job, formats, levels, wpm), daemon=True).start()
        return self._job_view(job)

    def _run(self, job: dict, formats: list[str], levels: list[str], wpm: float) -> None:
        from .render import save

        try:
            committee = self.make_committee(wpm, lambda msg: job["log"].append(msg))
            result = committee.run(job["topic"], formats, levels)
            md = save(result, self.output_dir)
            for d in result.drafts:
                logbook.log_draft(job["topic"], d, self.log_path)
            job["run"] = md.stem
            job["state"] = "done"
        except Exception as e:  # shown to the owner in the page
            traceback.print_exc()
            job["error"] = str(e) or e.__class__.__name__
            job["state"] = "failed"

    def _job_view(self, job: dict) -> dict:
        return {k: job[k] for k in ("id", "state", "topic", "log", "total_steps", "run", "error")}

    def job(self, job_id: str) -> dict:
        job = self.jobs.get(job_id)
        if job is None:
            raise KeyError("No such job.")
        return self._job_view(job)

    # -- library -----------------------------------------------------------------------------

    def runs(self) -> list[dict]:
        out = []
        for f in sorted(self.output_dir.glob("*.json"), reverse=True):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            drafts = data.get("drafts", [])
            out.append({"name": f.stem, "topic": data.get("topic", ""), "drafts": len(drafts),
                        "passed": sum(1 for d in drafts if d.get("passed"))})
        return out

    def run(self, name: str) -> dict:
        path = (self.output_dir / f"{name}.json").resolve()
        if path.parent != self.output_dir.resolve() or not path.exists():
            raise KeyError("No such run.")
        result = CommitteeResult.model_validate_json(path.read_text(encoding="utf-8"))
        data = result.model_dump()
        status = self._draft_status()
        for d, draft in zip(data["drafts"], result.drafts):
            d["plain_text"] = draft.script.plain_text()
            d.update(status.get(draft.id, {}))
        data["name"] = name
        return data

    def _draft_status(self) -> dict[str, dict]:
        status: dict[str, dict] = {}
        for r in logbook.read(self.log_path):
            s = status.setdefault(r["id"], {})
            if r["event"] == "edited":
                s["edited"] = {"edit_ratio": r["edit_ratio"], "dialect_fixes": r["dialect_fixes"],
                               "final_text": r.get("final_text", "")}
            elif r["event"] == "metrics":
                s["metrics"] = {k: v for k, v in r.items() if k not in ("event", "id", "at")}
        return status

    # -- tracking ----------------------------------------------------------------------------

    def drafts(self) -> list[dict]:
        status = self._draft_status()
        out = []
        for r in reversed(logbook.read(self.log_path)):
            if r["event"] != "generated":
                continue
            out.append({k: r.get(k) for k in ("id", "at", "topic", "format", "level", "critic_total",
                                                "dialect_score", "passed", "text")} | status.get(r["id"], {}))
        return out

    def log_edited(self, draft_id: str, final: str, dialect_fixes: int) -> dict:
        if not final.strip():
            raise ValueError("Paste the text you actually posted.")
        ratio = logbook.log_edit(draft_id, final, int(dialect_fixes), self.log_path)
        return {"edit_ratio": ratio, "light": ratio <= logbook.LIGHT_EDIT}

    def log_metrics(self, draft_id: str, metrics: dict) -> dict:
        clean = {}
        for k in ("views", "retention", "replies", "saves", "shares"):
            v = metrics.get(k)
            if v not in (None, ""):
                clean[k] = float(v)
        if not clean:
            raise ValueError("Fill in at least one number.")
        if "retention" in clean and clean["retention"] > 1:
            clean["retention"] = clean["retention"] / 100  # typed as a percentage
        logbook.log_metrics(draft_id, self.log_path, **clean)
        return {"ok": True}

    def report(self) -> dict:
        return logbook.report(self.log_path) | {
            "targets": {"light_edit_share": logbook.TARGET_LIGHT_SHARE,
                        "dialect_fixes_per_10_lines": logbook.TARGET_DIALECT_FIXES_PER_10,
                        "sample": logbook.WINDOW, "light_edit_max": logbook.LIGHT_EDIT}}

    # -- words -------------------------------------------------------------------------------

    def words(self) -> list[dict]:
        return dialect.pending(self.pending_path)

    def decide_words(self, words: list[str], approve: bool) -> dict:
        if not words:
            raise ValueError("Pick at least one word.")
        rows = dialect.decide(words, approve, self.sheet_path, self.pending_path)
        return {"rows": rows}

    def sync_words(self) -> dict:
        return dialect.sync_from_google(self.sheet_path)

    def add_word(self, iraqi: str, arabic: str, example: str) -> dict:
        if not iraqi.strip() or not arabic.strip():
            raise ValueError("Fill in both the Iraqi word and its Arabic meaning.")
        ok = dialect.propose(iraqi, arabic, "manual", example, self.sheet_path, self.pending_path)
        return {"queued": ok}

    # -- check -------------------------------------------------------------------------------

    def check(self, text: str, fmt: str, wpm: float) -> dict:
        if not text.strip():
            raise ValueError("Paste some text to check.")
        fmt = fmt if fmt in FORMATS else "short_video"
        script = Script(format=fmt, level="medium", title="", hook=text, beats=[], cta="")
        issues = checks.language(script)
        return {"seconds": round(checks.seconds(text, wpm), 1), "issues": [i.model_dump() for i in issues]}


# -- HTTP layer ------------------------------------------------------------------------------------

def make_handler(app: App, port: int):
    allowed_hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):  # keep the window quiet
            pass

        def _send(self, status: int, body: bytes, ctype: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, data, status: int = 200) -> None:
            self._send(status, json.dumps(data, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

        def _guard(self) -> bool:
            if self.headers.get("Host", "") not in allowed_hosts:
                self._json({"error": "Bad host."}, HTTPStatus.FORBIDDEN)
                return False
            if self.path.startswith("/api/") and not secrets.compare_digest(
                    self.headers.get("X-CW-Token", ""), app.token):
                self._json({"error": "Reload the dashboard page."}, HTTPStatus.FORBIDDEN)
                return False
            return True

        def _body(self) -> dict:
            n = int(self.headers.get("Content-Length") or 0)
            return json.loads(self.rfile.read(n) or b"{}") if n else {}

        def _call(self, fn) -> None:
            try:
                self._json(fn())
            except (ValueError, TypeError) as e:
                self._json({"error": str(e)}, HTTPStatus.BAD_REQUEST)
            except KeyError as e:
                self._json({"error": str(e.args[0]) if e.args else "Not found."}, HTTPStatus.NOT_FOUND)
            except Exception as e:
                traceback.print_exc()
                self._json({"error": str(e)}, HTTPStatus.INTERNAL_SERVER_ERROR)

        def do_GET(self):
            if not self._guard():
                return
            path = self.path.split("?", 1)[0]
            if path == "/healthz":  # lets the Mac app see the dashboard is already running
                return self._json({"app": "content-workshop"})
            if path in ("/", "/index.html"):
                html = PAGE.read_text(encoding="utf-8").replace("__CW_TOKEN__", app.token)
                return self._send(200, html.encode("utf-8"), "text/html; charset=utf-8")
            routes = {
                "/api/status": app.status,
                "/api/runs": app.runs,
                "/api/drafts": app.drafts,
                "/api/report": app.report,
                "/api/words": app.words,
                "/api/update/check": app.update_check,
            }
            if path in routes:
                return self._call(routes[path])
            if path.startswith("/api/runs/"):
                return self._call(lambda: app.run(path.removeprefix("/api/runs/")))
            if path.startswith("/api/jobs/"):
                return self._call(lambda: app.job(path.removeprefix("/api/jobs/")))
            self._json({"error": "Not found."}, HTTPStatus.NOT_FOUND)

        def do_POST(self):
            if not self._guard():
                return
            try:
                b = self._body()
            except (ValueError, json.JSONDecodeError):
                return self._json({"error": "Bad request."}, HTTPStatus.BAD_REQUEST)
            routes = {
                "/api/key": lambda: app.save_key(b.get("key", "")),
                "/api/generate": lambda: app.start_generate(b.get("topic", ""), b.get("formats", []),
                                                            b.get("levels", []),
                                                            float(b.get("wpm") or checks.DEFAULT_WPM)),
                "/api/check": lambda: app.check(b.get("text", ""), b.get("format", "short_video"),
                                                float(b.get("wpm") or checks.DEFAULT_WPM)),
                "/api/words/approve": lambda: app.decide_words(b.get("words", []), True),
                "/api/words/reject": lambda: app.decide_words(b.get("words", []), False),
                "/api/words/add": lambda: app.add_word(b.get("iraqi", ""), b.get("arabic", ""),
                                                       b.get("example", "")),
                "/api/log/edited": lambda: app.log_edited(b.get("id", ""), b.get("final", ""),
                                                          int(b.get("dialect_fixes") or 0)),
                "/api/log/metrics": lambda: app.log_metrics(b.get("id", ""), b.get("metrics", {})),
                "/api/words/sync": app.sync_words,
                "/api/update/apply": app.update_apply,
                "/api/open-folder": lambda: app.open_folder(b.get("which", "")),
                "/api/stop": app.stop,
            }
            if self.path in routes:
                return self._call(routes[self.path])
            self._json({"error": "Not found."}, HTTPStatus.NOT_FOUND)

    return Handler


def serve(port: int = 8765, open_browser: bool = True, app: App | None = None) -> None:
    app = app or App()
    url = f"http://127.0.0.1:{port}/"
    if INSTALLED:
        dialect.prepare_local_words(app.sheet_path, app.pending_path)
    try:
        httpd = ThreadingHTTPServer(("127.0.0.1", port), make_handler(app, port))
    except OSError:
        # Most likely the dashboard is already running: just show it.
        print(f"The dashboard seems to be open already: {url}")
        if open_browser:
            webbrowser.open(url)
        return

    def restart() -> None:  # after an update: start again on the new code, same port and settings
        httpd.server_close()
        os.execv(sys.executable, [sys.executable, "-m", "content_workshop", "dashboard",
                                  "--no-browser", "--port", str(port)])

    app.on_restart = restart
    app.on_shutdown = httpd.shutdown
    print(f"Content Workshop dashboard: {url}", flush=True)
    if not INSTALLED:
        print("Keep this window open while you use it. Close it (or press Ctrl+C) to stop.")
    if open_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
