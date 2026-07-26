"""Application configuration adapter for campaign update checks."""

from __future__ import annotations

from dataclasses import dataclass

from modules.helpers.config_helper import ConfigHelper


SECTION = "CampaignUpdates"


@dataclass(frozen=True)
class CampaignUpdatePreferences:
    automatic_checks: bool = True
    frequency_hours: int = 24
    automatic_download: bool = False
    offline: bool = False

    @classmethod
    def load(cls) -> "CampaignUpdatePreferences":
        try:
            hours = int(ConfigHelper.get(SECTION, "frequency_hours", fallback="24") or 24)
        except (TypeError, ValueError):
            hours = 24
        return cls(
            automatic_checks=ConfigHelper.getboolean(SECTION, "automatic_checks", fallback=True),
            frequency_hours=max(1, hours),
            automatic_download=ConfigHelper.getboolean(SECTION, "automatic_download", fallback=False),
            offline=ConfigHelper.getboolean(SECTION, "offline", fallback=False),
        )

    def save(self) -> None:
        ConfigHelper.set(SECTION, "automatic_checks", str(self.automatic_checks).lower())
        ConfigHelper.set(SECTION, "frequency_hours", self.frequency_hours)
        ConfigHelper.set(SECTION, "automatic_download", str(self.automatic_download).lower())
        ConfigHelper.set(SECTION, "offline", str(self.offline).lower())

