import shutil

from content_workshop import dialect
from content_workshop.text_ar import find_phrase, normalize


def test_normalize_spelling_rule_and_alef():
    assert normalize("گال") == normalize("كال")
    assert normalize("هيچ") == "هيج"
    assert normalize("أداة") == "اداة"


def test_find_phrase_with_prefix_and_diacritics():
    assert find_phrase("وسوفَ نتكلم", "سوف")
    assert find_phrase("فماذا قال المدير؟", "ماذا قال")
    assert not find_phrase("سوفت وير", "سوف")  # whole words only


def test_sheet_loads_with_corrections():
    sheet = dialect.load_sheet()
    by_iraqi = {e.iraqi: e for e in sheet}
    assert by_iraqi["يريدوك"].arabic == ("يريدونك",)
    assert by_iraqi["صار"].arabic == ("حسناً", "تمام")
    assert by_iraqi["يظن"].same_in_both


def test_formal_words_get_iraqi_suggestions():
    issues = dialect.scan_formal("ماذا قال لك؟ سوف نرى الان", dialect.load_sheet())
    pairs = {(i.original, i.suggestion) for i in issues}
    assert ("ماذا قال", "شكال") in pairs
    assert ("سوف", "راح") in pairs
    assert ("الان", "هسه") in pairs
    # "قال" alone is not reported separately because it's inside "ماذا قال"
    assert not any(i.original == "قال" for i in issues)


def test_words_not_in_sheet_are_fine():
    assert dialect.scan_formal("المنتج جميل والسعر مناسب", dialect.load_sheet()) == []


def test_same_in_both_rows_never_flagged():
    assert dialect.scan_formal("يظن إنه أداة", dialect.load_sheet()) == []


def test_other_dialects_blocked():
    issues = dialect.scan_other_dialects("دلوقتي عايز اروح", dialect.load_other_dialects())
    assert {i.detected_as for i in issues} == {"egyptian"}
    assert {i.suggestion for i in issues} == {"هسه", "اريد"}


def test_new_word_queue_approve_flow(tmp_path):
    sheet = tmp_path / "sheet.csv"
    pend = tmp_path / "new.csv"
    shutil.copy(dialect.SHEET, sheet)
    assert dialect.propose("كلش", "جداً", "test", "كلش حلو", sheet, pend)
    assert not dialect.propose("كلش", "جداً", "test", "", sheet, pend)      # already queued
    assert not dialect.propose("شنو", "ماذا", "test", "", sheet, pend)     # already in sheet
    assert [r["Iraqi"] for r in dialect.pending(pend)] == ["كلش"]
    rows = dialect.decide(["كلش"], True, sheet, pend)
    assert rows == [["55", "كلش", "جداً"]]
    assert dialect.pending(pend) == []
    assert "كلش" in {e.iraqi for e in dialect.load_sheet(sheet)}
