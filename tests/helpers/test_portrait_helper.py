from modules.helpers import portrait_helper
from modules.helpers.portrait_helper import parse_portrait_value


def test_parse_portrait_value_accepts_python_style_list_literal():
    assert parse_portrait_value("['No Image']") == ["No Image"]


def test_parse_portrait_value_accepts_json_list():
    assert parse_portrait_value('["portrait.png", "token.png"]') == [
        "portrait.png",
        "token.png",
    ]


def test_parse_portrait_value_keeps_invalid_list_like_text_as_single_value():
    assert parse_portrait_value("[not valid]") == ["[not valid]"]


def test_parse_portrait_value_keeps_no_image_placeholder_without_literal_eval(monkeypatch):
    def fail_parser(value):
        raise AssertionError(f"parser should not be called for {value!r}")

    monkeypatch.setattr(portrait_helper.json, "loads", fail_parser)
    monkeypatch.setattr(portrait_helper.ast, "literal_eval", fail_parser)

    assert parse_portrait_value("[No Image]") == ["[No Image]"]
