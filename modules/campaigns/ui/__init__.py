"""Campaign UI package.

Exports are resolved lazily to avoid chained imports during package import.
"""

__all__ = ["CampaignBuilderWizard", "ArcEditorDialog"]


def __getattr__(name: str):
    if name == "CampaignBuilderWizard":
        from .campaign_builder_wizard import CampaignBuilderWizard

        return CampaignBuilderWizard
    if name == "ArcEditorDialog":
        from .arc_editor_dialog import ArcEditorDialog

        return ArcEditorDialog
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
