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
from docx.enum.text import WD_ALIGN_PARAGRAPH
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


def hanzi_in(text: str) -> set[str]:
    """The distinct Chinese characters in `text` (everything else is ignored)."""
    return {ch for ch in text if is_hanzi(ch)}


def apply_exceptions(
    known: set[str], show_pinyin: str = "", hide_pinyin: str = ""
) -> set[str]:
    """Adjust the known set by hand, in both directions.

    show_pinyin: characters that keep their pinyin even if the level knows them.
    hide_pinyin: characters that lose their pinyin even if the level does not
    know them. A character in both raises ValueError. Non-Chinese characters
    in either string are ignored.
    """
    show, hide = hanzi_in(show_pinyin), hanzi_in(hide_pinyin)
    clash = show & hide
    if clash:
        raise ValueError(
            "In both exception lists: " + "".join(sorted(clash))
        )
    return (known - show) | hide


UPLOAD_TYPES = ("txt", "docx")


def extract_text(filename: str, data: bytes) -> str:
    """Passage text from an uploaded .txt or .docx file.

    .txt may be UTF-8 or GB18030 (common for Chinese files). In .docx, pinyin
    annotations (ruby text) are skipped, so a worksheet made by this tool can
    be uploaded again and gives back only the characters. Raises ValueError
    for an unsupported or unreadable file.
    """
    suffix = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if suffix == "txt":
        for encoding in ("utf-8-sig", "gb18030"):
            try:
                return data.decode(encoding)
            except UnicodeDecodeError:
                continue
        raise ValueError("Could not read the text file's encoding.")
    if suffix == "docx":
        try:
            doc = Document(io.BytesIO(data))
        except Exception as err:
            raise ValueError("Could not open the Word file.") from err
        lines = [
            "".join(p.xpath(".//w:t[not(ancestor::w:rt)]/text()"))
            for p in doc.element.body.iter(qn("w:p"))
        ]
        return "\n".join(lines)
    raise ValueError("Please upload a .txt or .docx file.")


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


def _new_paragraph(doc: Document, line_spacing: float):
    para = doc.add_paragraph()
    if line_spacing != 1.0:
        para.paragraph_format.line_spacing = line_spacing
    return para


def _add_pinyin_paragraph(
    doc: Document,
    line: str,
    known: set[str],
    plain_font: str,
    ruby_font: str,
    size_pt: int,
    ruby_pt: int,
    line_spacing: float = 1.0,
    seen: set[str] | None = None,
) -> None:
    """`seen`, when given, limits pinyin to the first appearance of a character
    (it is updated as characters are annotated)."""
    para = _new_paragraph(doc, line_spacing)
    buffer = ""
    for ch, reading in zip(line, pinyin_per_character(line)):
        if reading and is_hanzi(ch) and ch not in known and not (
            seen is not None and ch in seen
        ):
            if seen is not None:
                seen.add(ch)
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
    line_spacing: float = 1.0,
) -> None:
    """Consecutive characters share one run per font."""
    para = _new_paragraph(doc, line_spacing)
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
    title: str = "",
    name_line: bool = False,
    line_spacing: float = 1.0,
    pinyin_first_only: bool = False,
) -> Document:
    """One paragraph per line of `text`, under an optional title and name/date
    line. `line_spacing` is a multiple (1.0 = single). `pinyin_first_only`
    (pinyin mode) annotates a character only where it first appears."""
    if mode not in (MODE_PINYIN, MODE_FONT):
        raise ValueError(f"Unknown mode '{mode}'")
    if not 0.5 <= line_spacing <= 4:
        raise ValueError("Line spacing must be between 0.5 and 4.")
    doc = Document()
    if title.strip():
        heading = doc.add_paragraph()
        heading.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = heading.add_run(title.strip())
        _set_font(run, plain_font, 20)
        run.bold = True
    if name_line:
        line = doc.add_paragraph()
        _set_font(
            line.add_run("Name: ____________________      Date: ______________"),
            ruby_font,
            12,
        )
    seen: set[str] | None = set() if pinyin_first_only else None
    for line in text.splitlines() or [""]:
        if mode == MODE_PINYIN:
            _add_pinyin_paragraph(
                doc, line, known, plain_font, ruby_font, size_pt, ruby_pt,
                line_spacing, seen,
            )
        else:
            _add_font_paragraph(
                doc, line, known, pinyin_font, plain_font, size_pt, line_spacing
            )
    return doc


