import json
from pathlib import Path

import pytest

from modules.helpers import template_loader


def _write_json(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_sync_campaign_template_updates_fields_and_preserves_custom(tmp_path, monkeypatch):
    entity = "test_entity"
    default_path = tmp_path / "default.json"
    campaign_path = tmp_path / "campaign" / "templates" / f"{entity}_template.json"

    monkeypatch.setattr(template_loader, "_default_template_path", lambda name: str(default_path))
    monkeypatch.setattr(template_loader, "_campaign_template_path", lambda name: str(campaign_path))

    default_payload = {
        "fields": [
            {"name": "id", "type": "text"},
        ],
    }
    _write_json(default_path, default_payload)

    created = template_loader.sync_campaign_template(entity)
    assert created is True
    assert campaign_path.exists()

    # Simulate user-defined custom fields.
    campaign_payload = json.loads(campaign_path.read_text(encoding="utf-8"))
    campaign_payload["custom_fields"] = [{"name": "secret", "type": "text"}]
    _write_json(campaign_path, campaign_payload)

    # Update the default template with a new built-in field.
    default_payload["fields"].append({"name": "title", "type": "text"})
    _write_json(default_path, default_payload)

    updated = template_loader.sync_campaign_template(entity)
    assert updated is True

    refreshed_payload = json.loads(campaign_path.read_text(encoding="utf-8"))
    assert refreshed_payload["fields"] == default_payload["fields"]
    assert refreshed_payload["custom_fields"] == campaign_payload["custom_fields"]


@pytest.mark.parametrize(
    "fields_initial",
    [
        [{"name": "id", "type": "text"}],
        [
            {"name": "id", "type": "text"},
            {"name": "title", "type": "text"},
        ],
    ],
)
def test_sync_campaign_template_no_change_when_fields_match(tmp_path, monkeypatch, fields_initial):
    entity = "test_entity"
    default_path = tmp_path / "default.json"
    campaign_path = tmp_path / "campaign" / "templates" / f"{entity}_template.json"

    monkeypatch.setattr(template_loader, "_default_template_path", lambda name: str(default_path))
    monkeypatch.setattr(template_loader, "_campaign_template_path", lambda name: str(campaign_path))

    default_payload = {"fields": fields_initial}
    _write_json(default_path, default_payload)
    _write_json(campaign_path, {"fields": fields_initial, "custom_fields": [{"name": "c", "type": "text"}]})

    changed = template_loader.sync_campaign_template(entity)
    assert changed is False
    assert json.loads(campaign_path.read_text(encoding="utf-8")) == {
        "fields": fields_initial,
        "custom_fields": [{"name": "c", "type": "text"}],
    }
