from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).parent.parent / "app.py")


def test_app_runs_without_errors():
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception
    assert at.title[0].value == "Hanzi Solo"


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
    at.text_input(key="show_pinyin").set_value("你").run()  # force pinyin on 你
    assert not at.exception
    assert "1 with pinyin" in at.caption[0].value


def test_clashing_exceptions_show_an_error():
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.text_input(key="show_pinyin").set_value("龙").run()
    at.text_input(key="hide_pinyin").set_value("龙").run()
    assert at.error and "龙" in at.error[0].value
