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
    automatic_publication: bool = False
    publication_idle_seconds: int = 30
    publication_maximum_seconds: int = 300

    @classmethod
    def load(cls) -> "CampaignUpdatePreferences":
        try:
            hours = int(ConfigHelper.get(SECTION, "frequency_hours", fallback="24") or 24)
        except (TypeError, ValueError):
            hours = 24
        def positive(name: str, default: int) -> int:
            try:
                return max(1, int(ConfigHelper.get(SECTION, name, fallback=str(default)) or default))
            except (TypeError, ValueError):
                return default

        idle = positive("publication_idle_seconds", 30)
        maximum = positive("publication_maximum_seconds", 300)
        return cls(
            automatic_checks=ConfigHelper.getboolean(SECTION, "automatic_checks", fallback=True),
            frequency_hours=max(1, hours),
            automatic_download=ConfigHelper.getboolean(SECTION, "automatic_download", fallback=False),
            offline=ConfigHelper.getboolean(SECTION, "offline", fallback=False),
            automatic_publication=ConfigHelper.getboolean(
                SECTION, "automatic_publication", fallback=False
            ),
            publication_idle_seconds=idle,
            publication_maximum_seconds=max(idle, maximum),
        )

    def save(self) -> None:
        ConfigHelper.set(SECTION, "automatic_checks", str(self.automatic_checks).lower())
        ConfigHelper.set(SECTION, "frequency_hours", self.frequency_hours)
        ConfigHelper.set(SECTION, "automatic_download", str(self.automatic_download).lower())
        ConfigHelper.set(SECTION, "offline", str(self.offline).lower())
        ConfigHelper.set(SECTION, "automatic_publication", str(self.automatic_publication).lower())
        ConfigHelper.set(SECTION, "publication_idle_seconds", max(1, self.publication_idle_seconds))
        ConfigHelper.set(
            SECTION, "publication_maximum_seconds",
            max(self.publication_idle_seconds, self.publication_maximum_seconds),
        )
