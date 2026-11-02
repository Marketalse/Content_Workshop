"""One-click updates for the Mac install: compare with GitHub, download the new version, swap it in.

Only the program folder (~/Content Workshop/.program/code) is replaced. Drafts, the log, the key and
the word sheet live outside it (see config.py), so an update can never touch them.
A development checkout (a git clone) is updated with git instead; the dashboard says so.
"""

from __future__ import annotations

import io
import json
import shutil
import subprocess
import sys
import tarfile
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .config import PROGRAM_DIR, REPO_ROOT

REPO = "Marketalse/Content_Workshop"
BRANCH = "main"
API = f"https://api.github.com/repos/{REPO}"
TARBALL = f"https://codeload.github.com/{REPO}/tar.gz/{{sha}}"

Fetch = Callable[[str], bytes]


def _fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "content-workshop",
                                               "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


class Updater:
    def __init__(self, program_dir: Path | None = PROGRAM_DIR, code_dir: Path = REPO_ROOT,
                 fetch: Fetch = _fetch, run: Callable = subprocess.run, python: str = sys.executable):
        self.program_dir = program_dir
        self.code_dir = code_dir
        self.fetch = fetch
        self.run = run
        self.python = python

    @property
    def installed(self) -> bool:
        return self.program_dir is not None

    @property
    def version_file(self) -> Path:
        return self.program_dir / "version.json"

    def current(self) -> dict:
        if not self.installed:
            return {"installed": False, "sha": "", "date": ""}
        try:
            v = json.loads(self.version_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            v = {}
        return {"installed": True, "sha": v.get("sha", ""), "date": v.get("date", ""),
                "branch": v.get("branch") or BRANCH}

    def check(self) -> dict:
        cur = self.current()
        if not cur["installed"]:
            return {**cur, "branch": "", "available": False, "commits": [],
                    "note": "This is a development copy. Update it with git."}
        try:
            if cur["sha"]:
                data = json.loads(self.fetch(f"{API}/compare/{cur['sha']}...{cur['branch']}"))
                commits = data.get("commits", [])
                latest = commits[-1] if commits else None
                ahead = int(data.get("ahead_by", len(commits)))
            else:  # version unknown: offer the latest
                latest = json.loads(self.fetch(f"{API}/commits/{cur['branch']}"))
                commits, ahead = [latest], 1
        except Exception as e:
            raise ValueError(f"Couldn't reach GitHub to check for updates ({e}).") from e
        notes = [c["commit"]["message"].split("\n", 1)[0] for c in commits
                 if not c["commit"]["message"].startswith("Merge ")]
        return {**cur, "available": ahead > 0 and latest is not None,
                "latest_sha": latest["sha"] if latest else cur["sha"],
                "latest_date": latest["commit"]["committer"]["date"][:10] if latest else cur["date"],
                "commits": notes[-15:][::-1]}

    def apply(self) -> dict:
        info = self.check()
        if not info.get("available"):
            return {**info, "updated": False}
        sha = info["latest_sha"]
        try:
            blob = self.fetch(TARBALL.format(sha=sha))
        except Exception as e:
            raise ValueError(f"Couldn't download the update ({e}).") from e
        new = self.code_dir.with_name(self.code_dir.name + ".new")
        old = self.code_dir.with_name(self.code_dir.name + ".old")
        for d in (new, old):
            shutil.rmtree(d, ignore_errors=True)
        _extract(blob, new)
        if not (new / "pyproject.toml").exists():
            shutil.rmtree(new, ignore_errors=True)
            raise ValueError("The download looks incomplete; nothing was changed.")
        deps_changed = _read(new / "pyproject.toml") != _read(self.code_dir / "pyproject.toml")
        self.code_dir.rename(old)
        new.rename(self.code_dir)
        if deps_changed:
            r = self.run([self.python, "-m", "pip", "install", "--quiet", "-e", str(self.code_dir)],
                         capture_output=True, text=True)
            if r.returncode != 0:  # put the working version back
                shutil.rmtree(self.code_dir, ignore_errors=True)
                old.rename(self.code_dir)
                raise ValueError("Installing the update failed; you're still on the previous version.\n"
                                 + (r.stderr or "")[-600:])
        shutil.rmtree(old, ignore_errors=True)
        self.version_file.write_text(json.dumps({
            "sha": sha, "date": info["latest_date"], "branch": info["branch"],
            "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}), encoding="utf-8")
        return {**info, "updated": True, "sha": sha, "date": info["latest_date"], "available": False}


def _read(p: Path) -> bytes:
    try:
        return p.read_bytes()
    except OSError:
        return b""


def _extract(blob: bytes, dest: Path) -> None:
    """Unpack a GitHub tarball into dest, dropping its top folder and refusing anything odd."""
    dest.mkdir(parents=True)
    root = dest.resolve()
    with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as tar:
        for m in tar.getmembers():
            parts = Path(m.name).parts[1:]
            if not parts or not (m.isfile() or m.isdir()):
                continue
            target = (dest.joinpath(*parts)).resolve()
            if root not in target.parents:
                continue
            if m.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with tar.extractfile(m) as src, open(target, "wb") as out:
                shutil.copyfileobj(src, out)
            target.chmod(0o755 if m.mode & 0o111 else 0o644)
