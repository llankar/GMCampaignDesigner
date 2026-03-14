from modules.scenarios.gm_screen.dashboard.session_prep import build_session_brief_payload


def test_build_session_brief_payload_collects_expected_sections():
    fields = [
        {"name": "Summary", "type": "longtext", "value": "The city is on edge."},
        {
            "name": "Arcs",
            "type": "longtext",
            "value": [
                {"name": "Arc Alpha", "status": "In Progress", "objective": "Find the traitor"},
                {"name": "Arc Beta", "status": "Planned", "objective": "Prepare defenses"},
            ],
        },
        {"name": "CriticalNPCs", "type": "list", "values": ["Marshal Kora"]},
    ]
    campaign_item = {"LinkedScenarios": ["Opening Gambit", "Opening Gambit", "Siege at Dawn"]}

    payload = build_session_brief_payload(fields=fields, campaign_item=campaign_item)

    assert payload.summary == "The city is on edge."
    assert payload.active_arcs == ["Arc Alpha — Find the traitor"]
    assert payload.linked_scenarios == ["Opening Gambit", "Siege at Dawn"]
    assert payload.gm_priority_notes == ["Marshal Kora"]
