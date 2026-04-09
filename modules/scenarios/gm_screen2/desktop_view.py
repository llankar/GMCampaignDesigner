"""Desktop-focused variant of the GM screen."""

from modules.scenarios.gm_screen_view import GMScreenView


class GMScreen2View(GMScreenView):
    """GM Screen variant that opens panels in desktop mode by default."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("desktop_mode", True)
        super().__init__(*args, **kwargs)
