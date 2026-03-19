from modules.campaigns.services.campaign_form_mapper import build_form_state_from_campaign


def test_build_form_state_from_campaign_reads_rich_text_and_arcs_payloads():
    payload = {
        "Name": {"text": "Icewind"},
        "Genre": {"text": "Fantasy"},
        "Tone": {"text": "Dark"},
        "Status": {"text": "Running"},
        "StartDate": {"text": "1490 DR"},
        "EndDate": "",
        "Logline": {"text": "Heroes fight endless winter."},
        "Setting": {"text": "The far north."},
        "MainObjective": {"text": "Stop the everlasting rime."},
        "Stakes": {"text": "Entire Ten-Towns survival."},
        "Themes": ["Hope", {"text": "Sacrifice"}],
        "Notes": {"text": "Focus on faction politics."},
        "Arcs": {
            "text": '[{"name": "Auril", "status": "running", "thread": "Frostmaiden", "scenarios": ["Cold Open"]}]'
        },
    }

    form_vars, text_areas, arcs = build_form_state_from_campaign(payload)

    assert form_vars == {
        "name": "Icewind",
        "genre": "Fantasy",
        "tone": "Dark",
        "status": "Running",
        "start_date": "1490 DR",
        "end_date": "",
    }
    assert text_areas["logline"] == "Heroes fight endless winter."
    assert text_areas["themes"] == "Hope\nSacrifice"
    assert arcs == [
        {
            "name": "Auril",
            "summary": "",
            "objective": "",
            "status": "running",
            "thread": "Frostmaiden",
            "scenarios": ["Cold Open"],
        }
    ]
