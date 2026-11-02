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
rows the repo copy lacks, re-download it and update `dialect/iraqi_words.csv`.

## Working rules

- Never invent numbers, results, clients or quotes in scripts; use `{{رقمك}}` placeholders.
- Nothing is ever posted automatically. The owner records and posts.
- Run `python -m pytest -q` before committing. Tests use a fake model and need no API key.
- Model calls go through `src/content_workshop/llm.py` only (default `claude-opus-5-5`, adaptive thinking,
  structured outputs, server-side refusal fallback).
- Material adapted from instagram-agent-skill (MIT) is listed in `THIRD_PARTY_NOTICES.md`; keep it updated.
