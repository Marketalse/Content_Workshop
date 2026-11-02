import io
import json
import tarfile
import urllib.request

import pytest

from content_workshop import dialect
from content_workshop.updater import Updater

from test_dashboard import app, server  # noqa: F401  (fixtures)


def write_sheet(path, rows):
    dialect._write_rows(path, rows)


# --- word sheet ------------------------------------------------------------------------------------

def test_merge_keeps_repo_fixes_and_owner_words():
    base = [["1", "شنو", "ماذا"], ["2", "تبلش", "تبدأ"]]
    local = [["1", "شنو", "ماذا"], ["2", "تبلش", "تبدء"], ["3", "كلش", "جداً"]]
    assert dialect.merge_sheets(base, local) == [["1", "شنو", "ماذا"], ["2", "تبلش", "تبدأ"], ["3", "كلش", "جداً"]]


def test_prepare_local_words(tmp_path):
    repo_sheet, repo_pending = tmp_path / "repo.csv", tmp_path / "repo_pending.csv"
    sheet, pending = tmp_path / "Data" / "words" / "iraqi_words.csv", tmp_path / "Data" / "words" / "new.csv"
    write_sheet(repo_sheet, [["1", "شنو", "ماذا"]])
    dialect._write_pending([{"Iraqi": "هواية", "Arabic": "كثير", "source": "claude", "example": "",
                             "added_at": "2026-11-02", "status": "pending"}], repo_pending)
    dialect.prepare_local_words(sheet, pending, repo_sheet, repo_pending)
    assert dialect._read_rows(sheet) == [["1", "شنو", "ماذا"]]
    assert [r["Iraqi"] for r in dialect.pending(pending)] == ["هواية"]

    dialect.decide(["هواية"], approve=True, sheet_path=sheet, pending_path=pending)
    write_sheet(repo_sheet, [["1", "شنو", "ماذا"], ["2", "تبلش", "تبدأ"]])  # an update brings a new word
    dialect.prepare_local_words(sheet, pending, repo_sheet, repo_pending)
    assert [r[1] for r in dialect._read_rows(sheet)] == ["شنو", "تبلش", "هواية"]
    assert dialect.pending(pending) == []  # approved here, so not offered again


def test_sync_from_google_adds_only_new_rows(tmp_path):
    sheet = tmp_path / "sheet.csv"
    write_sheet(sheet, [["1", "شنو", "ماذا"], ["2", "تبلش", "تبدأ"]])
    google = "﻿#,Iraqi,Arabic\r\n1,شنو,ماذا\r\n2,تبلش,تبدء\r\n3,كلش,جداً\r\n"
    res = dialect.sync_from_google(sheet, fetch=lambda url: google)
    assert res["added"] == [["3", "كلش", "جداً"]]
    assert res["different"] == [{"iraqi": "تبلش", "here": "تبدأ", "google": "تبدء"}]
    assert dialect._read_rows(sheet)[1] == ["2", "تبلش", "تبدأ"]  # not overwritten
    assert dialect.sync_from_google(sheet, fetch=lambda url: google)["added"] == []


def test_sync_from_google_reports_network_errors(tmp_path):
    def boom(url):
        raise OSError("offline")
    with pytest.raises(ValueError, match="Google Sheet"):
        dialect.sync_from_google(tmp_path / "s.csv", fetch=boom)


# --- updater ---------------------------------------------------------------------------------------

def tarball(files: dict[str, tuple[str, int]]) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for name, (text, mode) in files.items():
            data = text.encode()
            info = tarfile.TarInfo(name)
            info.size, info.mode = len(data), mode
            tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def make_install(tmp_path, pyproject="v1"):
    prog = tmp_path / ".program"
    code = prog / "code"
    code.mkdir(parents=True)
    (code / "pyproject.toml").write_text(pyproject)
    (code / "old.txt").write_text("old")
    (prog / "version.json").write_text(json.dumps({"sha": "aaa", "date": "2026-11-01", "branch": "main"}))
    return prog, code


def fake_github(new_pyproject="v1"):
    calls = []
    blob = tarball({
        "Content_Workshop-bbb/pyproject.toml": (new_pyproject, 0o644),
        "Content_Workshop-bbb/scripts/launch.sh": ("#!/bin/bash\n", 0o755),
        "Content_Workshop-bbb/../../evil.txt": ("no", 0o644),
    })

    def fetch(url):
        calls.append(url)
        if "/compare/aaa...main" in url:
            return json.dumps({"ahead_by": 2, "commits": [
                {"sha": "m1", "commit": {"message": "Better hooks\n\nbody", "committer": {"date": "2026-11-02T08:00:00Z"}}},
                {"sha": "bbb", "commit": {"message": "Merge pull request #4", "committer": {"date": "2026-11-03T09:00:00Z"}}},
            ]}).encode()
        if url.endswith("/tar.gz/bbb"):
            return blob
        raise AssertionError(url)
    return fetch, calls


def test_dev_copy_is_not_self_updating():
    info = Updater(program_dir=None).check()
    assert info["installed"] is False and info["available"] is False


def test_check_lists_whats_new(tmp_path):
    prog, code = make_install(tmp_path)
    fetch, _ = fake_github()
    info = Updater(prog, code, fetch=fetch).check()
    assert info["available"] and info["latest_sha"] == "bbb" and info["latest_date"] == "2026-11-03"
    assert info["commits"] == ["Better hooks"]


def test_apply_swaps_code_and_keeps_deps_when_unchanged(tmp_path):
    prog, code = make_install(tmp_path)
    fetch, _ = fake_github()
    ran = []
    res = Updater(prog, code, fetch=fetch, run=lambda *a, **k: ran.append(a)).apply()
    assert res["updated"] and not ran  # pyproject unchanged: no reinstall
    assert not (code / "old.txt").exists() and (code / "scripts" / "launch.sh").stat().st_mode & 0o111
    assert not (tmp_path / "evil.txt").exists() and not list(tmp_path.rglob("evil.txt"))
    assert json.loads((prog / "version.json").read_text())["sha"] == "bbb"
    assert sorted(p.name for p in prog.iterdir()) == ["code", "version.json"]


def test_apply_reinstalls_and_rolls_back_on_failure(tmp_path):
    prog, code = make_install(tmp_path)
    fetch, _ = fake_github(new_pyproject="v2")

    class Failed:
        returncode, stderr = 1, "pip broke"
    with pytest.raises(ValueError, match="previous version"):
        Updater(prog, code, fetch=fetch, run=lambda *a, **k: Failed()).apply()
    assert (code / "old.txt").exists()  # old version back in place
    assert json.loads((prog / "version.json").read_text())["sha"] == "aaa"


# --- dashboard -------------------------------------------------------------------------------------

def test_healthz_needs_no_token(server):  # noqa: F811
    base, _ = server
    with urllib.request.urlopen(base + "/healthz") as r:
        assert json.loads(r.read()) == {"app": "content-workshop"}


def test_no_update_while_drafts_are_running(app):  # noqa: F811
    app.jobs["x"] = {"id": "x", "state": "running"}
    with pytest.raises(ValueError, match="Wait"):
        app.update_apply()
    with pytest.raises(ValueError):
        app.stop()
