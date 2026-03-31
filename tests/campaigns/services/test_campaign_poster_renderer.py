"""Tests for static campaign poster renderer."""
from __future__ import annotations

from pathlib import Path

from modules.campaigns.services.poster_export import PosterTheme, render_campaign_poster
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