def document_bytes(doc: Document) -> bytes:
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def build_answer_key(text: str, **kwargs) -> Document:
    """Teacher copy: the same worksheet with pinyin on every character.

    Takes the same keyword options as build_document (except `known`). It shows
    every pinyin, has no name line, and says "Answer key" in the title.
    """
    kwargs = dict(kwargs, name_line=False, pinyin_first_only=False)
    title = kwargs.get("title", "").strip()
    kwargs["title"] = f"{title} (Answer key)" if title else "Answer key"
    return build_document(text, set(), **kwargs)


_PROJECTOR_CSS = """
*{box-sizing:border-box}
body{margin:0;font-family:Arial,sans-serif}
#stage{background:#fff;color:#111;min-height:100vh;display:flex;flex-direction:column}
.bar{display:flex;gap:8px;flex-wrap:wrap;align-items:center;padding:10px 14px;
  border-bottom:1px solid #ddd;font-size:14px}
.bar button{font:inherit;padding:9px 14px;border:1px solid #bbb;border-radius:8px;
  background:#fafafa;cursor:pointer;min-height:40px}
.bar button:hover{background:#eee}
.bar .hint{color:#555;margin-left:auto}
#text{flex:1;padding:4vmin 6vmin;line-height:2.5;font-family:%(plain)s,"Noto Serif SC",serif}
ruby rt{font-family:%(ruby)s,sans-serif;font-size:.38em;color:#1a2a5c}
ruby rt.k{visibility:hidden}
.reveal ruby rt.k{visibility:visible;color:#6b6b6b}
#stage:fullscreen .bar{opacity:.3}
#stage:fullscreen .bar:hover{opacity:1}
"""

_PROJECTOR_JS = """
const stage=document.getElementById('stage'),text=document.getElementById('text'),
  note=document.getElementById('note'),rv=document.getElementById('rv');
let size=7;
function paint(){text.style.fontSize=size+'vmin'}
function reveal(){const on=stage.classList.toggle('reveal');
  rv.textContent=on?'Hide known pinyin':'Show all pinyin'}
document.getElementById('fs').onclick=()=>{
  if(document.fullscreenElement){document.exitFullscreen();return}
  (stage.requestFullscreen?stage.requestFullscreen():Promise.reject())
    .catch(()=>{note.textContent='This browser blocked full screen. Try F11 instead.'})};
document.getElementById('sm').onclick=()=>{size=Math.max(3,size-1);paint()};
document.getElementById('lg').onclick=()=>{size=Math.min(16,size+1);paint()};
rv.onclick=reveal;
document.addEventListener('keydown',e=>{
  if(e.key===' '){e.preventDefault();reveal()}});
paint();
"""


def _css_font(name: str) -> str:
    """A font name that is safe inside a CSS font-family declaration."""
    cleaned = "".join(c for c in name if c.isalnum() or c in " -_")
    return f'"{cleaned}"' if cleaned else "serif"


def projector_page(
    text: str, known: set[str], plain_font: str = PLAIN_FONT, ruby_font: str = RUBY_FONT
) -> str:
    """A self-contained HTML page for showing the passage on a projector.

    Unknown characters carry pinyin. Known characters carry hidden pinyin that
    a button (or the space bar) reveals. A button opens the page full screen.
    """
    lines = []
    for line in text.splitlines() or [""]:
        parts = []
        for ch, reading in zip(line, pinyin_per_character(line)):
            if reading and is_hanzi(ch):
                cls = ' class="k"' if ch in known else ""
                parts.append(
                    f"<ruby>{escape(ch)}<rt{cls}>{escape(reading)}</rt></ruby>"
                )
            else:
                parts.append(escape(ch))
        lines.append("".join(parts) or "&nbsp;")
    css = _PROJECTOR_CSS % {"plain": _css_font(plain_font), "ruby": _css_font(ruby_font)}
    return (
        '<!doctype html><html lang="zh"><head><meta charset="utf-8">'
        f"<style>{css}</style></head><body>"
        '<div id="stage"><div class="bar">'
        '<button id="fs" type="button">Full screen</button>'
        '<button id="sm" type="button" aria-label="Smaller text">A&minus;</button>'
        '<button id="lg" type="button" aria-label="Larger text">A+</button>'
        '<button id="rv" type="button">Show all pinyin</button>'
        '<span class="hint" id="note">Space shows or hides the known pinyin.</span></div>'
        f'<div id="text">{"<br>".join(lines)}</div></div>'
        f"<script>{_PROJECTOR_JS}</script></body></html>"
    )


