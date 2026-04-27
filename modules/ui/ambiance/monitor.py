"""Second-screen monitor selection helpers for ambiance playback."""

from __future__ import annotations

from dataclasses import dataclass

from modules.ui.image_viewer import _get_monitors


@dataclass(frozen=True, slots=True)
class MonitorBounds:
    """Screen bounds used to place a fullscreen player window."""

    x: int
    y: int
    width: int
    height: int
    is_secondary: bool


class MonitorSelectionError(RuntimeError):
    """Raised when no monitor can be selected for ambiance playback."""


def select_target_monitor(*, allow_single_screen_fallback: bool = True) -> MonitorBounds:
    """Resolve monitor bounds for ambiance playback.

    If two monitors are available, the second one is selected.
    If one monitor is available and fallback is allowed, return this monitor and
    mark it as non-secondary.
    """

    monitors = _get_monitors()
    if not monitors:
        raise MonitorSelectionError("Aucun écran détecté pour l'ambiance.")

    if len(monitors) > 1:
        x, y, width, height = monitors[1]
        return MonitorBounds(int(x), int(y), int(width), int(height), True)

    if not allow_single_screen_fallback:
        raise MonitorSelectionError(
            "Mode ambiance indisponible: un seul écran détecté."
        )

    x, y, width, height = monitors[0]
    return MonitorBounds(int(x), int(y), int(width), int(height), False)
