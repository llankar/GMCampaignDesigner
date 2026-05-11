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
