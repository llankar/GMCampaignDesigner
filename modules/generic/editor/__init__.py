"""UI helper utilities for the generic entity editor."""

__all__ = ["SmartEditorToolbar", "prioritize_fields"]


def __getattr__(name):
    if name in __all__:
        from .smart_ui import SmartEditorToolbar, prioritize_fields

        exports = {
            "SmartEditorToolbar": SmartEditorToolbar,
            "prioritize_fields": prioritize_fields,
        }
        return exports[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
