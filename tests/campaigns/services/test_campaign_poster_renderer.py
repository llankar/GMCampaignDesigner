"""Tests for static campaign poster renderer."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from modules.campaigns.services.poster_export import PosterTheme, render_campaign_poster
from modules.campaigns.services.poster_export import renderer
from modules.campaigns.ui.graphical_display.data import CampaignGraphArc, CampaignGraphPayload, CampaignGraphScenario


def _sample_payload() -> CampaignGraphPayload:
    return CampaignGraphPayload(
        name="Neon Rain",
        logline="A tangled city conspiracy unravels one lead at a time.",
        genre="Investigation",
        tone="Tense",
        status="In Progress",
        setting="Megacity",
        main_objective="Expose the hidden council.",
        stakes="Citywide unrest.",
        themes="trust, corruption",
        linked_scenario_count=3,
        arcs=[
            CampaignGraphArc(
                name="Arc One",
                status="In Progress",
                summary="",
                objective="",
                scenarios=[
                    CampaignGraphScenario(title="Dockside Clue", summary="Follow a courier.", has_secrets=True),
                    CampaignGraphScenario(title="Rooftop Exchange", summary="Intercept the signal."),
                ],
            )
        ],
    )


def test_render_campaign_poster_creates_png(tmp_path: Path) -> None:
    """Renderer should create a non-empty poster image file."""
    payload = _sample_payload()
    output = tmp_path / "poster.png"

    path = render_campaign_poster(payload, output)

    assert path == output
    assert output.exists()
    assert output.stat().st_size > 0


def test_render_campaign_poster_accepts_custom_theme(tmp_path: Path) -> None:
    """Renderer should accept a custom theme token set."""
    payload = _sample_payload()
    output = tmp_path / "poster_custom.png"
    theme = PosterTheme(
        background="#101010",
        surface="#202020",
        elevated="#303030",
        border="#404040",
        text_primary="#f0f0f0",
        text_secondary="#b0b0b0",
        accent="#ff66cc",
        connector="#666666",
    )

    render_campaign_poster(payload, output, theme=theme)

    assert output.exists()
    assert output.stat().st_size > 0


def test_load_fonts_uses_truetype_chain_when_available(monkeypatch) -> None:
    """Renderer should use a TrueType font chain when one path is available."""
    loaded = {}

    def _fake_truetype(path: str, size: int):
        loaded[size] = path
        return (path, size)

    monkeypatch.setattr(
        renderer,
        "ImageFont",
        SimpleNamespace(truetype=_fake_truetype, load_default=lambda: None),
    )

    title_font, body_font, small_font = renderer._load_fonts(height=1080)

    assert title_font == (loaded[42], 42)
    assert body_font == (loaded[28], 28)
    assert small_font == (loaded[24], 24)


def test_load_fonts_falls_back_to_default_when_truetype_fails(monkeypatch) -> None:
    """Renderer should fallback to Pillow default font if all TrueType loading fails."""
    fallback = object()

    def _raise_missing_font(*_args, **_kwargs):
        raise OSError("missing")

    monkeypatch.setattr(
        renderer,
        "ImageFont",
        SimpleNamespace(truetype=_raise_missing_font, load_default=lambda: fallback),
    )

    title_font, body_font, small_font = renderer._load_fonts(height=1080)

    assert title_font is fallback
    assert body_font is fallback
    assert small_font is fallback
