# Content Workshop — rules for Claude sessions

A copywriting committee (Analyst → Strategist → Writer → Dialect Guard → Critic) that turns one
topic into Baghdadi-Iraqi content for Instagram and TikTok, at Simple / Medium / Complex levels.
Formats: short video, long video story, story question stickers, posts.

## Dialect rules (agreed with the owner)

- Language of all audience-facing text: **Baghdadi Iraqi**.
- **The Iraqi word sheet is the source of truth.** Google Sheet "Iraqi Dilect words"
  (id `11l86Ku11cR8_0mTtDtbAu4aNNltf7WIeTSF_zcQQ5dM`); repo copy `dialect/iraqi_words.csv`.
  If a formal Arabic word has an entry, use the Iraqi word. **Not in the sheet = standard Arabic is fine.**
- Rows where Iraqi and Arabic are the same (e.g. يظن، إنه، أداة) are fine as-is.
- Spelling: **ك not گ, ج not چ** (كال، هيج).
- Egyptian, Gulf and Levantine words are blocked (`dialect/other_dialects.yaml`, `enabled: true`).

## Growing the word sheet (always do this)

Whenever a new Iraqi word appears — in generated content, in the owner's edits, **or in conversation
with the owner** — add it to the review queue instead of the sheet:

```bash
content-workshop words add "<Iraqi>" "<Arabic meaning>" --example "<line>"
```

Show the owner the pending list (`content-workshop words pending`) and only run
`content-workshop words approve ...` after they say yes. Then give them the printed rows to paste into the
Google Sheet (the Drive connector can read the sheet but cannot edit cells). If the Google Sheet has
rows the repo copy lacks, run `content-workshop words sync` (adds missing rows, never overwrites; the repo
copy carries spelling fixes the Google Sheet may not have).

## How the owner runs it (keep this working)

- The owner installed once with `install.sh` and only uses the dashboard (`~/Content Workshop/Content Workshop.app`).
  No Terminal, no git on their side. Don't ask them to run commands; add a dashboard control instead.
- **Updates reach the owner only from `main`**: the dashboard's Update button downloads the latest `main`
  from GitHub. Work isn't "delivered" until it's merged. Before merging, they can try a branch with
  `curl -fsSL https://raw.githubusercontent.com/Marketalse/Content_Workshop/<branch>/install.sh | CW_BRANCH=<branch> bash`.
- Their files live outside the program: `Drafts/` (CW_OUTPUT_DIR) and `Data/` (CW_DATA_DIR: `.env`, `logs/`,
  `words/iraqi_words.csv`, `words/new_words.csv`). Updates replace only `.program/code`. Never move user data
  into the program folder.
- Their word sheet copy is rebuilt from `dialect/iraqi_words.csv` on every start (repo rows win; words only they
  approved are kept), and words queued in `dialect/new_words.csv` show up on their New words page.
- Adding a Python dependency is fine: the updater reinstalls when `pyproject.toml` changes.

## Working rules

- Never invent numbers, results, clients or quotes in scripts; use `{{رقمك}}` placeholders.
- Nothing is ever posted automatically. The owner records and posts.
- Run `python -m pytest -q` before committing. Tests use a fake model and need no API key.
- Model calls go through `src/content_workshop/llm.py` only (adaptive thinking, structured outputs).
  Default model is `claude-haiku-5-5` (the owner's choice, for cost); they switch to Sonnet 5.5 / Opus 5.5 in
  Settings (saved as `CW_MODEL`). Server-side refusal fallback is sent only for models that support it (not Haiku).
- The API key is checked with Anthropic before it's saved, and only `Data/.env` counts in the Mac install
  (the launcher ignores keys/tokens from the Terminal environment).
- Material adapted from instagram-agent-skill (MIT) is listed in `THIRD_PARTY_NOTICES.md`; keep it updated.
