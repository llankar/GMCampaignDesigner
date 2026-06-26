"""Tests for GM Table reveal helpers."""

import tkinter as tk

from modules.scenarios.gm_table.reveal import service
from modules.scenarios.gm_table.reveal.service import (
    _format_reveal_value,
    _player_safe_sections,
    reveal_entity,
)


def test_player_safe_sections_omit_nested_gm_only_fields():
    item = {
        "Name": "Public Name",
        "Description": "Visible description",
        "GM Notes": "Do not reveal",
        "Details": {
            "Public clue": "A silver key",
            "Secret Answer": "Behind the statue",
        },
    }

    sections = dict(_player_safe_sections(item))

    assert sections == {
        "Name": "Public Name",
        "Description": "Visible description",
        "Details": "Public clue: A silver key",
    }


def test_format_reveal_value_handles_python_literal_rich_text_strings():
    payload = "{'text': 'Intro line\\nSecond line', 'formatting': {'bold': []}}"

    assert _format_reveal_value(payload) == "Intro line\nSecond line"


def test_reveal_entity_returns_failure_when_monitor_detection_needs_display(monkeypatch):
    def raise_tcl_error():
        raise tk.TclError("no display name and no $DISPLAY environment variable")

    monkeypatch.setattr(service, "_get_monitors", raise_tcl_error)
    monkeypatch.setattr(service.messagebox, "showinfo", lambda *_args, **_kwargs: raise_tcl_error())

    result = reveal_entity("npc", {"Name": "Ada", "Description": "Visible"})

    assert result.ok is False
    assert result.message == "No player display is available for this reveal."


def test_reveal_entity_returns_failure_when_text_window_creation_needs_display(monkeypatch):
    def raise_tcl_error(*_args, **_kwargs):
        raise tk.TclError("couldn't connect to display")

    monkeypatch.setattr(service, "_get_monitors", lambda: [(0, 0, 1280, 720)])
    monkeypatch.setattr(service.ctk, "CTkToplevel", raise_tcl_error)
    monkeypatch.setattr(service.messagebox, "showinfo", lambda *_args, **_kwargs: None)

    result = reveal_entity("npc", {"Name": "Ada", "Description": "Visible"})

    assert result.ok is False
    assert result.message == "No player display is available for this reveal."
