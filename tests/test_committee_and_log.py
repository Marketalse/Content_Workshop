from content_workshop import logbook
from content_workshop.committee import Committee, render
from content_workshop.config import Settings
from content_workshop.schemas import (
    Angle, Beat, CriterionScore, DialectReport, Guidelines, LevelBrief, Review, Script, TopicAnalysis,
)


class FakeLLM:
    """Returns canned objects. The first Critic review fails, the second passes."""

    def __init__(self):
        self.calls = []
        self.reviews = 0

    def ask(self, system, user, schema):
        self.calls.append((schema.__name__, system, user))
        if schema is TopicAnalysis:
            return TopicAnalysis(topic="t", core_idea="فكرة", angles=[Angle(name="a", why_it_works="w")],
                                 key_facts=[], common_misconceptions=[], audience_questions=[], claims_to_verify=[])
        if schema is Guidelines:
            return Guidelines(tone="t", do=[], dont=[], levels=[LevelBrief(
                level="simple", audience="a", assumed_knowledge="none", angle="a", key_message="k")])
        if schema is Script:
            return Script(format="post", level="complex", title="عنوان", hook="محد يكلك هاي — الشغلة",
                          beats=[Beat(label="payoff", spoken="وهاي الشغلة")], cta="اكتبلي")
        if schema is DialectReport:
            return DialectReport(score=9, issues=[])
        if schema is Review:
            self.reviews += 1
            ok = self.reviews > 1
            return Review(scores=[CriterionScore(criterion="hook", score=8, comment="")], total=90 if ok else 60,
                          must_fix=[] if ok else ["قوّي الهوك"], verdict="publish" if ok else "revise")
        raise AssertionError(schema)


def test_render_keeps_double_braces():
    text = render("house_rules", sheet="S", voice="V")
    assert "{{رقمك}}" in text and "S" in text and "{sheet}" not in text


def test_committee_revises_until_pass():
    llm = FakeLLM()
    c = Committee(llm, Settings(max_revisions=2), queue_words=False)
    result = c.run("topic", ["short_video"], ["simple"])
    d = result.drafts[0]
    assert d.passed and d.revisions == 1
    # format/level are forced to what was requested, and the em dash was cleaned
    assert (d.script.format, d.script.level) == ("short_video", "simple")
    assert "—" not in d.script.hook
    # the revision prompt carried the critic's must-fix point
    second_writer = [u for name, _, u in llm.calls if name == "Script"][1]
    assert "قوّي الهوك" in second_writer
    # sheet and Baghdadi rules reach every agent
    assert all("شكال" in system for _, system, _ in llm.calls)


def test_logbook_report(tmp_path):
    path = tmp_path / "log.jsonl"
    llm = FakeLLM()
    d = Committee(llm, Settings(max_revisions=2), queue_words=False).run("t", ["short_video"], ["simple"]).drafts[0]
    logbook.log_draft("t", d, path)
    ratio = logbook.log_edit(d.id, d.script.plain_text(), 0, path)
    assert ratio == 0.0
    rep = logbook.report(path)
    assert rep["reviewed"] == 1 and rep["light_edit_share"] == 1.0 and not rep["product_ready"]


def test_edit_ratio():
    assert logbook.edit_ratio("هسه راح نبلش", "هسه راح نبلش") == 0.0
    assert logbook.edit_ratio("هسه راح نبلش", "باجر نبلش") > 0.3
