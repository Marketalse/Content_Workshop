"""Deterministic checks run on every draft before the Critic sees it.

Timing logic adapted from skills/ig-reel/beats.py and caption logic from skills/ig-caption/caption.py
in Jakeschincariol/instagram-agent-skill (MIT), rewritten to count Arabic words and to read limits
from the format specs in formats/*.yaml.
"""

from __future__ import annotations

import re
from functools import lru_cache

import yaml

from . import dialect, humanize
from .config import FORMATS_DIR
from .schemas import CheckIssue, Script
from .text_ar import normalize, word_count, words

DEFAULT_WPM = 140  # Arabic speech; calibrate per creator with --wpm from timed recordings.
HASHTAG_RE = re.compile(r"#[\w؀-ۿ]+")
PLACEHOLDER_RE = re.compile(r"\{\{[^}]+\}\}")
# Very common words that don't count as a "loop" echo between first and last line.
_STOP = {normalize(w) for w in "من الى على عن في هذا هاي هذي اللي بس و يا ما مو شنو كل هم انت انتو".split()}


@lru_cache(maxsize=None)
def load_format(name: str) -> dict:
    return yaml.safe_load((FORMATS_DIR / f"{name}.yaml").read_text(encoding="utf-8"))


def seconds(text: str, wpm: float = DEFAULT_WPM) -> float:
    return word_count(text) / (wpm / 60.0)


def timing(script: Script, wpm: float = DEFAULT_WPM) -> list[CheckIssue]:
    spec = load_format(script.format)
    c = spec.get("checks", {})
    out: list[CheckIssue] = []
    if script.format in ("story_questions", "post"):
        return out

    hook_s = seconds(script.hook, wpm)
    if hook_s > c.get("hook_max_seconds", 3):
        out.append(CheckIssue(severity="fail", check="hook length",
                              detail=f"Hook takes ~{hook_s:.1f}s to say; max {c['hook_max_seconds']}s."))
    max_beat = c.get("beat_max_seconds")
    for b in script.beats:
        s = seconds(b.spoken, wpm)
        if max_beat and s > max_beat:
            out.append(CheckIssue(severity="warn", check="long beat",
                                  detail=f"'{b.label}' runs ~{s:.1f}s; split it or change the shot (max {max_beat}s)."))
    total = seconds(" ".join([script.hook, *[b.spoken for b in script.beats], script.cta]), wpm)
    rng = spec.get("length_seconds", {})
    if rng and not (rng["min"] <= total <= rng["max"]):
        out.append(CheckIssue(severity="warn", check="total length",
                              detail=f"~{total:.0f}s at {wpm:.0f} wpm; target range {rng['min']}-{rng['max']}s."))
    if c.get("require_loop"):
        last = script.beats[-1].spoken if script.beats else script.cta
        first_words = {w for w in words(script.hook) if len(w) > 2 and w not in _STOP}
        last_words = {w for w in words(last + " " + script.cta) if len(w) > 2 and w not in _STOP}
        if not first_words & last_words:
            out.append(CheckIssue(severity="warn", check="loop",
                                  detail="The ending doesn't echo a word from the hook; a loop makes replays land."))
    return out


def on_screen(script: Script) -> list[CheckIssue]:
    limit = load_format(script.format).get("on_screen_text", {}).get("max_words_per_card")
    if not limit:
        return []
    return [
        CheckIssue(severity="warn", check="on-screen text",
                   detail=f"'{b.on_screen_text}' has {word_count(b.on_screen_text)} words; max {limit}.")
        for b in script.beats if b.on_screen_text and word_count(b.on_screen_text) > limit
    ]


def caption(script: Script) -> list[CheckIssue]:
    c = load_format(script.format).get("checks", {})
    out: list[CheckIssue] = []
    text = script.caption
    tags = set(HASHTAG_RE.findall(text)) | {t if t.startswith("#") else f"#{t}" for t in script.hashtags}
    if "max_hashtags" in c and len(tags) > c["max_hashtags"]:
        out.append(CheckIssue(severity="fail", check="hashtags",
                              detail=f"{len(tags)} hashtags; the limit is {c['max_hashtags']}."))
    if text and "caption_max_chars" in c and len(text) > c["caption_max_chars"]:
        out.append(CheckIssue(severity="fail", check="caption length",
                              detail=f"{len(text)} characters; max {c['caption_max_chars']}."))
    if text and "feed_visible_chars" in c:
        first = text.strip().splitlines()[0] if text.strip() else ""
        if len(first) > c["feed_visible_chars"]:
            out.append(CheckIssue(severity="warn", check="visible window",
                                  detail=f"First line is {len(first)} characters; the feed cuts at ~{c['feed_visible_chars']}, "
                                         "so the hook gets cut mid-thought."))
    return out


def stickers(script: Script) -> list[CheckIssue]:
    if script.format != "story_questions":
        return []
    c = load_format("story_questions").get("checks", {})
    out: list[CheckIssue] = []
    if not script.sticker_questions:
        out.append(CheckIssue(severity="fail", check="stickers", detail="No sticker question written."))
    for q in script.sticker_questions:
        if len(q) > c.get("sticker_question_max_chars", 60):
            out.append(CheckIssue(severity="warn", check="sticker length",
                                  detail=f"'{q}' is {len(q)} characters; keep it under {c['sticker_question_max_chars']}."))
    if len(script.beats) > c.get("max_frames", 7):
        out.append(CheckIssue(severity="warn", check="frames",
                              detail=f"{len(script.beats)} frames; keep it to {c['max_frames']} or fewer."))
    return out


def language(script: Script, sheet=None, other=None, phrases=None) -> list[CheckIssue]:
    text = script.plain_text()
    out = [
        CheckIssue(severity="fail", check=f"dialect: {i.detected_as}",
                   detail=f"'{i.original}' -> use '{i.suggestion}'.")
        for i in dialect.scan(text, sheet, other)
    ]
    out += [
        CheckIssue(severity="warn", check="AI-sounding phrase", detail=f"'{p['phrase']}': {p['fix']}")
        for p in humanize.scan_phrases(text, phrases)
    ]
    _, counts = humanize.clean(text)
    if counts["invisible"] or counts["typography"]:
        out.append(CheckIssue(severity="info", check="cleanup",
                              detail=f"{counts['invisible']} invisible characters and {counts['typography']} "
                                     "typography marks will be cleaned automatically."))
    holes = PLACEHOLDER_RE.findall(text)
    if holes:
        out.append(CheckIssue(severity="info", check="needs your input",
                              detail="Fill in before recording: " + ", ".join(sorted(set(holes)))))
    return out


def run_all(script: Script, wpm: float = DEFAULT_WPM, sheet=None, other=None, phrases=None) -> list[CheckIssue]:
    return (timing(script, wpm) + on_screen(script) + caption(script) + stickers(script)
            + language(script, sheet, other, phrases))


def failures(issues: list[CheckIssue]) -> list[CheckIssue]:
    return [i for i in issues if i.severity == "fail"]
