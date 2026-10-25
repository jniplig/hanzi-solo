"""Hanzi Solo: build reading worksheets where known characters lose their pinyin.

Characters the student already knows (per the chosen YCT/HSK levels) are
written plainly. Every other character keeps its pinyin. Two modes:

- "pinyin" (default): the program writes the pinyin itself as Word ruby text
  above each unknown character. No special font is needed.
- "font": unknown characters use a pinyin font (e.g. FZKTPY) that draws the
  pinyin; known characters switch to a plain font. The font must be installed.
"""
from __future__ import annotations

import argparse
import csv
import io
import sys
from pathlib import Path

from xml.sax.saxutils import escape

from docx import Document
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls, qn
from docx.shared import Pt
from pypinyin import Style, pinyin

DATA_FILE = Path(__file__).parent / "data" / "levels.csv"
PINYIN_FONT = "FZKTPY"  # font mode: a font that draws pinyin above each character
PLAIN_FONT = "KaiTi"    # plain Kai font, no pinyin (ships with Windows)
RUBY_FONT = "Arial"     # pinyin mode: font for the pinyin letters and tone marks
MODE_PINYIN = "pinyin"
MODE_FONT = "font"


def is_hanzi(ch: str) -> bool:
    return "一" <= ch <= "鿿"


