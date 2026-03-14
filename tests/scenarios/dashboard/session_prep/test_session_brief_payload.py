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
    assert payload.arc_details == [
        "Arc 1: Arc Alpha | status: In Progress | objective: Find the traitor",
        "Arc 2: Arc Beta | status: Planned | objective: Prepare defenses",
    ]
    assert payload.dashboard_fields == [
        "Summary: The city is on edge.",
        "Arcs: {'name': 'Arc Alpha', 'status': 'In Progress', 'objective': 'Find the traitor'} | {'name': 'Arc Beta', 'status': 'Planned', 'objective': 'Prepare defenses'}",
        "CriticalNPCs: Marshal Kora",
    ]
    assert payload.gm_priority_notes == ["Marshal Kora"]
