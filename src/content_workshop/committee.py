"""The Copywriter Committee: Analyst -> Strategist -> Writer -> checks + Dialect Guard -> Critic.

Each draft loops back to the Writer with concrete feedback until it passes or runs out of
revisions. Every Iraqi word the committee uses that is not in the sheet is queued for review.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Callable



from . import checks, dialect, humanize
from .config import EXAMPLES_DIR, FORMATS_DIR, PROMPTS_DIR, REPO_ROOT, Settings
from .llm import SupportsAsk
from .schemas import (
    CommitteeResult, DialectReport, Draft, Guidelines, LevelBrief, Review, Script, TopicAnalysis,
)

Progress = Callable[[str], None]


def render(name: str, **values: str) -> str:
    """Load a prompt and fill {placeholders}. Plain replace, so {{رقمك}} survives untouched."""
    text = (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")
    for key, val in values.items():
        text = text.replace("{" + key + "}", val)
    return text


def _read(path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _examples(limit_chars: int = 12000) -> str:
    """Corrected transcripts of the creator's own videos, used as voice examples."""
    folder = EXAMPLES_DIR / "transcripts"
    parts, used = [], 0
    for f in sorted(folder.glob("*.md")) + sorted(folder.glob("*.txt")):
        if f.name.lower() == "readme.md":
            continue
        t = f.read_text(encoding="utf-8").strip()
        if not t or used + len(t) > limit_chars:
            continue
        parts.append(f"--- {f.stem} ---\n{t}")
        used += len(t)
    return "\n\n".join(parts)


def _clean_strings(obj):
    if isinstance(obj, str):
        return humanize.clean(obj)[0]
    if isinstance(obj, list):
        return [_clean_strings(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _clean_strings(v) for k, v in obj.items()}
    return obj


def draft_id(topic: str, fmt: str, level: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    h = hashlib.sha1(topic.encode("utf-8")).hexdigest()[:6]
    return f"{stamp}-{h}-{fmt}-{level}"


class Committee:
    def __init__(self, llm: SupportsAsk, settings: Settings | None = None, wpm: float = checks.DEFAULT_WPM,
                 progress: Progress | None = None, queue_words: bool = True):
        self.llm = llm
        self.s = settings or Settings()
        self.wpm = wpm
        self.progress = progress or (lambda msg: None)
        self.queue_words = queue_words
        self.sheet = dialect.load_sheet()
        self.other = dialect.load_other_dialects()
        self.phrases = humanize.load_phrases()
        voice = _read(REPO_ROOT / "voice" / "voice.md")
        examples = _examples()
        if examples:
            voice += "\n\nExamples of how the creator actually talks (corrected transcripts):\n" + examples
        self.house = render("house_rules", sheet=dialect.sheet_as_prompt(self.sheet), voice=voice)
        self.levels_yaml = _read(FORMATS_DIR / "levels.yaml")
        self.hooks_yaml = _read(REPO_ROOT / "hooks" / "hooks_ar.yaml")

    def _system(self, role: str, **values: str) -> str:
        return self.house + "\n\n---\n\n" + render(role, **values)

    # -- stages ------------------------------------------------------------------------------

    def analyse(self, topic: str) -> TopicAnalysis:
        self.progress("Analyst: breaking down the topic")
        return self.llm.ask(self._system("analyst"), f"Topic: {topic}", TopicAnalysis)

    def strategise(self, topic: str, analysis: TopicAnalysis, levels: list[str]) -> Guidelines:
        self.progress("Strategist: writing guidelines for " + ", ".join(levels))
        user = (f"Topic: {topic}\n\nAnalysis:\n{analysis.model_dump_json(indent=1)}\n\n"
                f"Write a level brief for each of these levels only: {', '.join(levels)}.")
        return self.llm.ask(self._system("strategist", levels=self.levels_yaml), user, Guidelines)

    def write(self, topic: str, fmt: str, level: str, analysis: TopicAnalysis, guidelines: Guidelines) -> Draft:
        did = draft_id(topic, fmt, level)
        brief = next((b for b in guidelines.levels if b.level == level), None) or LevelBrief(
            level=level, audience="", assumed_knowledge="", angle="", key_message=analysis.core_idea)
        spec = _read(FORMATS_DIR / f"{fmt}.yaml")
        system = self._system("writer", format=fmt, level=level, format_spec=spec, hooks=self.hooks_yaml)
        base = (f"Topic: {topic}\n\nAnalysis:\n{analysis.model_dump_json(indent=1)}\n\n"
                f"Guidelines: tone={guidelines.tone}\nDo: {guidelines.do}\nDon't: {guidelines.dont}\n\n"
                f"Level brief:\n{brief.model_dump_json(indent=1)}")

        script: Script | None = None
        feedback = ""
        draft = None
        for attempt in range(self.s.max_revisions + 1):
            self.progress(f"Writer: {fmt} / {level}" + (f" (revision {attempt})" if attempt else ""))
            user = base
            if script is not None:
                user += (f"\n\nYour previous draft:\n{script.model_dump_json(indent=1)}\n\n"
                         f"Revise it. Fix every point below and keep what already works:\n{feedback}")
            script = self.llm.ask(system, user, Script)
            script = Script.model_validate(_clean_strings(script.model_dump()) | {"format": fmt, "level": level})

            issues = checks.run_all(script, self.wpm, self.sheet, self.other, self.phrases)
            self.progress(f"Dialect Guard: {fmt} / {level}")
            report = self.llm.ask(self._system("dialect_guard"), script.model_dump_json(indent=1), DialectReport)
            self.progress(f"Critic: {fmt} / {level}")
            critic_input = (f"Format: {fmt}\nLevel brief:\n{brief.model_dump_json(indent=1)}\n\n"
                            f"Draft:\n{script.model_dump_json(indent=1)}\n\n"
                            f"Automatic checks:\n{json.dumps([i.model_dump() for i in issues], ensure_ascii=False, indent=1)}\n\n"
                            f"Dialect Guard report:\n{report.model_dump_json(indent=1)}")
            review = self.llm.ask(self._system("critic", pass_score=str(self.s.pass_score)), critic_input, Review)

            if self.queue_words:
                for w in [*script.new_iraqi_words, *report.new_iraqi_words]:
                    dialect.propose(w.iraqi, w.arabic, source=f"draft:{did}", example=w.example)

            passed = (review.verdict == "publish" and review.total >= self.s.pass_score
                      and report.score >= self.s.dialect_pass_score and not checks.failures(issues))
            draft = Draft(id=did, script=script, review=review, dialect=report, checks=issues,
                          revisions=attempt, passed=passed)
            if passed:
                break
            feedback = "\n".join(
                [f"- {m}" for m in review.must_fix]
                + [f"- [{i.check}] {i.detail}" for i in issues if i.severity in ("fail", "warn")]
                + [f"- Dialect: '{d.original}' -> '{d.suggestion}' ({d.detected_as})" for d in report.issues]
            ) or "- Raise the overall quality; the critic scored it below the bar."
        assert draft is not None
        return draft

    # -- full run ----------------------------------------------------------------------------

    def run(self, topic: str, formats: list[str], levels: list[str]) -> CommitteeResult:
        analysis = self.analyse(topic)
        guidelines = self.strategise(topic, analysis, levels)
        drafts = [self.write(topic, f, lvl, analysis, guidelines) for f in formats for lvl in levels]
        return CommitteeResult(topic=topic, analysis=analysis, guidelines=guidelines, drafts=drafts)
