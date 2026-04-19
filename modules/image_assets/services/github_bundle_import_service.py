"""Import GitHub image-library bundle zips into the active campaign image library."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from modules.generic.cross_campaign_asset_service import (
    analyze_bundle,
    apply_import_for_entity_types,
    cleanup_analysis,
    get_active_campaign,
)


@dataclass(slots=True)
class ImageLibraryBundleAnalysis:
    """Metadata extracted from a bundle before import."""

    duplicate_names: list[str]
    has_image_assets: bool


@dataclass(slots=True)
class ImageLibraryBundleImportSummary:
    """Outcome of an image-library-only bundle import."""

    imported: int
    updated: int
    skipped: int


class ImageLibraryBundleImportService:
    """Service dedicated to importing image-library GitHub bundle archives."""

    _ALLOWED_ENTITY_TYPES = {"image_assets"}

    def analyze_bundle(self, zip_path: str | Path) -> ImageLibraryBundleAnalysis:
        """Inspect bundle and return duplicate information for image assets."""
        archive_path = Path(zip_path)
        campaign = get_active_campaign()
        analysis = analyze_bundle(archive_path, campaign.db_path)
        try:
            image_records = analysis.data_by_type.get("image_assets", [])
            duplicates = analysis.duplicates.get("image_assets", [])
            return ImageLibraryBundleAnalysis(
                duplicate_names=list(duplicates),
                has_image_assets=bool(image_records),
            )
        finally:
            cleanup_analysis(analysis)

    def import_bundle(self, zip_path: str | Path, *, overwrite: bool) -> ImageLibraryBundleImportSummary:
        """Import image assets from bundle into active campaign."""
        archive_path = Path(zip_path)
        campaign = get_active_campaign()
        analysis = analyze_bundle(archive_path, campaign.db_path)
        try:
            result = apply_import_for_entity_types(
                analysis,
                campaign,
                entity_types=self._ALLOWED_ENTITY_TYPES,
                overwrite=overwrite,
                progress_callback=None,
            )
            return ImageLibraryBundleImportSummary(
                imported=int(result.get("imported", 0) or 0),
                updated=int(result.get("updated", 0) or 0),
                skipped=int(result.get("skipped", 0) or 0),
            )
        finally:
            cleanup_analysis(analysis)
