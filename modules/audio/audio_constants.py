"""Shared constants for audio UI components."""

from __future__ import annotations

from typing import Final

from modules.helpers.logging_helper import log_module_import

log_module_import(__name__)

# Mapping of audio sections to human readable titles.  Keep the keys in sync with
# the configuration stored by :class:`AudioLibrary`.
SECTION_TITLES: Final[dict[str, str]] = {
    "music": "Music",
    "effects": "Sound Effects",
}

# Default section used by small controller widgets.
DEFAULT_SECTION: Final[str] = "music"

# Ordered list of sections, convenient for iterating UI controls in a stable
# order without relying on dict ordering semantics in older Python versions.
SECTION_KEYS: Final[tuple[str, ...]] = tuple(SECTION_TITLES.keys())

__all__ = [
    "DEFAULT_SECTION",
    "SECTION_KEYS",
    "SECTION_TITLES",
]

