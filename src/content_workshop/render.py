"""Turn committee results into readable Markdown files the creator can record from."""

from __future__ import annotations

from pathlib import Path

from .schemas import CommitteeResult, Draft

FORMAT_NAMES = {
    "short_video": "Short video (Reels / TikTok)",
    "long_video_story": "Long video story",
    "story_questions": "Story with question stickers",
    "post": "Post",
}


def draft_md(d: Draft) -> str:
    s = d.script
    status = "PASSED" if d.passed else "NEEDS YOUR REVIEW"
    out = [
        f"# {s.title}",
        f"**{FORMAT_NAMES.get(s.format, s.format)} · {s.level}** · id `{d.id}` · {status}",
        f"Critic {d.review.total if d.review else '-'}/100 · Dialect {d.dialect.score if d.dialect else '-'}/10 · "
        f"revisions {d.revisions}",
        "",
        "## Hook",
        f"> {s.hook}",
        "",
        "## Script",
    ]
    for i, b in enumerate(s.beats, 1):
        t = f" ({b.seconds:.0f}s)" if b.seconds else ""
        out.append(f"{i}. **{b.label}**{t}: {b.spoken}")
        if b.on_screen_text:
            out.append(f"   - on screen: {b.on_screen_text}")
        if b.visual_note:
            out.append(f"   - visual: {b.visual_note}")
    out += ["", f"**CTA:** {s.cta}"]
    if s.sticker_questions:
        out += ["", "## Sticker questions", *[f"- {q}" for q in s.sticker_questions]]
    if s.caption:
        out += ["", "## Caption", s.caption]
    if s.hashtags:
        out += ["", " ".join(h if h.startswith("#") else f"#{h}" for h in s.hashtags)]
    if d.checks:
        out += ["", "## Checks", *[f"- **{c.severity}** {c.check}: {c.detail}" for c in d.checks]]
    if d.review and d.review.must_fix:
        out += ["", "## Critic: still to fix", *[f"- {m}" for m in d.review.must_fix]]
    return "\n".join(out) + "\n"


def result_md(r: CommitteeResult) -> str:
    head = [f"# {r.topic}", "", f"**Core idea:** {r.analysis.core_idea}", "",
            "**Claims to verify before posting:**", *([f"- {c}" for c in r.analysis.claims_to_verify] or ["- none"]), ""]
    return "\n".join(head) + "\n---\n\n" + "\n---\n\n".join(draft_md(d) for d in r.drafts)


def save(r: CommitteeResult, output_dir: Path) -> Path:
    """Write <run>.json (full detail) and <run>.md (readable). Returns the .md path."""
    output_dir.mkdir(parents=True, exist_ok=True)
    base = r.drafts[0].id.rsplit("-", 2)[0] if r.drafts else "run"
    (output_dir / f"{base}.json").write_text(r.model_dump_json(indent=1), encoding="utf-8")
    md = output_dir / f"{base}.md"
    md.write_text(result_md(r), encoding="utf-8")
    return md
