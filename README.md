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

## Setup

```bash
pip install -e ".[dev]"
```

```bash
export ANTHROPIC_API_KEY=...   # or copy .env.example
```

## Dashboard (no Terminal needed)

On a Mac, double-click **`Start Dashboard.command`** in the project folder. The first time, it sets
everything up (a minute or two); after that it opens straight away in your browser. Keep the small
window it opens running while you work, and close it when you're done.

If macOS says it can't open the file, right-click it → **Open** → **Open** (only needed once).

In the dashboard you can:

- **Create**: write a topic, pick formats and levels, and watch the committee work.
- **Library**: read every run, copy scripts and captions, and record what you actually posted.
- **New words**: approve or reject new Iraqi words and copy the rows for the Google Sheet.
- **Track**: see how much you edit each draft, its results, and whether it's ready to rely on.
- **Check text**: check a script you wrote yourself.
- **Settings**: save your API key (stored only in `.env` on your computer).

From a terminal the same thing is `content-workshop dashboard`. It only listens on your own computer.

## Use it from the command line

Write content:

```bash
content-workshop generate "كيف تبدأ تبيع اونلاين بالعراق" --formats short_video,story_questions --levels simple,medium,complex
```

Results are saved to `output/<run>.md` (readable) and `output/<run>.json` (full detail). Every draft is
logged in `logs/drafts.jsonl`.

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
| `src/content_workshop/` | The committee, checks, CLI |
| `CLAUDE.md` | Rules every Claude session follows on this repo |

Dialect rules: the sheet wins; words not in the sheet may be standard Arabic; spelling ك not گ, ج not چ.

Parts of the format rules and checks are adapted from
[instagram-agent-skill](https://github.com/Jakeschincariol/instagram-agent-skill) (MIT); see
`THIRD_PARTY_NOTICES.md`.
