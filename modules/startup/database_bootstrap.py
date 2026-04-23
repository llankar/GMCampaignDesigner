"""Startup helpers that ensure a valid campaign database is configured."""

from __future__ import annotations

import sqlite3
import tkinter as tk
from pathlib import Path

from modules.campaigns.services import (
    ensure_campaign_directory,
    normalize_campaign_db_path,
    seed_default_templates,
)
from modules.helpers.config_helper import ConfigHelper
from modules.helpers.logging_helper import log_exception, log_info, log_module_import
from modules.ui.database_manager_dialog import DatabaseManagerDialog

log_module_import(__name__)


def ensure_database_configured_for_startup() -> bool:
    """Ensure startup can reach a campaign database, prompting the user if needed."""
    current_path = ConfigHelper.get("Database", "path", fallback="") or ""

    if _is_database_path_usable(current_path):
        return True

    selection = _prompt_database_selection(current_path)
    if selection is None:
        log_info(
            "Startup database selection cancelled by user.",
            func_name="database_bootstrap.ensure_database_configured_for_startup",
        )
        return False

    selected_path, is_new_database = selection
    normalized_path = normalize_campaign_db_path(selected_path)
    normalized_path = ensure_campaign_directory(normalized_path)
    ConfigHelper.set("Database", "path", normalized_path)

    if is_new_database:
        try:
            seed_default_templates(normalized_path)
        except Exception:
            log_exception(
                "Failed to seed default templates during startup database bootstrap.",
                func_name="database_bootstrap.ensure_database_configured_for_startup",
            )

    return True


def _is_database_path_usable(path: str) -> bool:
    """Return whether ``path`` can be opened by sqlite."""
    normalized_path = str(path or "").strip()
    if not normalized_path:
        return False

    normalized_path = normalize_campaign_db_path(normalized_path)
    try:
        with sqlite3.connect(normalized_path):
            pass
    except sqlite3.OperationalError:
        return False
    except Exception:
        return False

    return True


def _prompt_database_selection(current_path: str):
    """Open the database selector dialog and return the chosen path and creation flag."""
    root = tk.Tk()
    root.withdraw()

    selection = {"value": None}

    def _on_selected(path: str, is_new: bool) -> None:
        selection["value"] = (path, is_new)

    dialog = DatabaseManagerDialog(
        root,
        current_path=current_path or None,
        on_selected=_on_selected,
        on_cancelled=lambda: None,
    )

    root.wait_window(dialog)
    root.destroy()

    return selection["value"]
