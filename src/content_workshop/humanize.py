"""Clean machine artefacts out of a draft and flag AI-sounding Arabic phrases.

The invisible-character and typography passes are adapted from skills/ig-human/humanize.py in
Jakeschincariol/instagram-agent-skill (MIT). The phrase list is Arabic and lives in
humanizer/ai_phrases_ar.yaml. Phrases are flagged, not auto-replaced: fixing them needs judgement.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from .config import REPO_ROOT
from .text_ar import find_phrase

PHRASES = REPO_ROOT / "humanizer" / "ai_phrases_ar.yaml"

# Characters a keyboard does not type. Removed.
# Deliberately NOT removed: ZWNJ/ZWJ (U+200C/D) and the bidi marks (U+200E/F, U+061C), which can
# be legitimate in mixed Arabic/English text.
_REMOVE = {
    "​",  # zero-width space
    "⁠",  # word joiner
    "﻿",  # byte-order mark
    "­",  # soft hyphen
    "⁡", "⁢", "⁣", "⁤",  # invisible operators
}
_TAGS = range(0xE0000, 0xE0080)  # Unicode tag characters
_SPACES = {" ": " ", " ": " ", " ": " ", " ": " "}
_TYPO = {
    " — ": "، ", "—": "، ",  # em dash: the clearest AI tell; Arabic comma instead
    "–": "-",                 # en dash
    "“": '"', "”": '"', "‘": "'", "’": "'",
    "…": "...",
}


def clean(text: str) -> tuple[str, dict[str, int]]:
    """Remove invisible characters and fix typography. Returns (text, counts of changes)."""
    counts = {"invisible": 0, "spaces": 0, "typography": 0}
    out = []
    for ch in text:
        if ch in _REMOVE or ord(ch) in _TAGS:
            counts["invisible"] += 1
            continue
        if ch in _SPACES:
            counts["spaces"] += 1
            ch = _SPACES[ch]
        out.append(ch)
    text = "".join(out)
    for src, dst in _TYPO.items():
        n = text.count(src)
        if n:
            counts["typography"] += n
            text = text.replace(src, dst)
    return text, counts


def load_phrases(path: Path = PHRASES) -> list[dict]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return [dict(item, group=group) for group, items in data.items() for item in (items or [])]


def scan_phrases(text: str, phrases: list[dict] | None = None) -> list[dict]:
    phrases = load_phrases() if phrases is None else phrases
    return [p for p in phrases if find_phrase(text, str(p["phrase"]))]
