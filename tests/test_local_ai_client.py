import sys
import types


# Provide lightweight stubs for optional dependencies that are not
# available in the test environment. The LocalAIClient only needs the
# modules to exist during import for these tests.
sys.modules.setdefault("requests", types.ModuleType("requests"))

from modules.ai.local_ai_client import LocalAIClient


def test_parse_json_safe_markdown_table_fallback():
    text = (
        "Below is a table.\n"
        "| # | Item Name | Category |\n"
        "|---|-----------|----------|\n"
        "| 1 | Sword | Weapons |\n"
        "| 2 | Potion | Miscellaneous |\n"
    )

    result = LocalAIClient._parse_json_safe(text)

    assert isinstance(result, list)
    assert result[0]["Item Name"] == "Sword"
    assert result[1]["Category"] == "Miscellaneous"


def test_parse_markdown_table_ignores_non_tables():
    assert LocalAIClient._parse_markdown_table("No tables here") is None
