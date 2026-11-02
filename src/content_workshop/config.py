"""Paths and runtime settings. Everything here can be overridden with environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
DIALECT_DIR = REPO_ROOT / "dialect"
FORMATS_DIR = REPO_ROOT / "formats"
EXAMPLES_DIR = REPO_ROOT / "examples"
LOGS_DIR = REPO_ROOT / "logs"
OUTPUT_DIR = REPO_ROOT / "output"

LEVELS = ("simple", "medium", "complex")
FORMATS = ("short_video", "long_video_story", "story_questions", "post")


@dataclass(frozen=True)
class Settings:
    model: str = field(default_factory=lambda: os.getenv("CW_MODEL", "claude-opus-5-5"))
    effort: str = field(default_factory=lambda: os.getenv("CW_EFFORT", "high"))
    max_revisions: int = field(default_factory=lambda: int(os.getenv("CW_MAX_REVISIONS", "2")))
    max_tokens: int = 16000
    # Critic total (0-100) a draft needs before it leaves the committee.
    pass_score: int = 80
    # Dialect Guard score (0-10) a draft needs before it leaves the committee.
    dialect_pass_score: int = 8
