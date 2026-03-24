from importlib import import_module

__all__ = ["CalendarWindow", "QuickAddPopover", "EventEditorDialog", "TimelineSimulatorDialog"]


_MODULE_MAP = {
    "CalendarWindow": ".calendar_window",
    "EventEditorDialog": ".event_editor_dialog",
    "QuickAddPopover": ".quick_add_popover",
    "TimelineSimulatorDialog": ".timeline_simulator_dialog",
}


def __getattr__(name: str):
    module_name = _MODULE_MAP.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(module_name, __name__)
    value = getattr(module, name)
    globals()[name] = value
    return value


def __dir__():
    return sorted(set(globals()) | set(__all__))
