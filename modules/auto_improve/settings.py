"""Utilities for auto improve settings."""

from __future__ import annotations

from dataclasses import dataclass

from modules.helpers.config_helper import ConfigHelper


@dataclass
class AutoImproveSettings:
    agent_command: str = "codex exec --input-file {prompt_file}"
    validation_command: str = "python -m pytest tests/test_main_window_update.py -q"
    auto_commit: bool = False
    dry_run: bool = True

    @classmethod
    def load(cls) -> "AutoImproveSettings":
        """Load the operation."""
        return cls(
            agent_command=ConfigHelper.get("AutoImprove", "agent_command", fallback=cls.agent_command),
            validation_command=ConfigHelper.get("AutoImprove", "validation_command", fallback=cls.validation_command),
            auto_commit=ConfigHelper.getboolean("AutoImprove", "auto_commit", fallback=cls.auto_commit),
            dry_run=ConfigHelper.getboolean("AutoImprove", "dry_run", fallback=cls.dry_run),
        )
