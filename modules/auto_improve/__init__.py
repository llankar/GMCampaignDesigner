"""Auto-improve package.

Keep package import side effects minimal; import heavy orchestrator code lazily.
"""

__all__ = ["AutoImproveOrchestrator"]


def __getattr__(name: str):
    """Handle getattr."""
    if name == "AutoImproveOrchestrator":
        from .orchestrator import AutoImproveOrchestrator

        return AutoImproveOrchestrator
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
