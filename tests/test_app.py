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


def test_setup_is_read_from_the_page_address():
    at = AppTest.from_file(APP, default_timeout=30)
    at.query_params["lists"] = "YCT:3"
    at.query_params["size"] = "36"
    at.run()
    assert not at.exception
    assert at.multiselect[0].value == ["YCT"]
    assert at.slider[0].value == 3
    assert at.slider(key="size_pt").value == 36


def test_exceptions_are_read_from_the_page_address():
    at = AppTest.from_file(APP, default_timeout=30)
    at.query_params["lists"] = "YCT:1"
    at.query_params["hide"] = "京北"
    at.run()
    assert not at.exception
    assert set(at.multiselect(key="hide_pinyin").value) == {"北", "京"}
    # At YCT 1 the sample has three characters with pinyin (也 北 京); two are hidden.
    assert "20 without pinyin, 1 with pinyin" in at.caption[0].value


def test_changes_are_written_back_to_the_address():
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.multiselect[0].set_value(["YCT"]).run()
    at.slider[0].set_value(2).run()
    assert "YCT:2" in str(at.query_params["lists"])


def test_report_shows_what_is_left_to_learn():
    at = AppTest.from_file(APP, default_timeout=30)
    at.query_params["lists"] = "YCT:1"
    at.run()
    assert not at.exception
    metrics = {m.label: m.value for m in at.metric}
    assert metrics["Still to learn"] == "3"  # 也 北 京 in the sample passage
    assert metrics["Text the class can read"].endswith("%")
    # 88% is what a class at YCT 1 can read of the sample; at YCT 4 it is everything.
    assert metrics["Text the class can read"] == "88%"
    at = AppTest.from_file(APP, default_timeout=30)
    at.query_params["lists"] = "YCT:4"
    at.run()
    assert {m.label: m.value for m in at.metric}["Text the class can read"] == "100%"
