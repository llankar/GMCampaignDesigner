"""Compatibility patches for CustomTkinter widgets used by the app."""

from __future__ import annotations

from typing import Any

from modules.helpers.logging_helper import log_debug, log_module_import

log_module_import(__name__)


def apply_ctk_button_after_cleanup_patch(ctk_module: Any) -> None:
    """Ensure ``CTkButton`` cancels pending ``after`` callbacks on destroy.

    Some CustomTkinter builds can emit Tcl errors like
    ``invalid command name "..._click_animation"`` when a button is destroyed
    while a click animation callback is still queued. This patch tracks callback
    IDs created via ``after`` on each button instance and cancels them during
    ``destroy``.
    """

    button_cls = getattr(ctk_module, "CTkButton", None)
    if button_cls is None:
        return
    if getattr(button_cls, "_gm_after_cleanup_patch", False):
        return

    original_after = button_cls.after
    original_after_cancel = button_cls.after_cancel
    original_destroy = button_cls.destroy

    def _tracked_after(self: Any, ms: int, callback: Any = None, *args: Any) -> Any:
        callback_id = original_after(self, ms, callback, *args)
        if callback is not None and callback_id:
            tracked = getattr(self, "_gm_tracked_after_ids", None)
            if tracked is None:
                tracked = set()
                setattr(self, "_gm_tracked_after_ids", tracked)
            tracked.add(callback_id)
        return callback_id

    def _tracked_after_cancel(self: Any, callback_id: Any) -> None:
        tracked = getattr(self, "_gm_tracked_after_ids", None)
        if tracked is not None:
            tracked.discard(callback_id)
        original_after_cancel(self, callback_id)

    def _safe_destroy(self: Any) -> Any:
        tracked = tuple(getattr(self, "_gm_tracked_after_ids", ()))
        for callback_id in tracked:
            try:
                original_after_cancel(self, callback_id)
            except Exception:
                pass
        if hasattr(self, "_gm_tracked_after_ids"):
            self._gm_tracked_after_ids.clear()
        return original_destroy(self)

    button_cls.after = _tracked_after
    button_cls.after_cancel = _tracked_after_cancel
    button_cls.destroy = _safe_destroy
    button_cls._gm_after_cleanup_patch = True
    log_debug("Applied CTkButton after-cleanup compatibility patch")
