import pytest
from docx import Document
from docx.oxml.ns import qn

from hanzi_trainer import (
    DATA_FILE,
    PINYIN_FONT,
    PLAIN_FONT,
    build_document,
    document_bytes,
    load_known_chars,
    load_levels,
    parse_selections,
)


def test_levels_available():
    levels = load_levels(DATA_FILE)
    assert levels == {
        "YCT": 4,
        "HSK2.0": 6,
        "HSK3.0": 7,
        "HSK3.0-2026": 7,
    }


@pytest.mark.parametrize(
    "selections, expected",
    [
        ({"YCT": 1}, 99),
        ({"YCT": 3}, 353),
        ({"HSK3.0": 2}, 598),
    ],
)
def test_up_to_level_counts(selections, expected):
    # Regression values for the bundled data/levels.csv.
    assert len(load_known_chars(DATA_FILE, selections)) == expected


def test_levels_are_cumulative():
    lower = load_known_chars(DATA_FILE, {"YCT": 2})
    higher = load_known_chars(DATA_FILE, {"YCT": 3})
    assert lower < higher


def test_multiple_systems_union():
    a = load_known_chars(DATA_FILE, {"YCT": 2})
    b = load_known_chars(DATA_FILE, {"HSK3.0": 1})
    both = load_known_chars(DATA_FILE, {"YCT": 2, "HSK3.0": 1})
    assert both == a | b


def test_unknown_system_raises():
    with pytest.raises(ValueError, match="Unknown word list"):
        load_known_chars(DATA_FILE, {"HSK": 3})


def test_parse_selections():
    assert parse_selections("YCT=3, HSK3.0=1") == {"YCT": 3, "HSK3.0": 1}
    with pytest.raises(ValueError):
        parse_selections("YCT")


def test_document_fonts_follow_known_characters():
    # 你 is in YCT 1; 龙 is not.
    known = load_known_chars(DATA_FILE, {"YCT": 1})
    assert "你" in known and "龙" not in known
    doc = build_document("你龙\n你", known)
    paragraphs = doc.paragraphs
    assert len(paragraphs) == 2
    first = paragraphs[0].runs
    assert [r.text for r in first] == ["你", "龙"]
    assert first[0].font.name == PLAIN_FONT
    assert first[1].font.name == PINYIN_FONT
    for run in first:
        east_asia = run._element.rPr.rFonts.get(qn("w:eastAsia"))
        assert east_asia == run.font.name


def test_consecutive_same_font_characters_share_a_run():
    known = load_known_chars(DATA_FILE, {"YCT": 1})
    doc = build_document("你好我", known)
    assert len(doc.paragraphs[0].runs) == 1


def test_document_bytes_roundtrip(tmp_path):
    out = tmp_path / "w.docx"
    out.write_bytes(document_bytes(build_document("你好", set())))
    assert Document(str(out)).paragraphs[0].text == "你好"
