"""Arabic text helpers: normalisation, word splitting, phrase search.

Kept deliberately light. The goal is matching words from the slang sheet against drafts,
not full linguistic analysis.
"""

from __future__ import annotations

import re

_DIACRITICS = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭ]")
_TATWEEL = "ـ"
_ALEF = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا"})
# Project spelling rule: ك not گ, ج not چ. Normalise the Persian letters so both spellings match.
_IRAQI_LETTERS = str.maketrans({"گ": "ك", "چ": "ج", "ڤ": "ف", "پ": "ب"})
_ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")

# Arabic letters plus Latin letters and digits; everything else separates words.
WORD_RE = re.compile(r"[ء-ي٠-٩ٱ-ۓڤگچپA-Za-z0-9%$]+")

# Single-letter prefixes that attach to a word (و ف ب ل ك). Stripped for a second match attempt.
_PREFIXES = ("و", "ف", "ب", "ل")


def normalize(text: str) -> str:
    text = _DIACRITICS.sub("", text).replace(_TATWEEL, "")
    text = text.translate(_ALEF).translate(_IRAQI_LETTERS).translate(_ARABIC_DIGITS)
    return text


def words(text: str) -> list[str]:
    return WORD_RE.findall(normalize(text))


def word_count(text: str) -> int:
    return len(WORD_RE.findall(text))


def _variants(token: str) -> set[str]:
    out = {token}
    if len(token) > 3 and token[0] in _PREFIXES:
        out.add(token[1:])
    return out


def find_phrase(text: str, phrase: str) -> bool:
    """True if `phrase` (one or more words) appears in `text` as whole words.

    Matching ignores diacritics, alef variants and a single attached prefix (و ف ب ل) on the
    first word, so "وسوف" matches "سوف" and "فماذا قال" matches "ماذا قال".
    """
    target = words(phrase)
    if not target:
        return False
    toks = words(text)
    n = len(target)
    for i in range(len(toks) - n + 1):
        if target[0] in _variants(toks[i]) and toks[i + 1 : i + n] == target[1:]:
            return True
    return False
