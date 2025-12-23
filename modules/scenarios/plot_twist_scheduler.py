from __future__ import annotations

from datetime import datetime, timedelta
from typing import Callable, Optional
import tkinter as tk

from modules.helpers.logging_helper import log_info, log_exception, log_module_import


class PlotTwistScheduler:
    def __init__(self, root_widget: tk.Misc):
        self._root = root_widget
        self._after_ids: list[str] = []
        self._active = False
        self._session_start: Optional[datetime] = None

    def start(
        self,
        session_start: datetime,
        mid_hours: Optional[float],
        end_hours: Optional[float],
        on_mid: Callable[[], None],
        on_end: Callable[[], None],
    ) -> None:
        self.cancel()
        self._active = True
        self._session_start = session_start
        now = datetime.now()

        def _schedule(hours: Optional[float], callback: Callable[[], None], label: str) -> None:
            if hours is None or hours < 0:
                return
            target = session_start + timedelta(hours=hours)
            delay = max(0.0, (target - now).total_seconds())
            delay_ms = int(delay * 1000)

            def _fire():
                if not self._active:
                    return
                try:
                    callback()
                except Exception as exc:
                    log_exception(exc, func_name="PlotTwistScheduler._fire")
                finally:
                    log_info(f"Plot twist timer fired: {label}", func_name="PlotTwistScheduler._fire")

            try:
                after_id = self._root.after(delay_ms, _fire)
            except Exception as exc:
                log_exception(exc, func_name="PlotTwistScheduler.start")
                return
            self._after_ids.append(after_id)

        _schedule(mid_hours, on_mid, "mid")
        _schedule(end_hours, on_end, "end")
        log_info("Plot twist scheduler started.", func_name="PlotTwistScheduler.start")

    def cancel(self) -> None:
        if not self._after_ids:
            self._active = False
            self._session_start = None
            return
        for after_id in list(self._after_ids):
            try:
                self._root.after_cancel(after_id)
            except Exception:
                pass
        self._after_ids.clear()
        self._active = False
        self._session_start = None
        log_info("Plot twist scheduler canceled.", func_name="PlotTwistScheduler.cancel")

    def is_active(self) -> bool:
        return self._active


log_module_import(__name__)
