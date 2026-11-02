"""The Iraqi word sheet: lookups for the Dialect Guard, and the new-word review queue.

Rules (agreed with the project owner):
  * If a formal Arabic word has an entry in the sheet, use the Iraqi word instead.
  * If a word is NOT in the sheet, standard Arabic is fine.
  * Egyptian / Gulf / Levantine words are blocked (dialect/other_dialects.yaml).
  * New Iraqi words never go straight into the sheet. They wait in dialect/new_words.csv until
    the owner approves them; approved rows are appended to iraqi_words.csv and printed so they
    can be pasted into the Google Sheet.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import yaml

from .config import DIALECT_DIR, INSTALLED, WORDS_DIR
from .schemas import DialectIssue
from .text_ar import find_phrase, normalize, words

REPO_SHEET = DIALECT_DIR / "iraqi_words.csv"
REPO_PENDING = DIALECT_DIR / "new_words.csv"
SHEET = WORDS_DIR / "iraqi_words.csv"       # same as REPO_SHEET in a development checkout
PENDING = WORDS_DIR / "new_words.csv"
GOOGLE_SHEET_ID = "11l86Ku11cR8_0mTtDtbAu4aNNltf7WIeTSF_zcQQ5dM"
GOOGLE_CSV = f"https://docs.google.com/spreadsheets/d/{GOOGLE_SHEET_ID}/export?format=csv"
OTHER = DIALECT_DIR / "other_dialects.yaml"
PENDING_FIELDS = ["Iraqi", "Arabic", "source", "example", "added_at", "status"]


@dataclass(frozen=True)
class SheetEntry:
    number: str
    iraqi: str
    arabic: tuple[str, ...]  # alternatives, split on "/"

    @property
    def same_in_both(self) -> bool:
        """Rows like يظن / إنه / أداة: fine as-is, nothing to replace."""
        return normalize(self.iraqi) in {normalize(a) for a in self.arabic}


def _clean(cell: str) -> str:
    return cell.strip().strip("؟?").strip()


def load_sheet(path: Path = SHEET) -> list[SheetEntry]:
    with open(path, encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f))
    out = []
    for row in rows[1:]:
        if len(row) < 3 or not row[1].strip():
            continue
        alts = tuple(a for a in (_clean(x) for x in row[2].split("/")) if a)
        out.append(SheetEntry(row[0].strip(), row[1].strip(), alts))
    return out


def load_other_dialects(path: Path = OTHER) -> dict[str, list[dict]]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not data.pop("enabled", True):
        return {}
    return {k: v for k, v in data.items() if isinstance(v, list)}


def scan_formal(text: str, sheet: list[SheetEntry]) -> list[DialectIssue]:
    """Formal Arabic words in `text` that have an Iraqi replacement in the sheet."""
    candidates = []
    for e in sheet:
        if e.same_in_both:
            continue
        for alt in e.arabic:
            if find_phrase(text, alt):
                candidates.append((alt, e.iraqi))
    # Drop a short match that is part of a longer one (e.g. "قال" inside "ماذا قال").
    candidates.sort(key=lambda c: -len(words(c[0])))
    kept: list[tuple[str, str]] = []
    for alt, iraqi in candidates:
        w = words(alt)
        inside_longer = any(
            len(words(k)) > len(w) and _contains(words(k), w) for k, _ in kept
        )
        if not inside_longer and (alt, iraqi) not in kept:
            kept.append((alt, iraqi))
    return [DialectIssue(original=a, detected_as="msa", suggestion=i) for a, i in kept]


def _contains(big: list[str], small: list[str]) -> bool:
    n = len(small)
    return any(big[i : i + n] == small for i in range(len(big) - n + 1))


def scan_other_dialects(text: str, other: dict[str, list[dict]]) -> list[DialectIssue]:
    out = []
    for dialect, entries in other.items():
        kind = dialect if dialect in {"egyptian", "gulf", "levantine"} else "other"
        for e in entries:
            if find_phrase(text, str(e["word"])):
                out.append(DialectIssue(original=str(e["word"]), detected_as=kind, suggestion=str(e["use"])))
    return out


def scan(text: str, sheet: list[SheetEntry] | None = None, other: dict | None = None) -> list[DialectIssue]:
    sheet = load_sheet() if sheet is None else sheet
    other = load_other_dialects() if other is None else other
    return scan_formal(text, sheet) + scan_other_dialects(text, other)


def sheet_as_prompt(sheet: list[SheetEntry] | None = None) -> str:
    """The sheet as compact lines for agent prompts: 'formal -> Iraqi'."""
    sheet = load_sheet() if sheet is None else sheet
    lines = []
    for e in sheet:
        if e.same_in_both:
            lines.append(f"{e.iraqi} (same in both, fine as-is)")
        else:
            lines.append(f"{' / '.join(e.arabic)} -> {e.iraqi}")
    return "\n".join(lines)


# --- New-word review queue ----------------------------------------------------------------------

def _read_pending(path: Path = PENDING) -> list[dict]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _write_pending(rows: list[dict], path: Path = PENDING) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=PENDING_FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def known_iraqi(sheet: list[SheetEntry] | None = None) -> set[str]:
    sheet = load_sheet() if sheet is None else sheet
    return {normalize(e.iraqi) for e in sheet}


def propose(iraqi: str, arabic: str, source: str, example: str = "",
            sheet_path: Path = SHEET, pending_path: Path = PENDING) -> bool:
    """Queue a new Iraqi word for review. Returns False if it is already in the sheet or queue."""
    key = normalize(iraqi.strip())
    if not key or key in known_iraqi(load_sheet(sheet_path)):
        return False
    rows = _read_pending(pending_path)
    if any(normalize(r["Iraqi"]) == key and r["status"] == "pending" for r in rows):
        return False
    rows.append({
        "Iraqi": iraqi.strip(), "Arabic": arabic.strip(), "source": source, "example": example.strip(),
        "added_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"), "status": "pending",
    })
    _write_pending(rows, pending_path)
    return True


def pending(pending_path: Path = PENDING) -> list[dict]:
    return [r for r in _read_pending(pending_path) if r["status"] == "pending"]


def decide(iraqi_words: list[str], approve: bool,
           sheet_path: Path = SHEET, pending_path: Path = PENDING) -> list[list[str]]:
    """Approve or reject queued words. Approved words are appended to the sheet copy.

    Returns the new sheet rows (#, Iraqi, Arabic) so they can be pasted into the Google Sheet.
    """
    wanted = {normalize(w) for w in iraqi_words}
    rows = _read_pending(pending_path)
    new_rows: list[list[str]] = []
    if approve:
        with open(sheet_path, encoding="utf-8", newline="") as f:
            existing = list(csv.reader(f))
        nums = [int(r[0]) for r in existing[1:] if r and r[0].strip().isdigit()]
        next_num = max(nums, default=0) + 1
    for r in rows:
        if r["status"] != "pending" or normalize(r["Iraqi"]) not in wanted:
            continue
        r["status"] = "approved" if approve else "rejected"
        if approve:
            new_rows.append([str(next_num), r["Iraqi"], r["Arabic"]])
            next_num += 1
    if new_rows:
        raw = sheet_path.read_bytes()
        with open(sheet_path, "a", encoding="utf-8", newline="") as f:
            if raw and not raw.endswith(b"\n"):
                f.write("\n")
            csv.writer(f, lineterminator="\n").writerows(new_rows)
    _write_pending(rows, pending_path)
    return new_rows


# --- Keeping the owner's copy in step (Mac install) and pulling new rows from the Google Sheet ----

def _read_rows(path: Path) -> list[list[str]]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8", newline="") as f:
        return [r for r in csv.reader(f)][1:]


def _write_rows(path: Path, rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["#", "Iraqi", "Arabic"])
        w.writerows(rows)


def merge_sheets(base: list[list[str]], local: list[list[str]]) -> list[list[str]]:
    """The repo copy wins for every word it has; words only the owner has are kept and numbered after it."""
    out = [r[:3] for r in base if len(r) >= 3 and r[1].strip()]
    seen = {normalize(r[1]) for r in out}
    nums = [int(r[0]) for r in out if r[0].strip().isdigit()]
    n = max(nums, default=0)
    for r in local:
        if len(r) < 3 or not r[1].strip() or normalize(r[1]) in seen:
            continue
        n += 1
        out.append([str(n), r[1].strip(), r[2].strip()])
        seen.add(normalize(r[1]))
    return out


def prepare_local_words(sheet_path: Path = SHEET, pending_path: Path = PENDING,
                        repo_sheet: Path = REPO_SHEET, repo_pending: Path = REPO_PENDING) -> None:
    """Mac install only: refresh the owner's word sheet from the copy that came with the latest update.

    Corrections in the repo copy reach the owner, and words they approved that aren't in the repo yet stay.
    Words queued in the repo (e.g. by a Claude session) are added to the owner's review list.
    """
    if sheet_path == repo_sheet:
        return
    _write_rows(sheet_path, merge_sheets(_read_rows(repo_sheet), _read_rows(sheet_path)))
    local = _read_pending(pending_path)
    have = {normalize(r["Iraqi"]) for r in local} | known_iraqi(load_sheet(sheet_path))
    extra = [r for r in _read_pending(repo_pending)
             if r.get("status") == "pending" and normalize(r["Iraqi"]) not in have]
    if extra or not pending_path.exists():
        pending_path.parent.mkdir(parents=True, exist_ok=True)
        _write_pending(local + extra, pending_path)


def sync_from_google(sheet_path: Path = SHEET, fetch=None) -> dict:
    """Add words that are in the Google Sheet but missing here. Existing rows are never overwritten.

    Rows whose meaning differs are only reported, because the repo copy carries spelling fixes
    (e.g. ذهبوا, تبدأ) that the Google Sheet may not have yet.
    """
    if fetch is None:
        import urllib.request

        def fetch(url: str) -> str:
            with urllib.request.urlopen(url, timeout=20) as r:
                return r.read().decode("utf-8-sig")
    try:
        text = fetch(GOOGLE_CSV)
    except Exception as e:  # shown in the dashboard
        raise ValueError(f"Couldn't read the Google Sheet ({e}). Check the internet connection.") from e
    google = [r for r in list(csv.reader(text.splitlines()))[1:] if len(r) >= 3 and r[1].strip()]
    if not google:
        raise ValueError("The Google Sheet came back empty. Is it still shared as 'anyone with the link'?")
    mine = _read_rows(sheet_path)
    by_word = {normalize(r[1]): r for r in mine if len(r) >= 3}
    nums = [int(r[0]) for r in mine if r and r[0].strip().isdigit()]
    n = max(nums, default=0)
    added, different = [], []
    for g in google:
        key = normalize(g[1])
        if key in by_word:
            if normalize(by_word[key][2]) != normalize(g[2]):
                different.append({"iraqi": g[1].strip(), "here": by_word[key][2], "google": g[2].strip()})
            continue
        n += 1
        row = [str(n), g[1].strip(), g[2].strip()]
        added.append(row)
        by_word[key] = row
    if added:
        _write_rows(sheet_path, mine + added)
    return {"added": added, "different": different}