def load_levels(csv_path: Path | str = DATA_FILE) -> dict[str, int]:
    """Return {system: highest level} for every word list in the CSV."""
    top: dict[str, int] = {}
    with open(csv_path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            level = int(row["level"])
            if level > top.get(row["system"], 0):
                top[row["system"]] = level
    return top


def load_known_chars(
    csv_path: Path | str, selections: dict[str, int]
) -> set[str]:
    """Characters in every word up to and including the chosen level.

    selections: {"YCT": 3, "HSK3.0": 1}. Raises ValueError for an unknown
    system name, so a typo can't silently produce an empty set.
    """
    known: set[str] = set()
    seen_systems: set[str] = set()
    with open(csv_path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            system = row["system"]
            seen_systems.add(system)
            max_level = selections.get(system)
            if max_level is not None and int(row["level"]) <= max_level:
                known.update(ch for ch in row["word"] if is_hanzi(ch))
    unknown = set(selections) - seen_systems
    if unknown:
        raise ValueError(
            f"Unknown word list(s): {', '.join(sorted(unknown))}. "
            f"Available: {', '.join(sorted(seen_systems))}"
        )
    return known


def _set_font(run, name: str, size_pt: int) -> None:
    run.font.size = Pt(size_pt)
    run.font.name = name
    run._element.rPr.rFonts.set(qn("w:eastAsia"), name)


def pinyin_per_character(line: str) -> list[str]:
    """One pinyin string per character of `line` ('' where there is none).

    Readings come from the whole phrase, so 银行 gives yín háng and 长大 gives
    zhǎng dà. No tone sandhi is applied, matching printed textbooks (nǐ hǎo).
    """
    readings = pinyin(line, style=Style.TONE, errors=lambda s: [""] * len(s))
    if len(readings) != len(line):
        raise ValueError("Could not align pinyin with the characters of a line.")
    return [r[0] for r in readings]


def _xml_attr(value: str) -> str:
    return escape(value, {'"': "&quot;"})


def _rpr_xml(font: str, half_points: int) -> str:
    f = _xml_attr(font)
    return (
        f'<w:rPr><w:rFonts w:ascii="{f}" w:hAnsi="{f}" w:eastAsia="{f}" w:cs="{f}"/>'
        f'<w:sz w:val="{half_points}"/><w:szCs w:val="{half_points}"/></w:rPr>'
    )


def _ruby_run(
    base: str, reading: str, base_font: str, ruby_font: str, size_pt: int, ruby_pt: int
):
    """A Word ruby annotation: `reading` printed above `base`."""
    base_hp, ruby_hp = size_pt * 2, ruby_pt * 2
    raise_hp = round(base_hp * 0.86)
    xml = (
        f"<w:r {nsdecls('w')}><w:ruby><w:rubyPr>"
        '<w:rubyAlign w:val="center"/>'
        f'<w:hps w:val="{ruby_hp}"/>'
        f'<w:hpsRaise w:val="{raise_hp}"/>'
        f'<w:hpsBaseText w:val="{base_hp}"/>'
        '<w:lid w:val="zh-CN"/>'
        "</w:rubyPr>"
        f"<w:rt><w:r>{_rpr_xml(ruby_font, ruby_hp)}<w:t>{escape(reading)}</w:t></w:r></w:rt>"
        f"<w:rubyBase><w:r>{_rpr_xml(base_font, base_hp)}<w:t>{escape(base)}</w:t></w:r></w:rubyBase>"
        "</w:ruby></w:r>"
    )
    return parse_xml(xml)


def _add_pinyin_paragraph(
    doc: Document,
    line: str,
    known: set[str],
    plain_font: str,
    ruby_font: str,
    size_pt: int,
    ruby_pt: int,
) -> None:
    para = doc.add_paragraph()
    buffer = ""
    for ch, reading in zip(line, pinyin_per_character(line)):
        if reading and is_hanzi(ch) and ch not in known:
            if buffer:
                _set_font(para.add_run(buffer), plain_font, size_pt)
                buffer = ""
            para._p.append(
                _ruby_run(ch, reading, plain_font, ruby_font, size_pt, ruby_pt)
            )
        else:
            buffer += ch
    if buffer:
        _set_font(para.add_run(buffer), plain_font, size_pt)


def _add_font_paragraph(
    doc: Document,
    line: str,
    known: set[str],
    pinyin_font: str,
    plain_font: str,
    size_pt: int,
) -> None:
    """Consecutive characters share one run per font."""
    para = doc.add_paragraph()
    buffer = ""
    current = None
    for ch in line:
        font = plain_font if ch in known else pinyin_font
        if font != current and buffer:
            _set_font(para.add_run(buffer), current, size_pt)
            buffer = ""
        current = font
        buffer += ch
    if buffer:
        _set_font(para.add_run(buffer), current, size_pt)


def build_document(
    text: str,
    known: set[str],
    mode: str = MODE_PINYIN,
    pinyin_font: str = PINYIN_FONT,
    plain_font: str = PLAIN_FONT,
    ruby_font: str = RUBY_FONT,
    size_pt: int = 28,
    ruby_pt: int = 12,
) -> Document:
    """One paragraph per line of `text`."""
    if mode not in (MODE_PINYIN, MODE_FONT):
        raise ValueError(f"Unknown mode '{mode}'")
    doc = Document()
    for line in text.splitlines() or [""]:
        if mode == MODE_PINYIN:
            _add_pinyin_paragraph(
                doc, line, known, plain_font, ruby_font, size_pt, ruby_pt
            )
        else:
            _add_font_paragraph(doc, line, known, pinyin_font, plain_font, size_pt)
    return doc


def document_bytes(doc: Document) -> bytes:
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def parse_selections(arg: str) -> dict[str, int]:
    """Parse 'YCT=3,HSK3.0=1' into {'YCT': 3, 'HSK3.0': 1}."""
    selections: dict[str, int] = {}
    for part in filter(None, (p.strip() for p in arg.split(","))):
        system, _, level = part.partition("=")
        if not level.isdigit():
            raise ValueError(f"Expected SYSTEM=LEVEL, got '{part}'")
        selections[system.strip()] = int(level)
    return selections


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("levels", help="e.g. 'YCT=3,HSK3.0=1' (up to and including)")
    parser.add_argument("passage", help="text file containing the Chinese passage")
    parser.add_argument("-o", "--output", default="worksheet.docx")
    parser.add_argument("--data", default=str(DATA_FILE))
    parser.add_argument(
        "--mode",
        choices=[MODE_PINYIN, MODE_FONT],
        default=MODE_PINYIN,
        help="pinyin: write pinyin into the file (no font needed); "
        "font: rely on an installed pinyin font",
    )
    parser.add_argument("--pinyin-font", default=PINYIN_FONT, help="font mode only")
    parser.add_argument("--plain-font", default=PLAIN_FONT)
    parser.add_argument("--ruby-font", default=RUBY_FONT, help="pinyin mode only")
    args = parser.parse_args(argv)

    known = load_known_chars(args.data, parse_selections(args.levels))
    text = Path(args.passage).read_text(encoding="utf-8")
    doc = build_document(
        text,
        known,
        mode=args.mode,
        pinyin_font=args.pinyin_font,
        plain_font=args.plain_font,
        ruby_font=args.ruby_font,
    )
    Path(args.output).write_bytes(document_bytes(doc))
    print(f"{len(known)} known characters -> {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
