from modules.campaigns.services.campaign_presets import list_campaign_presets


def test_list_campaign_presets_loads_json_files():
    presets = list_campaign_presets()

    assert len(presets) >= 12

    ids = {preset["id"] for preset in presets}
    assert "high_fantasy_epic" in ids
    assert "noir_investigation" in ids

    fantasy = next(p for p in presets if p["id"] == "high_fantasy_epic")
    assert fantasy["form"]["tone"]
    assert fantasy["text_areas"]["themes"]
    assert fantasy["arcs"]
