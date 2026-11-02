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

# Where the owner's own files live. A development checkout keeps them inside the repo (as before).
# The Mac install (install.sh) keeps the program and the owner's files apart, so updates can replace
# the program without touching anything the owner made:
#   ~/Content Workshop/Drafts   every run                     (CW_OUTPUT_DIR)
#   ~/Content Workshop/Data     key, log, word sheet, queue   (CW_DATA_DIR)
#   ~/Content Workshop/.program the code and Python; replaced by updates (CW_PROGRAM_DIR)
INSTALLED = bool(os.getenv("CW_DATA_DIR"))
DATA_DIR = Path(os.environ["CW_DATA_DIR"]) if INSTALLED else REPO_ROOT
PROGRAM_DIR = Path(os.environ["CW_PROGRAM_DIR"]) if os.getenv("CW_PROGRAM_DIR") else None
LOGS_DIR = DATA_DIR / "logs"
OUTPUT_DIR = Path(os.environ["CW_OUTPUT_DIR"]) if os.getenv("CW_OUTPUT_DIR") else DATA_DIR / "output"
WORDS_DIR = DATA_DIR / "words" if INSTALLED else DIALECT_DIR
ENV_FILE = DATA_DIR / ".env"

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
