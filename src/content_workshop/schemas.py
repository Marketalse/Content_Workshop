"""Structured outputs exchanged between committee members.

Every agent returns one of these models, so each hand-off is validated rather than free text.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Level = Literal["simple", "medium", "complex"]
Format = Literal["short_video", "long_video_story", "story_questions", "post"]


# --- 1. Analyst -------------------------------------------------------------------------------

class Angle(BaseModel):
    name: str
    why_it_works: str


class TopicAnalysis(BaseModel):
    topic: str
    core_idea: str = Field(description="One sentence: what the audience should walk away knowing.")
    angles: list[Angle]
    key_facts: list[str]
    common_misconceptions: list[str]
    audience_questions: list[str] = Field(description="Questions real Iraqi viewers would ask about this topic.")
    claims_to_verify: list[str] = Field(description="Anything that must not be stated without a source.")


# --- 2. Strategist ----------------------------------------------------------------------------

class LevelBrief(BaseModel):
    level: Level
    audience: str
    assumed_knowledge: str
    angle: str = Field(description="Which analyst angle this level uses.")
    key_message: str


class Guidelines(BaseModel):
    tone: str
    do: list[str]
    dont: list[str]
    levels: list[LevelBrief]


# --- Shared ------------------------------------------------------------------------------------

class WordProposal(BaseModel):
    iraqi: str = Field(description="The Iraqi word or expression as written in the script.")
    arabic: str = Field(description="Its standard Arabic meaning.")
    example: str = Field("", description="The line where it was used.")


# --- 3. Writer --------------------------------------------------------------------------------

class Beat(BaseModel):
    label: str = Field(description="e.g. hook, setup, point 1, twist, payoff, CTA")
    spoken: str = Field(description="What is said or written, in Baghdadi Iraqi.")
    on_screen_text: str = ""
    visual_note: str = Field("", description="Shot, B-roll or design direction, in English.")
    seconds: float | None = None


class Script(BaseModel):
    format: Format
    level: Level
    title: str
    hook: str
    beats: list[Beat]
    cta: str
    caption: str = ""
    hashtags: list[str] = []
    sticker_questions: list[str] = Field([], description="Only for story_questions.")
    estimated_seconds: float | None = None
    new_iraqi_words: list[WordProposal] = Field(
        [], description="Iraqi words or expressions you used that are NOT in the Iraqi word sheet."
    )

    def lines(self) -> list[str]:
        """All audience-facing text, one item per line, for dialect checks and edit tracking."""
        out = [self.hook]
        for b in self.beats:
            out.append(b.spoken)
            if b.on_screen_text:
                out.append(b.on_screen_text)
        out += [self.cta, *self.sticker_questions]
        if self.caption:
            out.append(self.caption)
        return [line for line in out if line.strip()]

    def plain_text(self) -> str:
        return "\n".join(self.lines())


# --- 4. Dialect Guard -------------------------------------------------------------------------

class DialectIssue(BaseModel):
    original: str = Field(description="The exact word or phrase that is not Baghdadi.")
    detected_as: Literal["msa", "egyptian", "gulf", "levantine", "other", "unnatural"]
    suggestion: str = Field(description="Baghdadi replacement.")
    line: str = ""


class DialectReport(BaseModel):
    score: int = Field(ge=0, le=10, description="10 = sounds like a Baghdadi creator wrote it.")
    issues: list[DialectIssue]
    new_iraqi_words: list[WordProposal] = Field(
        [], description="Good Baghdadi words in the draft that are missing from the word sheet."
    )
    notes: str = ""


# --- 5. Critic --------------------------------------------------------------------------------

class CriterionScore(BaseModel):
    criterion: str
    score: int = Field(ge=0, le=10)
    comment: str


class Review(BaseModel):
    scores: list[CriterionScore]
    total: int = Field(ge=0, le=100, description="Weighted total out of 100.")
    must_fix: list[str]
    verdict: Literal["publish", "revise"]


# --- Deterministic checks ---------------------------------------------------------------------

class CheckIssue(BaseModel):
    severity: Literal["fail", "warn", "info"]
    check: str
    detail: str


# --- Result -----------------------------------------------------------------------------------

class Draft(BaseModel):
    id: str
    script: Script
    review: Review | None = None
    dialect: DialectReport | None = None
    checks: list[CheckIssue] = []
    revisions: int = 0
    passed: bool = False


class CommitteeResult(BaseModel):
    topic: str
    analysis: TopicAnalysis
    guidelines: Guidelines
    drafts: list[Draft]
