"""Tests for chatbot book excerpt collection."""

from __future__ import annotations

from typing import Any

import pytest


class _DummyCTkModule:
    class CTkToplevel:
        def __init__(self, *args: Any, **kwargs: Any) -> None:  # pragma: no cover - simple stub
            pass

    def __getattr__(self, name: str):  # pragma: no cover - simple stub
        return type(name, (), {"__init__": lambda self, *args, **kwargs: None})


import sys

sys.modules.setdefault("customtkinter", _DummyCTkModule())
sys.modules.setdefault("pypdf", type("_DummyPdfModule", (), {"PdfReader": object}))

from modules.ui import chatbot_dialog


@pytest.mark.parametrize(
    "record, expected_label",
    [
        (
            {
                "ExtractedPages": [
                    {
                        "Path": "assets/books/excerpt.pdf",
                        "Label": "Excerpt Label",
                    }
                ]
            },
            "Excerpt Label",
        ),
        (
            {
                "ExtractedPages": [
                    {
                        "path": "assets/books/another_excerpt.pdf",
                        "StartPage": 5,
                        "EndPage": 6,
                    }
                ]
            },
            "Pages 5-6",
        ),
    ],
)
def test_collect_book_excerpts_uses_path(monkeypatch: pytest.MonkeyPatch, record: dict[str, Any], expected_label: str) -> None:
    calls: list[str] = []

    def fake_extract(path: str) -> str:
        calls.append(path)
        return "The wandering wizard uncovers hidden lore."  # contains query word

    monkeypatch.setattr(chatbot_dialog, "_extract_text_from_pdf", fake_extract)

    excerpts = chatbot_dialog._collect_book_excerpts(record, "wizard")

    assert calls, "Expected the path-based extractor to be invoked."
    assert len(calls) == 1, "Extractor should cache results for identical paths."
    assert excerpts, "Expected excerpts to be returned for path-only entries."

    labels = {label for label, _ in excerpts}
    assert expected_label in labels

    matching = [value for label, value in excerpts if label == expected_label]
    assert matching and matching[0].text
    assert "wizard" in matching[0].text.lower()
