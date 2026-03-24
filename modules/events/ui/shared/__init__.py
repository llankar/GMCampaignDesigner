from importlib import import_module

__all__ = ["MultiLinkSelector", "RelatedEventsPanel"]


_MODULE_MAP = {
    "MultiLinkSelector": ".multi_link_selector",
    "RelatedEventsPanel": ".related_events_panel",
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
