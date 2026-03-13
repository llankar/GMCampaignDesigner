import pytest

from modules.campaigns.services.campaign_payload_builder import build_campaign_payload


def test_build_campaign_payload_embeds_arcs_and_linked_scenarios():
    payload = build_campaign_payload(
        form_data={
            "name": "The Shattered Crown",
            "genre": "Fantasy",
            "status": "Running",
            "themes": "Power\nCorruption\nHope",
        },
        arcs_data=[
            {
                "name": "Arc One",
                "summary": "Setup",
                "objective": "Gather allies",
                "status": "Running",
                "scenarios": ["The Fallen Keep", "Court of Ash"],
            },
            {
                "name": "Arc Two",
                "scenarios": "Court of Ash, Throne of Glass",
            },
        ],
    )

    assert payload["Name"] == "The Shattered Crown"
    assert payload["Status"] == "Running"
    assert payload["Themes"] == ["Power", "Corruption", "Hope"]
    assert len(payload["Arcs"]) == 2
    assert payload["Arcs"][0]["name"] == "Arc One"
    assert payload["Arcs"][1]["scenarios"] == ["Court of Ash", "Throne of Glass"]
    assert payload["LinkedScenarios"] == ["The Fallen Keep", "Court of Ash", "Throne of Glass"]


def test_build_campaign_payload_requires_name():
    with pytest.raises(ValueError):
        build_campaign_payload(form_data={"name": "  "}, arcs_data=[])
