import pytest
from docx import Document
from docx.oxml.ns import qn

from hanzi_trainer import (
    DATA_FILE,
    MODE_FONT,
    MODE_PINYIN,
    PINYIN_FONT,
    PLAIN_FONT,
    RUBY_FONT,
    build_document,
    document_bytes,
    load_known_chars,
    load_levels,
    main,
    parse_selections,
    pinyin_per_character,
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
    doc = build_document("你龙\n你", known, mode=MODE_FONT)
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
    doc = build_document("你好我", known, mode=MODE_FONT)
    assert len(doc.paragraphs[0].runs) == 1


def test_document_bytes_roundtrip(tmp_path):
    out = tmp_path / "w.docx"
    out.write_bytes(document_bytes(build_document("你好", set(), mode=MODE_FONT)))
    assert Document(str(out)).paragraphs[0].text == "你好"


# --- pinyin (ruby) mode -------------------------------------------------------


def _ruby_pairs(doc):
    """[(base, pinyin)] for every ruby annotation in document order."""
    pairs = []
    for ruby in doc.element.body.iter(qn("w:ruby")):
        rt = "".join(t.text for t in ruby.find(qn("w:rt")).iter(qn("w:t")))
        base = "".join(t.text for t in ruby.find(qn("w:rubyBase")).iter(qn("w:t")))
        pairs.append((base, rt))
    return pairs


def test_pinyin_per_character_is_aligned():
    assert pinyin_per_character("ab你c") == ["", "", "nǐ", ""]
    assert pinyin_per_character("") == []


def test_pinyin_uses_phrase_context():
    assert pinyin_per_character("银行") == ["yín", "háng"]
    assert pinyin_per_character("他行不行") == ["tā", "xíng", "bù", "xíng"]
    assert pinyin_per_character("长大了") == ["zhǎng", "dà", "le"]


def test_pinyin_mode_annotates_only_unknown_hanzi():
    known = load_known_chars(DATA_FILE, {"YCT": 1})
    doc = build_document("你龙", known)  # default mode is pinyin
    assert _ruby_pairs(doc) == [("龙", "lóng")]
    # The known character is an ordinary plain run.
    plain = doc.paragraphs[0].runs[0]
    assert plain.text == "你" and plain.font.name == PLAIN_FONT


def test_pinyin_mode_skips_known_punctuation_and_ascii():
    known = load_known_chars(DATA_FILE, {"YCT": 1})
    doc = build_document("你好,Hello 123。", known)
    assert _ruby_pairs(doc) == []
    assert doc.paragraphs[0].text == "你好,Hello 123。"


def test_pinyin_mode_one_paragraph_per_line():
    doc = build_document("龙\n\n龙", set())
    assert len(doc.paragraphs) == 3
    assert _ruby_pairs(doc) == [("龙", "lóng"), ("龙", "lóng")]


def test_ruby_properties_and_fonts():
    doc = build_document("龙", set(), size_pt=30, ruby_pt=10)
    ruby = next(doc.element.body.iter(qn("w:ruby")))
    props = ruby.find(qn("w:rubyPr"))
    assert props.find(qn("w:hps")).get(qn("w:val")) == "20"
    assert props.find(qn("w:hpsBaseText")).get(qn("w:val")) == "60"
    rt_fonts = ruby.find(qn("w:rt")).find(".//" + qn("w:rFonts"))
    base_fonts = ruby.find(qn("w:rubyBase")).find(".//" + qn("w:rFonts"))
    assert rt_fonts.get(qn("w:eastAsia")) == RUBY_FONT
    assert base_fonts.get(qn("w:eastAsia")) == PLAIN_FONT


def test_font_names_with_special_characters_are_escaped(tmp_path):
    doc = build_document("龙", set(), plain_font='A"B&<C', ruby_font="X'Y>")
    out = tmp_path / "w.docx"
    out.write_bytes(document_bytes(doc))
    assert _ruby_pairs(Document(str(out))) == [("龙", "lóng")]


def test_unknown_mode_raises():
    with pytest.raises(ValueError, match="Unknown mode"):
        build_document("你", set(), mode="nope")


def test_cli_writes_a_worksheet_in_each_mode(tmp_path):
    passage = tmp_path / "p.txt"
    passage.write_text("你好,我是龙。\n", encoding="utf-8")
    for mode in (MODE_PINYIN, MODE_FONT):
        out = tmp_path / f"{mode}.docx"
        assert main(["YCT=1", str(passage), "-o", str(out), "--mode", mode]) == 0
        assert Document(str(out)).paragraphs
    assert _ruby_pairs(Document(str(tmp_path / "pinyin.docx"))) == [("龙", "lóng")]
    assert _ruby_pairs(Document(str(tmp_path / "font.docx"))) == []
