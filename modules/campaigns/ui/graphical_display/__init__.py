"""Campaign graphical display package.

Use lazy exports so importing the package does not immediately import UI windows.
"""

__all__ = ["CampaignGraphWindow", "CampaignGraphPanel"]


def __getattr__(name: str):
    """Handle getattr."""
    if name == "CampaignGraphWindow":
        from .window import CampaignGraphWindow

        return CampaignGraphWindow
    if name == "CampaignGraphPanel":
        from .panel import CampaignGraphPanel

        return CampaignGraphPanel
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
