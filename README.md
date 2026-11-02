# Content Workshop

A **Copywriter Committee** of AI agents that turns one topic into Instagram and TikTok content in
**Baghdadi Iraqi dialect**, at three depth levels: **Simple, Medium, Complex**.

Formats: short video (Reels / TikTok) · long video story · story with question stickers · post + caption.

## How it works

```
topic
  │
  ├─ Analyst ─────── angles, facts, misconceptions, real audience questions, claims to verify
  ├─ Strategist ──── tone, do / don't, one brief per level (different angle per level)
  │
  └─ for each format × level:
        Writer ──────── script: hook, beats, on-screen text, CTA, caption, hashtags, stickers
        Checks ──────── timing, hook ≤ 3s, loop, hashtags ≤ 5, caption window, Iraqi word sheet,
                        other-dialect words, AI-sounding phrases, invisible characters
        Dialect Guard ─ does it sound Baghdadi? suggests fixes, finds new Iraqi words
        Critic ──────── scores out of 100; "publish" or "revise" → back to the Writer (max 2 revisions)
```

New Iraqi words found along the way go into a **review queue**, never straight into the word sheet.

## Install on a Mac (once)

Open **Terminal** (Spotlight → "Terminal"), paste this line, press Enter:

```bash
curl -fsSL https://raw.githubusercontent.com/Marketalse/Content_Workshop/main/install.sh | bash
```

It takes a few minutes the first time (it fetches Python by itself if your Mac doesn't have it) and
opens the dashboard when it's done. That's the only time you need Terminal.

You get one folder:

```
~/Content Workshop/
  Content Workshop.app   ← double-click this (or find "Content Workshop" in Spotlight)
  Drafts/                ← every run you create (.md to read, .json with full detail)
  Data/                  ← your API key, tracking log, your copy of the word sheet, words waiting
  Read me.txt
  (.program/ is hidden: the program itself. Updates replace it; Drafts and Data are never touched.)
```

## Using it

Double-click **Content Workshop**. The dashboard opens in your browser and keeps running quietly in
the background (stop it from Settings, or it stops when the Mac restarts).

- **Create**: write a topic, pick formats and levels, and watch the committee work.
- **Library**: read every run, copy scripts and captions, and record what you actually posted.
- **New words**: approve or reject new Iraqi words and copy the rows for the Google Sheet.
- **Track**: see how much you edit each draft, its results, and whether it's ready to rely on.
- **Check text**: check a script you wrote yourself.
- **Settings**: everything you can change, all in one place:
  - **Updates**: when a new version is on GitHub, "Update ready" shows in the sidebar. One click
    downloads it and restarts the dashboard. It lists what's new.
  - **API key**: saved only in `Data/.env` on your computer.
  - **Iraqi word sheet**: get new words from the Google Sheet (new rows are added, existing rows are
    never overwritten; differences are listed).
  - **Your folders**: open Drafts or Data in Finder.
  - **Stop dashboard**.

The dashboard only listens on your own computer. Nothing is ever posted for you.

To try a version before it's merged, install it with its branch name:
`curl -fsSL https://raw.githubusercontent.com/Marketalse/Content_Workshop/<branch>/install.sh | CW_BRANCH=<branch> bash`.
Running the install command again is always safe: it repairs the program and keeps Drafts and Data.

## For development

```bash
pip install -e ".[dev]"
```

```bash
export ANTHROPIC_API_KEY=...   # or copy .env.example to .env
```

`content-workshop dashboard` runs the same dashboard from a checkout. A checkout keeps its files in
the repo (`output/`, `logs/`, `dialect/`, `.env`) and is updated with git, not the Update button.

## Use it from the command line

Write content:

```bash
content-workshop generate "شلون تبلش تبيع اونلاين بالعراق" --formats short_video,story_questions --levels simple,medium,complex
```

Results are saved to `output/<run>.md` (readable) and `output/<run>.json` (full detail). Every draft is
logged in `logs/drafts.jsonl`. (In the Mac install these are `Drafts/` and `Data/logs/`.)

Check any script or text you wrote yourself:

```bash
content-workshop check my_script.txt
```

Review new Iraqi words, then paste the approved rows into the Google Sheet:

```bash
content-workshop words pending
```

```bash
content-workshop words approve كلش
```

Pull rows that were added to the Google Sheet (never overwrites existing rows):

```bash
content-workshop words sync
```

Track reliability. Record what you actually posted, and later its results:

```bash
content-workshop log edited <draft-id> --final posted.txt --dialect-fixes 2
```

```bash
content-workshop log metrics <draft-id> --views 12000 --retention 0.41 --replies 35
```

```bash
content-workshop log report
```

**Product gate:** across the last 50 reviewed drafts, 80% need only light edits (≤ 20% of words
changed) and there is less than 1 dialect fix per 10 lines.

## Project map

| Path | What it is |
|---|---|
| `dialect/iraqi_words.csv` | Copy of the owner's Google Sheet of Iraqi words (source of truth) |
| `dialect/new_words.csv` | New words waiting for approval |
| `dialect/other_dialects.yaml` | Egyptian / Gulf / Levantine words to block |
| `formats/*.yaml` | Rules and limits per format, plus the three level definitions |
| `hooks/hooks_ar.yaml` | 16 hook formulas in Baghdadi |
| `humanizer/ai_phrases_ar.yaml` | Arabic phrases that sound AI-written |
| `voice/voice.md` | The creator's voice profile (fill this in) |
| `examples/transcripts/` | Corrected transcripts of the creator's own videos |
| `src/content_workshop/` | The committee, checks, CLI, dashboard, updater |
| `install.sh` | One-time Mac install (creates `~/Content Workshop`) |
| `scripts/launch.sh` | What `Content Workshop.app` runs: opens the dashboard, starting it if needed |
| `CLAUDE.md` | Rules every Claude session follows on this repo |

Dialect rules: the sheet wins; words not in the sheet may be standard Arabic; spelling ك not گ, ج not چ.

Parts of the format rules and checks are adapted from
[instagram-agent-skill](https://github.com/Jakeschincariol/instagram-agent-skill) (MIT); see
`THIRD_PARTY_NOTICES.md`.
