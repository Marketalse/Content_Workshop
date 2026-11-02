"""Command line entry point: `content-workshop <command>` (or `python -m content_workshop`)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import checks, dialect, logbook
from .config import FORMATS, LEVELS, OUTPUT_DIR, Settings
from .schemas import Script


def _list(value: str, allowed: tuple[str, ...]) -> list[str]:
    items = [v.strip() for v in value.split(",") if v.strip()]
    bad = [v for v in items if v not in allowed]
    if bad:
        raise argparse.ArgumentTypeError(f"unknown: {', '.join(bad)} (choose from {', '.join(allowed)})")
    return items


def cmd_generate(a) -> int:
    from .committee import Committee
    from .llm import LLM
    from .render import draft_md, result_md

    settings = Settings()
    committee = Committee(LLM(settings), settings, wpm=a.wpm, progress=lambda m: print(f"  · {m}", file=sys.stderr))
    result = committee.run(a.topic, a.formats, a.levels)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    base = result.drafts[0].id.rsplit("-", 2)[0] if result.drafts else "run"
    (OUTPUT_DIR / f"{base}.json").write_text(result.model_dump_json(indent=1), encoding="utf-8")
    (OUTPUT_DIR / f"{base}.md").write_text(result_md(result), encoding="utf-8")
    for d in result.drafts:
        logbook.log_draft(a.topic, d)
        print(f"{'PASS ' if d.passed else 'CHECK'}  {d.id}  critic {d.review.total if d.review else '-'}  "
              f"dialect {d.dialect.score if d.dialect else '-'}")
    print(f"\nSaved: {OUTPUT_DIR / (base + '.md')}")
    n = len(dialect.pending())
    if n:
        print(f"{n} new Iraqi word(s) waiting for your approval: content-workshop words pending")
    return 0


def cmd_check(a) -> int:
    raw = Path(a.file).read_text(encoding="utf-8")
    if a.file.endswith(".json"):
        script = Script.model_validate_json(raw)
        issues = checks.run_all(script, a.wpm)
    else:
        # Plain text: only the language checks apply (no structure to time beat by beat).
        issues = checks.language(Script(format=a.format, level="medium", title="", hook=raw, beats=[], cta=""))
        print(f"~{checks.seconds(raw, a.wpm):.1f}s to say at {a.wpm:.0f} wpm")
    for i in issues:
        print(f"{i.severity.upper():5} {i.check}: {i.detail}")
    if not issues:
        print("No issues found.")
    return 1 if checks.failures(issues) else 0


def cmd_words(a) -> int:
    if a.action == "pending":
        rows = dialect.pending()
        if not rows:
            print("No words waiting.")
        for r in rows:
            print(f"{r['Iraqi']}  =  {r['Arabic']}   ({r['source']}; e.g. {r['example']})")
    elif a.action == "add":
        if len(a.words) != 2:
            print("usage: words add <Iraqi> <Arabic>", file=sys.stderr)
            return 2
        ok = dialect.propose(a.words[0], a.words[1], source="manual", example=a.example or "")
        print("Queued for approval." if ok else "Already in the sheet or the queue.")
    else:
        rows = dialect.decide(a.words, approve=(a.action == "approve"))
        if a.action == "approve":
            print("Added to dialect/iraqi_words.csv. Paste these rows into the Google Sheet:\n")
            print("#\tIraqi\tArabic")
            for r in rows:
                print("\t".join(r))
        else:
            print("Rejected.")
    return 0


def cmd_log(a) -> int:
    if a.action == "edited":
        final = Path(a.final).read_text(encoding="utf-8")
        ratio = logbook.log_edit(a.id, final, a.dialect_fixes)
        print(f"Logged. You changed {ratio:.0%} of the words"
              f" ({'light edit' if ratio <= logbook.LIGHT_EDIT else 'heavy edit'}).")
    elif a.action == "metrics":
        logbook.log_metrics(a.id, views=a.views, retention=a.retention, replies=a.replies,
                            saves=a.saves, shares=a.shares)
        print("Logged.")
    else:
        print(json.dumps(logbook.report(), indent=1))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="content-workshop", description="Baghdadi copywriting committee.")
    sub = p.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate", help="Write content for a topic.")
    g.add_argument("topic")
    g.add_argument("--formats", type=lambda v: _list(v, FORMATS), default=["short_video"],
                   help=f"comma list: {','.join(FORMATS)} (default short_video)")
    g.add_argument("--levels", type=lambda v: _list(v, LEVELS), default=list(LEVELS),
                   help="comma list: simple,medium,complex (default all)")
    g.add_argument("--wpm", type=float, default=checks.DEFAULT_WPM, help="your speaking speed")
    g.set_defaults(fn=cmd_generate)

    c = sub.add_parser("check", help="Run the automatic checks on a script (.json) or plain text (.txt).")
    c.add_argument("file")
    c.add_argument("--format", choices=FORMATS, default="short_video")
    c.add_argument("--wpm", type=float, default=checks.DEFAULT_WPM)
    c.set_defaults(fn=cmd_check)

    w = sub.add_parser("words", help="Review new Iraqi words before they go into the sheet.")
    w.add_argument("action", choices=["pending", "approve", "reject", "add"])
    w.add_argument("words", nargs="*")
    w.add_argument("--example")
    w.set_defaults(fn=cmd_words)

    lg = sub.add_parser("log", help="Record edits and results; see the reliability report.")
    lg.add_argument("action", choices=["edited", "metrics", "report"])
    lg.add_argument("id", nargs="?")
    lg.add_argument("--final", help="file with the text you actually posted")
    lg.add_argument("--dialect-fixes", type=int, default=0, help="how many words you fixed for dialect")
    for m in ("views", "retention", "replies", "saves", "shares"):
        lg.add_argument(f"--{m}", type=float)
    lg.set_defaults(fn=cmd_log)
    return p


def load_dotenv(path: Path | None = None) -> None:
    """Read KEY=value lines from the repo's .env. Variables already set in the environment win."""
    import os

    from .config import REPO_ROOT

    path = path or REPO_ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip("'\"")
        if key and value and key not in os.environ:
            os.environ[key] = value


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    a = build_parser().parse_args(argv)
    if a.cmd == "log" and a.action in ("edited", "metrics") and not a.id:
        print("log edited/metrics needs a draft id", file=sys.stderr)
        return 2
    if a.cmd == "log" and a.action == "edited" and not a.final:
        print("log edited needs --final <file>", file=sys.stderr)
        return 2
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
