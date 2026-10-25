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

## Licence

MIT for the code (see `LICENSE`). Data sources and font notes are in `NOTICE.md`.
HSK and YCT are products of the Center for Language Education and Cooperation;
this project is not affiliated with them.
