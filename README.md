# Hanzi Solo

A reading-practice tool for Chinese characters. A teacher picks a YCT and/or HSK
level and pastes a passage. Every character at or below that level is switched
to a plain font, so it shows **no pinyin**. All other characters stay in a font
that draws pinyin above them. The result is a Word worksheet.

## How it works

There are two ways to show pinyin, chosen with the "Pinyin" option in the app
or `--mode` on the command line:

- **pinyin (default):** the program works out the pinyin itself with
  [pypinyin](https://github.com/mozillazg/python-pinyin) and writes it into the
  `.docx` as Word's own pinyin annotation (ruby text) above each character that
  is not yet known. No special font is needed. Readings take the surrounding word
  into account (银行 is yín háng, 长大 is zhǎng dà). Tone changes in speech, such
  as nǐ hǎo being said ní hǎo, are not applied, matching printed textbooks.
- **font:** unknown characters use a pinyin font such as FZKTPY and known
  characters switch to a plain font. This only works where that font is
  installed, and characters typed into the worksheet later also get pinyin.

**Try it online:** https://7enwlsu582hhgidpovckm3.streamlit.app/ (free, nothing is stored).

## Quick start

```bash
git clone <this repository>
cd hanzi-solo
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Or from the command line (levels are "up to and including"):

```bash
python hanzi_trainer.py "YCT=3,HSK3.0=1" passage.txt -o worksheet.docx
python hanzi_trainer.py "YCT=3" passage.txt --mode font   # needs a pinyin font
```

Exceptions and a teacher copy (also in the app under "Exceptions"):

```bash
python hanzi_trainer.py "YCT=3" passage.txt \
    --show-pinyin 你 --hide-pinyin 龙 --answer-key key.docx
```

`--show-pinyin` keeps pinyin on characters the level would hide;
`--hide-pinyin` removes it from characters the level would show. The answer key
is the same passage with pinyin on every character. In the app, one button
downloads the student worksheet and the answer key together as a zip.

## Worksheet layout

Under "Worksheet layout" in the app (or with command-line flags) you can add a
title, a Name and Date line, wider line spacing (1 to 2 times), and, in pinyin
mode, show pinyin only where a character first appears so repeats read clean.
The answer key always shows pinyin on every character, has no Name line, and
adds "(Answer key)" to the title. Spacing, the Name line and first-appearance
mode are kept in the class set-up link; the title is not, because it belongs to
one lesson.

```bash
python hanzi_trainer.py "YCT=3" passage.txt --title "Lesson 1" --name-line \
    --line-spacing 1.5 --first-only
```

## Uploading a passage

In the app, upload a Word (`.docx`) or text (`.txt`) file instead of pasting. The
text lands in the passage box, where you can still edit it. Pinyin already in a
Word file is ignored, so a worksheet made by this tool can be uploaded again.
Text files may be UTF-8 or GB18030. PDFs are not supported, because text pulled
out of a PDF is unreliable; scanned pages need to be typed or pasted. Uploads
are limited to 5 MB and are not stored.

## Passage report (off by default)

This is a niche feature, so the app hides it. Set the environment variable
`HANZI_SOLO_REPORT=1` before `streamlit run app.py` to show it. When on, it
sits under the preview and the report shows how much of the passage the class can read
(counting every character, repeats included), how many different characters are
known, and a table of the characters still to learn: pinyin (every reading, for
characters like 行), how many times each appears, and the level that first
teaches it. A toggle adds the known characters, and the table downloads as a CSV
that opens in Excel.

## Class set-ups

The page address always holds the current set-up: word lists and levels,
exceptions, pinyin mode, sizes and fonts. Bookmark the page to reopen a class
exactly as you left it, or send the link to a colleague. The passage is never in
the address, so a link carries no lesson text or student material. Exceptions
stay with the class when you change passages, as long as the chosen levels still
make them sensible.

## Presenting in class

Under the preview, "Present to the class" shows the passage in large type for a
projector. Press **Full screen** (Esc leaves it), change the size with **A-**
and **A+**, and press **Space** or "Show all pinyin" to reveal the pinyin on the
characters the class is expected to know. It uses the same levels and exceptions
as the worksheet.

## Fonts

In the default pinyin mode no font needs installing. The worksheet names two
fonts that every Windows computer has, and you can change them:

- **KaiTi** for the characters (`--plain-font`; on a Mac try `Kaiti SC`).
- **Arial** for the pinyin letters and tone marks (`--ruby-font`). Choose a font
  that includes the marks ā á ǎ à.

If a named font is missing, Word substitutes another one and the worksheet is
still readable.

**FZKTPY** (font mode only) is proprietary and is not included. Install your own
licensed copy on every computer that opens the worksheet.

Test a worksheet in the Word you will actually use. Word for the web may display
pinyin annotations differently from desktop Word.

## Word lists

`data/levels.csv` has one row per word and system, listing the word at the level
where it is first introduced. Choosing "up to level N" includes levels 1 to N.

| System | Levels | Notes |
|---|---|---|
| `YCT` | 1-4 | Compiled from the published YCT outline |
| `HSK2.0` | 1-6 | Original HSK |
| `HSK3.0` | 1-7 | 2021 standard; level 7 is bands 7-9 |
| `HSK3.0-2026` | 1-7 | The 2026 update, as labelled "newest" upstream |

Check which standard your students follow. The lists are working data, not an
official publication, so verify them against the official syllabi. To rebuild
the CSV, see `scripts/build_levels.py` (it expects a clone of
[complete-hsk-vocabulary](https://github.com/drkameleon/complete-hsk-vocabulary)
and the files in `data/sources/`).

## Privacy

The app processes the pasted passage in memory and stores nothing. Do not paste
student names or other personal data into a shared, hosted copy.

## Development

```bash
pip install -r requirements-dev.txt
pytest
```

## Deploying

The app is a plain Streamlit app with `app.py` as the entry point, so it can run
on Streamlit Community Cloud straight from a GitHub repository.

Each push to `main` redeploys automatically. `app.py` reloads `hanzi_trainer.py`
on every run, so a deploy that changes both files cannot leave the app stuck on
an old copy of the module. If the app ever shows an error after a deploy that a
refresh does not clear, use "Manage app" then "Reboot app" on Streamlit.

## Licence

MIT for the code (see `LICENSE`). Data sources and font notes are in `NOTICE.md`.
HSK and YCT are products of the Center for Language Education and Cooperation;
this project is not affiliated with them.
