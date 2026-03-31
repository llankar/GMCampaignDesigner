"""Dashboard package."""

try:
    from .campaign_dashboard_panel import CampaignDashboardPanel
except ModuleNotFoundError:  # pragma: no cover - optional UI dependency in headless tests
    CampaignDashboardPanel = None

__all__ = ["CampaignDashboardPanel"]
