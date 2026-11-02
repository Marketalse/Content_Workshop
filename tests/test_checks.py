from content_workshop import checks, humanize
from content_workshop.schemas import Beat, Script


def make(**kw):
    base = dict(format="short_video", level="simple", title="t", hook="محد يكلك هاي الشغلة",
                beats=[Beat(label="body", spoken="اول نقطة بسيطة"), Beat(label="payoff", spoken="وهاي الشغلة")],
                cta="اكتبلي بالتعليقات")
    base.update(kw)
    return Script(**base)


def test_clean_removes_invisible_and_em_dash():
    text, counts = humanize.clean("هسه​ راح — نبلش هسه…")
    assert "​" not in text and "—" not in text and "…" not in text
    assert counts["invisible"] == 1 and counts["typography"] == 2 and counts["spaces"] == 1


def test_ai_phrase_flagged():
    hits = humanize.scan_phrases("في عالمنا اليوم كلشي تغير")
    assert [h["phrase"] for h in hits] == ["في عالمنا اليوم"]


def test_long_hook_fails():
    long_hook = " ".join(["كلمة"] * 12)  # ~5s at 140 wpm
    issues = checks.timing(make(hook=long_hook))
    assert any(i.check == "hook length" and i.severity == "fail" for i in issues)


def test_loop_detected():
    assert not any(i.check == "loop" for i in checks.timing(make()))
    no_loop = make(beats=[Beat(label="b", spoken="موضوع ثاني تماما")], cta="تابعني")
    assert any(i.check == "loop" for i in checks.timing(no_loop))


def test_hashtag_limit_and_visible_window():
    s = make(caption="سطر " * 40 + "\nباقي", hashtags=[f"tag{i}" for i in range(6)])
    found = {i.check for i in checks.caption(s)}
    assert {"hashtags", "visible window"} <= found


def test_story_requires_sticker():
    s = make(format="story_questions")
    assert any(i.check == "stickers" and i.severity == "fail" for i in checks.stickers(s))


def test_language_check_flags_formal_and_placeholders():
    s = make(hook="سوف اكلك {{رقمك}}")
    found = {i.check for i in checks.language(s)}
    assert "dialect: msa" in found and "needs your input" in found


def test_on_screen_word_limit():
    s = make(beats=[Beat(label="b", spoken="هاي", on_screen_text="واحد اثنين ثلاثة اربعة خمسة ستة سبعة")])
    assert any(i.check == "on-screen text" for i in checks.on_screen(s))
