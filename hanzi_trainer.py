"""Hanzi Solo: build reading worksheets where known characters lose their pinyin.

The pinyin comes from a font (FZKTPY) that draws pinyin above each character.
Characters the student already knows (per the chosen YCT/HSK levels) are
written in a plain font instead, so no pinyin is drawn for them.
"""
from __future__ import annotations

import argparse
import csv
import io
import sys
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn
from docx.shared import Pt

DATA_FILE = Path(__file__).parent / "data" / "levels.csv"
PINYIN_FONT = "FZKTPY"  # draws pinyin above each character
PLAIN_FONT = "KaiTi"    # plain Kai font, no pinyin (ships with Windows)


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


def build_document(
    text: str,
    known: set[str],
    pinyin_font: str = PINYIN_FONT,
    plain_font: str = PLAIN_FONT,
    size_pt: int = 28,
) -> Document:
    """One paragraph per line; consecutive characters share a run per font."""
    doc = Document()
    for line in text.splitlines() or [""]:
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
    parser.add_argument("--pinyin-font", default=PINYIN_FONT)
    parser.add_argument("--plain-font", default=PLAIN_FONT)
    args = parser.parse_args(argv)

    known = load_known_chars(args.data, parse_selections(args.levels))
    text = Path(args.passage).read_text(encoding="utf-8")
    doc = build_document(text, known, args.pinyin_font, args.plain_font)
    Path(args.output).write_bytes(document_bytes(doc))
    print(f"{len(known)} known characters -> {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
