"""Utilities for audio library."""

from modules.audio.library.repository import AUDIO_EXTENSIONS
from modules.audio.library.service import AudioLibraryService
from modules.helpers.logging_helper import log_module_import

log_module_import(__name__)


class AudioLibrary(AudioLibraryService):
    """Backward-compatible facade for the dedicated audio library service layer."""

    def get_moods(self, section: str, category: str | None = None):
        """Return moods."""
        if category is None:
            return self.get_moods_for_section(section)
        return super().get_moods(section, category)
