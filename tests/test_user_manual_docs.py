from __future__ import annotations

from scripts.generate_docs import build_user_manual


def test_user_manual_covers_current_user_facing_workflows() -> None:
    manual = build_user_manual({}, [], [])

    required_content = (
        "Application 1.0.4.22",
        "AI Scenario Generation",
        "Manage Prompts",
        "Generate All Missing",
        "Campaign Validation",
        "Verify Campaign",
        "Campaign Time &amp; Session Tools",
        "Session Timers",
        "Character Creation",
        "Scenario Board",
        "Object Shelf",
        "Fixed overlays",
        "Marker types",
        "Measurements",
        "Audio &amp; Ambiance",
        "Guided Tour",
        "Troubleshooting &amp; Safety",
    )
    for expected in required_content:
        assert expected in manual


def test_user_manual_navigation_targets_existing_sections() -> None:
    manual = build_user_manual({}, [], [])

    for target in (
        "install-and-create-your-first-campaign",
        "build-and-organize-a-campaign",
        "turn-an-idea-into-a-playable-scenario",
        "prepare-a-session-with-the-gm-screen-and-gm-table",
        "present-maps-handouts-and-ambiance",
        "back-up-validate-and-repair-a-campaign",
        "reference-appendix",
    ):
        assert f"href='#{target}'" in manual
        assert f"id='{target}'" in manual

    for target in (
        "getting-started-reference",
        "navigation",
        "systems-data",
        "ai-scenario-generation",
        "portrait-generation",
        "campaign-validation",
        "campaign-time-session-tools",
        "gm-virtual-table",
        "audio-ambiance",
        "guided-tour",
        "troubleshooting-safety",
    ):
        assert f"id='{target}'" in manual

    assert manual.startswith("<!doctype html>")
    assert manual.endswith("</html>\n")
    assert "\n<section>" in manual


def test_user_manual_workflows_have_outcomes_and_checkpoints() -> None:
    manual = build_user_manual({}, [], [])

    assert manual.count("<p><b>Outcome:</b>") == 6
    assert manual.count("class='checkpoint'") == 6
    assert "Screenshot age:" in manual
    assert manual.index("id='install-and-create-your-first-campaign'") < manual.index("id='reference-appendix'")
    assert manual.index("id='reference-appendix'") < manual.index("id='entity-managers'")
