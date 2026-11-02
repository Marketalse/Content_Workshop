# Third-party notices

Parts of this project are adapted from **instagram-agent-skill** by Jake Schincariol
(https://github.com/Jakeschincariol/instagram-agent-skill, commit `d03c56b`), used under the MIT License.

| Our file | Adapted from |
|---|---|
| `formats/short_video.yaml` | `skills/ig-reel/SKILL.md` (Reel shape, on-screen rules, safe zones) |
| `formats/story_questions.yaml` | `skills/ig-story/SKILL.md` (frame sequence, sticker jobs) |
| `formats/post.yaml`, `src/content_workshop/checks.py` (caption) | `skills/ig-caption/caption.py` |
| `src/content_workshop/checks.py` (timing) | `skills/ig-reel/beats.py` |
| `hooks/hooks_ar.yaml` | `skills/ig-reel/hooks.json` (16 of 26 formulas, rewritten in Baghdadi) |
| `src/content_workshop/humanize.py`, `humanizer/ai_phrases_ar.yaml` | `skills/ig-human/humanize.py`, `skills/ig-human/slop.json` |
| `voice/voice.md` | `templates/voice.md` |

All adapted material was rewritten for Baghdadi Iraqi Arabic, TikTok, and this project's agent committee.

---

MIT License

Copyright (c) 2026 Jake Schincariol

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