def worksheet_bundle(text: str, known: set[str], **kwargs) -> bytes:
    """A zip holding student_worksheet.docx and teacher_answer_key.docx."""
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(
            "student_worksheet.docx",
            document_bytes(build_document(text, known, **kwargs)),
        )
        z.writestr(
            "teacher_answer_key.docx",
            document_bytes(build_answer_key(text, **kwargs)),
        )
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


def character_levels(csv_path: Path | str, systems: list[str]) -> dict[str, str]:
    """{character: "YCT 3"}: the lowest level, across the given word lists,
    of any word that contains the character."""
    best: dict[str, tuple[int, int]] = {}
    with open(csv_path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if row["system"] not in systems:
                continue
            rank = (int(row["level"]), systems.index(row["system"]))
            for ch in row["word"]:
                if is_hanzi(ch) and (ch not in best or rank < best[ch]):
                    best[ch] = rank
    return {ch: f"{systems[s]} {lvl}" for ch, (lvl, s) in best.items()}


def passage_report(
    text: str, known: set[str], levels: dict[str, str] | None = None
) -> dict:
    """What a passage asks of a class: each distinct character in order of first
    appearance with its reading(s), how often it occurs, whether the class knows
    it, and the level that introduces it (from `character_levels`).

    pct_text is the share of all characters in the text that are known (what a
    reader experiences); pct_distinct the share of different characters.
    Percentages are None for a passage with no Chinese characters.
    """
    counts: dict[str, int] = {}
    readings: dict[str, list[str]] = {}
    for line in text.splitlines():
        for ch, reading in zip(line, pinyin_per_character(line)):
            if not is_hanzi(ch):
                continue
            counts[ch] = counts.get(ch, 0) + 1
            seen = readings.setdefault(ch, [])
            if reading and reading not in seen:
                seen.append(reading)
    total = sum(counts.values())
    known_total = sum(n for ch, n in counts.items() if ch in known)
    known_distinct = sum(1 for ch in counts if ch in known)
    rows = [
        {
            "char": ch,
            "pinyin": " / ".join(readings[ch]),
            "count": n,
            "known": ch in known,
            "level": (levels or {}).get(ch, ""),
        }
        for ch, n in counts.items()
    ]
    return {
        "rows": rows,
        "total": total,
        "known_total": known_total,
        "distinct": len(counts),
        "known_distinct": known_distinct,
        "pct_text": round(100 * known_total / total) if total else None,
        "pct_distinct": round(100 * known_distinct / len(counts)) if counts else None,
    }


def report_csv(report: dict) -> bytes:
    """The report as a spreadsheet-friendly CSV (UTF-8 with BOM, opens in Excel)."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Character", "Pinyin", "Times in passage", "Status", "First taught at"])
    for r in report["rows"]:
        writer.writerow(
            [r["char"], r["pinyin"], r["count"], "Known" if r["known"] else "To learn", r["level"]]
        )
    return buf.getvalue().encode("utf-8-sig")


SIZE_RANGE = (18, 48)
RUBY_RANGE = (8, 18)
SPACING_RANGE = (1.0, 2.0)


def encode_setup(
    selections: dict[str, int],
    show: str = "",
    hide: str = "",
    mode: str = MODE_PINYIN,
    size_pt: int = 28,
    ruby_pt: int = 12,
    plain_font: str = PLAIN_FONT,
    ruby_font: str = RUBY_FONT,
    line_spacing: float = 1.0,
    name_line: bool = False,
    first_only: bool = False,
) -> dict[str, str]:
    """A class set-up as short URL query parameters (settings left at their
    default are left out). The passage is deliberately not part of it."""
    params = {"lists": ",".join(f"{s}:{n}" for s, n in selections.items()) or "-"}
    for name, chars in (("show", show), ("hide", hide)):
        chars = "".join(sorted(hanzi_in(chars)))
        if chars:
            params[name] = chars
    for name, value, default in (
        ("mode", mode, MODE_PINYIN),
        ("size", size_pt, 28),
        ("psize", ruby_pt, 12),
        ("cfont", plain_font, PLAIN_FONT),
        ("rfont", ruby_font, RUBY_FONT),
    ):
        if value != default:
            params[name] = str(value)
    if line_spacing != 1.0:
        params["spacing"] = f"{line_spacing:g}"
    if name_line:
        params["nameline"] = "1"
    if first_only:
        params["first"] = "1"
    return params


def _bounded_int(text: str, low: int, high: int) -> int | None:
    return min(max(int(text), low), high) if text.strip().isdigit() else None


def decode_setup(params: dict[str, str], levels: dict[str, int]) -> dict:
    """The valid parts of a set-up from URL parameters; anything unknown,
    malformed or out of range is ignored. `levels` is {system: top level}."""
    out: dict = {}
    if "lists" in params:
        selections: dict[str, int] = {}
        for part in params["lists"].split(","):
            system, _, level = part.partition(":")
            level_n = _bounded_int(level, 1, levels.get(system, 0)) if system in levels else None
            if level_n is not None:
                selections[system] = level_n
        if selections or params["lists"].strip() == "-":
            out["selections"] = selections
    for name in ("show", "hide"):
        if name in params:
            out[name] = "".join(sorted(hanzi_in(params[name])))
    if params.get("mode") in (MODE_PINYIN, MODE_FONT):
        out["mode"] = params["mode"]
    for name, key, (low, high) in (("size", "size_pt", SIZE_RANGE), ("psize", "ruby_pt", RUBY_RANGE)):
        value = _bounded_int(params.get(name, ""), low, high)
        if value is not None:
            out[key] = value
    try:
        spacing = float(params.get("spacing", ""))
    except ValueError:
        spacing = None
    if spacing is not None and spacing == spacing:  # not NaN
        out["line_spacing"] = round(min(max(spacing, SPACING_RANGE[0]), SPACING_RANGE[1]), 2)
    for name, key in (("nameline", "name_line"), ("first", "first_only")):
        if params.get(name) == "1":
            out[key] = True
    for name, key in (("cfont", "plain_font"), ("rfont", "ruby_font")):
        font = params.get(name, "").strip()[:60]
        if font:
            out[key] = font
    return out


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
    parser.add_argument(
        "--show-pinyin", default="", help="characters that keep pinyin despite the level"
    )
    parser.add_argument(
        "--hide-pinyin", default="", help="characters that lose pinyin despite the level"
    )
    parser.add_argument(
        "--answer-key", metavar="FILE", help="also write a teacher copy with all pinyin"
    )
    parser.add_argument("--title", default="", help="heading at the top of the worksheet")
    parser.add_argument("--name-line", action="store_true", help="add a Name / Date line")
    parser.add_argument(
        "--line-spacing", type=float, default=1.0, help="multiple of single spacing (default 1.0)"
    )
    parser.add_argument(
        "--first-only",
        action="store_true",
        help="pinyin mode: annotate a character only where it first appears",
    )
    args = parser.parse_args(argv)

    known = load_known_chars(args.data, parse_selections(args.levels))
    known = apply_exceptions(known, args.show_pinyin, args.hide_pinyin)
    text = Path(args.passage).read_text(encoding="utf-8")
    options = dict(
        mode=args.mode,
        pinyin_font=args.pinyin_font,
        plain_font=args.plain_font,
        ruby_font=args.ruby_font,
        title=args.title,
        name_line=args.name_line,
        line_spacing=args.line_spacing,
        pinyin_first_only=args.first_only,
    )
    Path(args.output).write_bytes(
        document_bytes(build_document(text, known, **options))
    )
    print(f"{len(known)} known characters -> {args.output}")
    if args.answer_key:
        Path(args.answer_key).write_bytes(
            document_bytes(build_answer_key(text, **options))
        )
        print(f"answer key -> {args.answer_key}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
