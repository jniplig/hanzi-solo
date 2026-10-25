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
    UPLOAD_TYPES,
    apply_exceptions,
    build_document,
    character_levels,
    decode_setup,
    document_bytes,
    encode_setup,
    extract_text,
    hanzi_in,
    is_hanzi,
    load_known_chars,
    load_levels,
    passage_report,
    pinyin_per_character,
    projector_page,
    report_csv,
    worksheet_bundle,
)

SAMPLE = "你好,我是老师。我喜欢吃苹果,也喜欢喝牛奶。\n明天我们去北京。"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
VIEW_STUDENT, VIEW_KEY = "Student copy", "Answer key"

st.set_page_config(page_title="Hanzi Solo", page_icon="字", layout="wide")

STYLE = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Sora:wght@600;700&family=Noto+Serif+SC:wght@400;600&display=swap');
.block-container { padding-top: 4rem; max-width: 1280px; }
.hs-head { display: flex; align-items: center; gap: 14px; padding-bottom: 14px;
  margin-bottom: 14px; border-bottom: 1px solid #E4E0D5; }
.hs-head svg { flex-shrink: 0; }
.hs-head h1.hs-title { font-family: 'Sora', sans-serif; font-weight: 700; font-size: 1.5rem !important;
  line-height: 1.2 !important; margin: 0 !important; padding: 0 !important; }
.hs-tag { font-size: 0.9rem; color: #5A6890; }
.hs-step { display: flex; align-items: center; gap: 10px; margin-bottom: 4px;
  font-family: 'Sora', sans-serif; font-weight: 600; font-size: 1.05rem; }
.hs-num { width: 26px; height: 26px; border-radius: 50%; background: #F2A93B; color: #1A1203;
  font-size: 0.8rem; font-weight: 700; display: inline-flex; align-items: center;
  justify-content: center; }
.hs-muted { font-size: 0.85rem; color: #5A6890; margin: 0.4rem 0 0.3rem; }
.hs-paper { background: #FBFAF6; color: #141A33; border-radius: 6px; padding: 2.2rem 2.6rem 2.6rem;
  box-shadow: 0 18px 44px rgba(20,26,51,0.14), 0 0 0 1px #E4E0D5; margin: 0.4rem 0 0.8rem; }
.hs-paper-label { font-family: 'Sora', sans-serif; font-size: 0.75rem; letter-spacing: 0.08em;
  color: #5A6890; text-transform: uppercase; margin-bottom: 1rem; }
.hs-paper ruby rt { color: #3B4A73; }
.hs-foot { margin-top: 1.5rem; padding-top: 12px; border-top: 1px solid #E4E0D5;
  font-size: 0.8rem; color: #5A6890; }
</style>
"""

LOGO = (
    '<svg width="44" height="44" viewBox="0 0 44 44" role="img" '
    'aria-label="Hanzi Solo logo: the character 字 inside an orbit ring">'
    '<ellipse cx="22" cy="22" rx="20" ry="9" fill="none" stroke="#F2A93B" '
    'stroke-width="1.6" transform="rotate(-24 22 22)"></ellipse>'
    '<circle cx="22" cy="22" r="14" fill="#FFFFFF" stroke="#CFCABB" stroke-width="1.2"></circle>'
    '<text x="22" y="28.5" text-anchor="middle" font-size="18" '
    'font-family="Noto Serif SC, serif" font-weight="600" fill="#141A33">字</text>'
    '<circle cx="38.5" cy="14" r="2.6" fill="#F2A93B"></circle></svg>'
)

st.markdown(STYLE, unsafe_allow_html=True)
st.markdown(
    f'<div class="hs-head">{LOGO}<div><h1 class="hs-title">Hanzi Solo</h1>'
    '<div class="hs-tag">Reading worksheets matched to your students\' levels. '
    "Characters at the chosen levels lose their pinyin; every other character keeps it."
    "</div></div></div>",
    unsafe_allow_html=True,
)


def step(number: int, title: str) -> None:
    st.markdown(
        f'<div class="hs-step"><span class="hs-num">{number}</span>{html.escape(title)}</div>',
        unsafe_allow_html=True,
    )


@st.cache_data
def levels_available():
    return load_levels(DATA_FILE)


@st.cache_data
def level_labels_for(systems: tuple):
    return character_levels(DATA_FILE, list(systems))


def _label(ch: str) -> str:
    return f"{ch}  {pinyin_per_character(ch)[0]}"


def _pick(label: str, key: str, options: set[str], valid, help_text: str) -> str:
    # Saved picks stay (so a class set-up works with any passage) as long as the
    # chosen levels still make them a sensible exception.
    saved = [c for c in st.session_state.get(key, []) if valid(c)]
    st.session_state[key] = saved
    return "".join(
        st.multiselect(
            label, sorted(options | set(saved)), key=key, format_func=_label, help=help_text
        )
    )


levels = levels_available()

# First visit: take the class set-up from the page address, if there is one.
st.session_state.setdefault("lists", ["YCT"] if "YCT" in levels else [])
st.session_state.setdefault("mode", MODE_PINYIN)
st.session_state.setdefault("size_pt", 28)
st.session_state.setdefault("ruby_pt", 12)
st.session_state.setdefault("plain_font", PLAIN_FONT)
st.session_state.setdefault("ruby_font", RUBY_FONT)
if "_setup_loaded" not in st.session_state:
    st.session_state["_setup_loaded"] = True
    saved_setup = decode_setup(dict(st.query_params), levels)
    if "selections" in saved_setup:
        st.session_state["lists"] = list(saved_setup["selections"])
        for system, level in saved_setup["selections"].items():
            st.session_state[f"level_{system}"] = level
    for name in ("show", "hide"):
        if name in saved_setup:
            st.session_state[f"{name}_pinyin"] = list(saved_setup[name])
    for name in ("mode", "size_pt", "ruby_pt", "plain_font", "ruby_font"):
        if name in saved_setup:
            st.session_state[name] = saved_setup[name]
left, right = st.columns([5, 7], gap="large")

# ---- left: the three steps -------------------------------------------------------
with left:
    with st.container(border=True):
        step(1, "Choose levels")
        chosen = st.multiselect(
            "Word lists",
            list(levels),
            key="lists",
            help="HSK3.0 and HSK3.0-2026 level 7 covers bands 7-9.",
        )
        selections = {
            system: st.slider(
                f"{system}: include up to level", 1, levels[system], key=f"level_{system}"
            )
            for system in chosen
        }
        level_known = load_known_chars(DATA_FILE, selections) if selections else set()
        st.markdown(
            f'<div class="hs-muted">{len(level_known)} characters known at these levels</div>',
            unsafe_allow_html=True,
        )

    with st.container(border=True):
        step(2, "Add a passage")
        st.session_state.setdefault("passage", SAMPLE)
        uploaded = st.file_uploader(
            "Upload a passage (optional)",
            type=list(UPLOAD_TYPES),
            help="Word (.docx) or text (.txt). The text appears below, where you can edit it.",
        )
        if uploaded is not None and st.session_state.get("_loaded_file") != uploaded.file_id:
            try:
                text = extract_text(uploaded.name, uploaded.getvalue())
            except ValueError as err:
                st.error(str(err))
            else:
                st.session_state["_loaded_file"] = uploaded.file_id
                if text.strip():
                    st.session_state["passage"] = text
                else:
                    st.warning(
                        "No text found in that file. Scanned pages need to be typed or pasted."
                    )
        passage = st.text_area("Passage", height=180, key="passage")

    hanzi = hanzi_in(passage)
    with st.container(border=True):
        step(3, "Make exceptions")
        show_pinyin = _pick(
            "Always show pinyin for",
            "show_pinyin",
            hanzi & level_known,
            lambda c: c in level_known,
            "Characters the chosen levels would hide, but you want pinyin on.",
        )
        hide_pinyin = _pick(
            "Never show pinyin for",
            "hide_pinyin",
            hanzi - level_known,
            lambda c: c not in level_known,
            "Characters above the chosen levels that your class already knows.",
        )

    pinyin_font, ruby_font, ruby_pt = PINYIN_FONT, RUBY_FONT, 12
    with st.expander("Pinyin and fonts"):
        MODE_LABELS = {
            MODE_PINYIN: "Write the pinyin into the worksheet (no font needed)",
            MODE_FONT: "Use an installed pinyin font such as FZKTPY",
        }
        mode = st.radio("Pinyin", list(MODE_LABELS), format_func=MODE_LABELS.get, key="mode")
        plain_font = st.text_input("Character font", key="plain_font")
        size_pt = st.slider("Character size (pt)", 18, 48, key="size_pt")
        if mode == MODE_PINYIN:
            ruby_font = st.text_input("Pinyin font", key="ruby_font")
            ruby_pt = st.slider("Pinyin size (pt)", 8, 18, key="ruby_pt")
        else:
            pinyin_font = st.text_input("Font that shows pinyin", PINYIN_FONT)

    st.markdown(
        '<div class="hs-muted">This set-up (levels, exceptions, sizes, fonts) is kept in the '
        "page address, never the passage. Bookmark the page to reopen this class.</div>",
        unsafe_allow_html=True,
    )

known = apply_exceptions(level_known, show_pinyin, hide_pinyin)
setup_params = encode_setup(
    selections, show_pinyin, hide_pinyin, mode, size_pt, ruby_pt, plain_font, ruby_font
)
if dict(st.query_params) != setup_params:
    st.query_params.from_dict(setup_params)
options = dict(
    mode=mode,
    pinyin_font=pinyin_font,
    plain_font=plain_font,
    ruby_font=ruby_font,
    size_pt=size_pt,
    ruby_pt=ruby_pt,
)

# ---- right: downloads and preview ------------------------------------------------
with right:
    switched = hanzi & known
    st.caption(
        f"{len(hanzi)} different characters in the passage: "
        f"{len(switched)} without pinyin, {len(hanzi) - len(switched)} with pinyin."
    )

    doc_col, zip_col = st.columns(2)
    with doc_col:
        st.download_button(
            "Worksheet (.docx)",
            data=document_bytes(build_document(passage, known, **options)),
            file_name="worksheet.docx",
            mime=DOCX_MIME,
            use_container_width=True,
        )
    with zip_col:
        st.download_button(
            "Worksheet + answer key (.zip)",
            data=worksheet_bundle(passage, known, **options),
            file_name="worksheet_and_answer_key.zip",
            mime="application/zip",
            type="primary",
            use_container_width=True,
            help="The key is the same passage with pinyin on every character.",
        )

    view = st.radio(
        "Preview", [VIEW_STUDENT, VIEW_KEY], horizontal=True, label_visibility="collapsed"
    )
    shown = known if view == VIEW_STUDENT else set()
    plain_css = html.escape(plain_font)
    rt_style = f"font-size:0.4em;font-family:'{html.escape(ruby_font)}',sans-serif"
    lines = []
    for line in passage.splitlines():
        readings = pinyin_per_character(line) if mode == MODE_PINYIN else [""] * len(line)
        parts = []
        for ch, reading in zip(line, readings):
            if mode == MODE_PINYIN:
                if reading and is_hanzi(ch) and ch not in shown:
                    parts.append(
                        f'<ruby>{html.escape(ch)}<rt style="{rt_style}">'
                        f"{html.escape(reading)}</rt></ruby>"
                    )
                else:
                    parts.append(html.escape(ch))
            elif ch in shown:
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

    label = " · ".join(f"{s} {lvl}" for s, lvl in selections.items())
    st.markdown(
        '<div class="hs-paper">'
        f'<div class="hs-paper-label">Reading practice{" · " + html.escape(label) if label else ""}</div>'
        f'<div style="font-size:2.2rem;line-height:3.6rem;'
        f"font-family:'{plain_css}','Noto Serif SC',serif\">"
        f'{"<br>".join(lines)}</div></div>',
        unsafe_allow_html=True,
    )
    if mode == MODE_PINYIN:
        st.markdown(
            '<div class="hs-muted">Pinyin appears above the characters that are not yet known.</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div class="hs-muted">Shows the fonts only if they are installed on this computer.</div>',
            unsafe_allow_html=True,
        )

    report = passage_report(
        passage, known, level_labels_for(tuple(selections)) if selections else {}
    )
    st.markdown(
        '<div class="hs-step" style="margin-top:1.2rem">Passage report</div>',
        unsafe_allow_html=True,
    )
    if not report["total"]:
        st.markdown(
            '<div class="hs-muted">No Chinese characters in the passage yet.</div>',
            unsafe_allow_html=True,
        )
    else:
        m_text, m_known, m_learn = st.columns(3)
        m_text.metric(
            "Text the class can read",
            f"{report['pct_text']}%",
            help="Share of all the characters in the passage, counting repeats, that are known.",
        )
        m_known.metric(
            "Different characters known", f"{report['known_distinct']} of {report['distinct']}"
        )
        m_learn.metric("Still to learn", report["distinct"] - report["known_distinct"])
        show_known = st.toggle("Show known characters too", key="report_all")
        table = [
            {
                "Character": r["char"],
                "Pinyin": r["pinyin"],
                "Times in passage": r["count"],
                "Status": "Known" if r["known"] else "To learn",
                "First taught at": r["level"] or ("not in these lists" if selections else ""),
            }
            for r in report["rows"]
            if show_known or not r["known"]
        ]
        if table:
            st.dataframe(table, hide_index=True, width="stretch")
        else:
            st.markdown(
                '<div class="hs-muted">Every character is known at these levels.</div>',
                unsafe_allow_html=True,
            )
        st.download_button(
            "Download report (.csv)",
            data=report_csv(report),
            file_name="passage_report.csv",
            mime="text/csv",
        )

    st.markdown(
        '<div class="hs-step" style="margin-top:1.2rem">Present to the class</div>'
        '<div class="hs-muted">Full screen for a projector. Pinyin on unknown '
        "characters stays visible; the space bar reveals the rest.</div>",
        unsafe_allow_html=True,
    )
    st.iframe(projector_page(passage, known, plain_font, ruby_font), height=460)

st.markdown(
    '<div class="hs-foot">Open source, MIT licence. Nothing you paste is stored. '
    "Not affiliated with the publishers of HSK or YCT.</div>",
    unsafe_allow_html=True,
)
