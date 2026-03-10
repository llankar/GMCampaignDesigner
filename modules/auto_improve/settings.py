from __future__ import annotations

from dataclasses import dataclass

from modules.helpers.config_helper import ConfigHelper


@dataclass
class AutoImproveSettings:
    agent_command: str = "codex exec --input-file {prompt_file}"
    validation_command: str = "python -m pytest tests/test_main_window_update.py -q"
    branch_prefix: str = "auto-improve"
    auto_commit: bool = False
    dry_run: bool = True

    @classmethod
    def load(cls) -> "AutoImproveSettings":
        return cls(
            agent_command=ConfigHelper.get("AutoImprove", "agent_command", fallback=cls.agent_command),
            validation_command=ConfigHelper.get("AutoImprove", "validation_command", fallback=cls.validation_command),
            branch_prefix=ConfigHelper.get("AutoImprove", "branch_prefix", fallback=cls.branch_prefix),
            auto_commit=ConfigHelper.getboolean("AutoImprove", "auto_commit", fallback=cls.auto_commit),
            dry_run=ConfigHelper.getboolean("AutoImprove", "dry_run", fallback=cls.dry_run),
        )
