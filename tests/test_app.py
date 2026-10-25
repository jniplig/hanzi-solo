from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).parent.parent / "app.py")


def test_app_runs_without_errors():
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception
    assert "<h1 class=\"hs-title\">Hanzi Solo</h1>" in at.markdown[1].value


def test_level_selection_changes_caption():
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.multiselect[0].set_value(["YCT"]).run()
    at.slider[0].set_value(4).run()
    assert not at.exception
    # The sample passage is within YCT 4, so every character loses its pinyin.
    assert "0 with pinyin" in at.caption[0].value


def test_both_modes_run_without_errors():
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert at.radio[0].value == "pinyin"  # the no-font mode is the default
    at.radio[0].set_value("font").run()
    assert not at.exception
    at.radio[0].set_value("pinyin").run()
    assert not at.exception


def test_no_selection_keeps_pinyin_everywhere():
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.multiselect[0].set_value([]).run()
    assert not at.exception
    assert "0 without pinyin" in at.caption[0].value


def test_exceptions_change_the_caption():
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.multiselect[0].set_value(["YCT"]).run()
    at.slider[0].set_value(4).run()
    assert "0 with pinyin" in at.caption[0].value
    # 你 is known at this level, so it is offered under "Always show pinyin".
    at.multiselect(key="show_pinyin").set_value(["你"]).run()
    assert not at.exception
    assert "1 with pinyin" in at.caption[0].value


def test_hide_list_offers_unknown_characters_and_applies_them():
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.multiselect[0].set_value([]).run()  # nothing known yet
    assert "你  nǐ" in at.multiselect(key="hide_pinyin").options
    at.multiselect(key="hide_pinyin").set_value(["你"]).run()
    assert not at.exception
    assert "1 without pinyin" in at.caption[0].value


def test_stale_picks_are_dropped_when_levels_change():
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.multiselect[0].set_value([]).run()
    at.multiselect(key="hide_pinyin").set_value(["你"]).run()
    at.multiselect[0].set_value(["YCT"]).run()  # 你 is now known, not offered
    at.slider[0].set_value(4).run()
    assert not at.exception
    assert at.multiselect(key="hide_pinyin").value == []
