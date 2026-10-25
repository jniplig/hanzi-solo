"""Streamlit front end for Hanzi Solo."""
import html

import streamlit as st

from hanzi_trainer import (
    PINYIN_FONT,
    PLAIN_FONT,
    build_document,
    document_bytes,
    is_hanzi,
    load_known_chars,
    load_levels,
    DATA_FILE,
)

SAMPLE = "你好,我是老师。我喜欢吃苹果,也喜欢喝牛奶。\n明天我们去北京。"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

st.set_page_config(page_title="Hanzi Solo", page_icon="字")
st.title("Hanzi Solo")
st.write(
    "Characters at the chosen YCT/HSK levels are switched to a plain font, "
    "so they show **no pinyin**. Every other character keeps its pinyin."
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

with st.expander("Fonts"):
    pinyin_font = st.text_input("Font that shows pinyin", PINYIN_FONT)
    plain_font = st.text_input("Font with no pinyin", PLAIN_FONT)

known = load_known_chars(DATA_FILE, selections) if selections else set()
hanzi = {ch for ch in passage if is_hanzi(ch)}
switched = hanzi & known
st.caption(
    f"{len(hanzi)} different characters in the passage: "
    f"{len(switched)} without pinyin, {len(hanzi) - len(switched)} with pinyin."
)

st.subheader("Preview")
st.caption("Shows the fonts only if they are installed on this computer.")
spans = []
for ch in passage:
    if ch == "\n":
        spans.append("<br>")
    elif ch in known:
        spans.append(
            f'<span style="font-family:\'{html.escape(plain_font)}\',serif;'
            f'color:#1a7f37">{html.escape(ch)}</span>'
        )
    else:
        spans.append(
            f'<span style="font-family:\'{html.escape(pinyin_font)}\',serif">'
            f"{html.escape(ch)}</span>"
        )
st.markdown(
    f'<div style="font-size:2rem;line-height:3rem">{"".join(spans)}</div>',
    unsafe_allow_html=True,
)

doc = build_document(passage, known, pinyin_font, plain_font)
st.download_button(
    "Download worksheet (.docx)",
    data=document_bytes(doc),
    file_name="worksheet.docx",
    mime=DOCX_MIME,
)
