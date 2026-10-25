"""Streamlit front end for Hanzi Solo."""
import html

import streamlit as st

from hanzi_trainer import (
    DATA_FILE,
    MODE_FONT,
    MODE_PINYIN,
    PINYIN_FONT,
    PLAIN_FONT,
    RUBY_FONT,
    apply_exceptions,
    build_document,
    document_bytes,
    hanzi_in,
    is_hanzi,
    load_known_chars,
    load_levels,
    pinyin_per_character,
    worksheet_bundle,
)

SAMPLE = "你好,我是老师。我喜欢吃苹果,也喜欢喝牛奶。\n明天我们去北京。"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

st.set_page_config(page_title="Hanzi Solo", page_icon="字")
st.title("Hanzi Solo")
st.write(
    "Characters at the chosen YCT/HSK levels are written plainly, with "
    "**no pinyin**. Every other character shows its pinyin."
)


@st.cache_data
def levels_available():
    return load_levels(DATA_FILE)


levels = levels_available()
chosen = st.multiselect(
    "Word lists",
    list(levels),
    default=["YCT"] if "YCT" in levels else [],
    help="HSK3.0 and HSK3.0-2026 level 7 covers bands 7-9.",
)
selections = {
    system: st.slider(f"{system}: include up to level", 1, levels[system], 1)
    for system in chosen
}

passage = st.text_area("Passage", value=SAMPLE, height=180)

MODE_LABELS = {
    MODE_PINYIN: "Write the pinyin into the worksheet (no font needed)",
    MODE_FONT: "Use an installed pinyin font such as FZKTPY",
}
mode = st.radio("Pinyin", list(MODE_LABELS), format_func=MODE_LABELS.get)

pinyin_font, ruby_font, ruby_pt = PINYIN_FONT, RUBY_FONT, 12
with st.expander("Fonts and sizes"):
    plain_font = st.text_input("Character font", PLAIN_FONT)
    size_pt = st.slider("Character size (pt)", 18, 48, 28)
    if mode == MODE_PINYIN:
        ruby_font = st.text_input("Pinyin font", RUBY_FONT)
        ruby_pt = st.slider("Pinyin size (pt)", 8, 18, 12)
    else:
        pinyin_font = st.text_input("Font that shows pinyin", PINYIN_FONT)

hanzi = hanzi_in(passage)
level_known = load_known_chars(DATA_FILE, selections) if selections else set()


def _label(ch: str) -> str:
    return f"{ch}  {pinyin_per_character(ch)[0]}"


def _pick(label: str, key: str, options: list[str], help_text: str) -> str:
    # Drop earlier picks that are no longer on offer (passage or level changed).
    st.session_state[key] = [c for c in st.session_state.get(key, []) if c in options]
    return "".join(
        st.multiselect(label, options, key=key, format_func=_label, help=help_text)
    )


with st.expander("Exceptions: pick characters by hand"):
    show_pinyin = _pick(
        "Always show pinyin for",
        "show_pinyin",
        sorted(hanzi & level_known),
        "Characters the chosen levels would hide, but you want pinyin on.",
    )
    hide_pinyin = _pick(
        "Never show pinyin for",
        "hide_pinyin",
        sorted(hanzi - level_known),
        "Characters above the chosen levels that your class already knows.",
    )

known = apply_exceptions(level_known, show_pinyin, hide_pinyin)
switched = hanzi & known
st.caption(
    f"{len(hanzi)} different characters in the passage: "
    f"{len(switched)} without pinyin, {len(hanzi) - len(switched)} with pinyin."
)

st.subheader("Preview")
if mode == MODE_PINYIN:
    st.caption("Pinyin appears above the characters that are not yet known.")
else:
    st.caption("Shows the fonts only if they are installed on this computer.")

plain_css = html.escape(plain_font)
rt_style = f"font-size:0.4em;font-family:'{html.escape(ruby_font)}',sans-serif"
lines = []
for line in passage.splitlines():
    readings = pinyin_per_character(line) if mode == MODE_PINYIN else [""] * len(line)
    parts = []
    for ch, reading in zip(line, readings):
        if mode == MODE_PINYIN:
            if reading and is_hanzi(ch) and ch not in known:
                parts.append(
                    f'<ruby>{html.escape(ch)}<rt style="{rt_style}">'
                    f"{html.escape(reading)}</rt></ruby>"
                )
            else:
                parts.append(html.escape(ch))
        elif ch in known:
            parts.append(
                f'<span style="font-family:\'{plain_css}\',serif;'
                f'color:#1a7f37">{html.escape(ch)}</span>'
            )
        else:
            parts.append(
                f'<span style="font-family:\'{html.escape(pinyin_font)}\',serif">'
                f"{html.escape(ch)}</span>"
            )
    lines.append("".join(parts))
st.markdown(
    f'<div style="font-size:2rem;line-height:3.6rem;font-family:\'{plain_css}\',serif">'
    f'{"<br>".join(lines)}</div>',
    unsafe_allow_html=True,
)

options = dict(
    mode=mode,
    pinyin_font=pinyin_font,
    plain_font=plain_font,
    ruby_font=ruby_font,
    size_pt=size_pt,
    ruby_pt=ruby_pt,
)
st.caption(
    "The zip holds the student worksheet and a teacher answer key: "
    "the same passage with pinyin on every character."
)
st.download_button(
    "Download worksheet (.docx)",
    data=document_bytes(build_document(passage, known, **options)),
    file_name="worksheet.docx",
    mime=DOCX_MIME,
)
st.download_button(
    "Download student worksheet + teacher answer key (.zip)",
    data=worksheet_bundle(passage, known, **options),
    file_name="worksheet_and_answer_key.zip",
    mime="application/zip",
)
