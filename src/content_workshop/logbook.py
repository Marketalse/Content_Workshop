"""The editing log: the evidence for "is this reliable enough to become a product?".

Every generated draft is logged. When you record what you actually posted, the log measures how
much you had to change. The product gate (agreed): 80% of drafts need only light edits
(<= 20% of words changed) across the last 50 reviewed drafts, and fewer than 1 dialect fix per 10 lines.
"""

from __future__ import annotations

import difflib
import json
from datetime import datetime, timezone
from pathlib import Path

from .config import LOGS_DIR
from .schemas import Draft
from .text_ar import words

LOG = LOGS_DIR / "drafts.jsonl"
LIGHT_EDIT = 0.20
TARGET_LIGHT_SHARE = 0.80
TARGET_DIALECT_FIXES_PER_10 = 1.0
WINDOW = 50


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _append(record: dict, path: Path = LOG) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def read(path: Path = LOG) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def log_draft(topic: str, draft: Draft, path: Path = LOG) -> None:
    _append({
        "event": "generated", "id": draft.id, "at": _now(), "topic": topic,
        "format": draft.script.format, "level": draft.script.level,
        "critic_total": draft.review.total if draft.review else None,
        "dialect_score": draft.dialect.score if draft.dialect else None,
        "passed": draft.passed, "revisions": draft.revisions,
        "lines": len(draft.script.lines()), "text": draft.script.plain_text(),
    }, path)


def edit_ratio(original: str, final: str) -> float:
    """Share of words changed between the draft and what was actually posted (0 = untouched)."""
    a, b = words(original), words(final)
    if not a and not b:
        return 0.0
    return round(1 - difflib.SequenceMatcher(None, a, b, autojunk=False).ratio(), 3)


def log_edit(draft_id: str, final_text: str, dialect_fixes: int, path: Path = LOG) -> float:
    gen = next((r for r in read(path) if r["event"] == "generated" and r["id"] == draft_id), None)
    if gen is None:
        raise KeyError(f"No generated draft with id {draft_id}")
    ratio = edit_ratio(gen["text"], final_text)
    _append({"event": "edited", "id": draft_id, "at": _now(), "edit_ratio": ratio,
             "dialect_fixes": dialect_fixes, "final_text": final_text}, path)
    return ratio


def log_metrics(draft_id: str, path: Path = LOG, **metrics: float) -> None:
    _append({"event": "metrics", "id": draft_id, "at": _now(),
             **{k: v for k, v in metrics.items() if v is not None}}, path)


def report(path: Path = LOG) -> dict:
    records = read(path)
    gens = {r["id"]: r for r in records if r["event"] == "generated"}
    edits = {r["id"]: r for r in records if r["event"] == "edited"}  # latest edit wins
    reviewed = [i for i in gens if i in edits][-WINDOW:]
    light = [i for i in reviewed if edits[i]["edit_ratio"] <= LIGHT_EDIT]
    lines = sum(gens[i]["lines"] for i in reviewed) or 0
    fixes = sum(edits[i]["dialect_fixes"] for i in reviewed)
    share = len(light) / len(reviewed) if reviewed else 0.0
    per10 = (fixes / lines * 10) if lines else 0.0
    return {
        "generated": len(gens),
        "reviewed": len(reviewed),
        "light_edit_share": round(share, 3),
        "dialect_fixes_per_10_lines": round(per10, 2),
        "gate_light_edits": share >= TARGET_LIGHT_SHARE,
        "gate_dialect": per10 < TARGET_DIALECT_FIXES_PER_10,
        "gate_sample_size": len(reviewed) >= WINDOW,
        "product_ready": len(reviewed) >= WINDOW and share >= TARGET_LIGHT_SHARE
                         and per10 < TARGET_DIALECT_FIXES_PER_10,
    }
