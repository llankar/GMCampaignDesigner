#!/usr/bin/env python3
"""Synchronize campaign template JSON files with module templates."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULES_DIR = REPO_ROOT / "modules"
CAMPAIGNS_DIR = REPO_ROOT / "Campaigns"


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def dump_json(path: Path, data: dict) -> None:
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")


def get_module_templates() -> Dict[str, dict]:
    templates: Dict[str, dict] = {}
    for module_dir in MODULES_DIR.iterdir():
        if not module_dir.is_dir():
            continue
        template_path = module_dir / f"{module_dir.name}_template.json"
        if template_path.exists():
            templates[module_dir.name] = load_json(template_path)
    return templates


def update_campaign_templates() -> Dict[Path, bool]:
    module_templates = get_module_templates()
    updates: Dict[Path, bool] = {}

    for campaign_dir in CAMPAIGNS_DIR.iterdir():
        if not campaign_dir.is_dir():
            continue
        templates_dir = campaign_dir / "templates"
        if not templates_dir.exists():
            continue

        for module_name, template_data in module_templates.items():
            template_filename = f"{module_name}_template.json"
            campaign_template_path = templates_dir / template_filename
            if not campaign_template_path.exists():
                continue

            current_data = load_json(campaign_template_path)
            if current_data != template_data:
                dump_json(campaign_template_path, template_data)
                updates[campaign_template_path] = True
            else:
                updates.setdefault(campaign_template_path, False)
    return updates


def main() -> None:
    updates = update_campaign_templates()
    if not updates:
        print("No campaign templates found to update.")
        return

    updated = [path for path, changed in updates.items() if changed]
    if updated:
        print("Updated the following campaign templates:")
        for path in sorted(updated):
            print(f" - {path.relative_to(REPO_ROOT)}")
    else:
        print("All campaign templates are already up to date.")


if __name__ == "__main__":
    main()
