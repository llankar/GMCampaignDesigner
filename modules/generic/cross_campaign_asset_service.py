"""Service layer for exporting and importing assets between campaigns."""

from __future__ import annotations

import copy
import json
import os
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from modules.audio.entity_audio import normalize_audio_reference
from modules.generic.generic_model_wrapper import GenericModelWrapper
from modules.helpers.config_helper import ConfigHelper
from modules.helpers.logging_helper import (
    log_exception,
    log_module_import,
    log_warning,
)

log_module_import(__name__)

BUNDLE_VERSION = 1


PORTRAIT_ENTITY_TYPES = {"npcs", "objects", "pcs", "creatures", "places", "clues"}
AUDIO_ENTITY_TYPES = {"npcs", "pcs", "creatures", "places"}
ATTACHMENT_FIELDS = {
    "clues": "Attachment",
    "informations": "Attachment",
}


@dataclass
class CampaignDatabase:
    """Simple metadata structure for a campaign database location."""

    name: str
    root: Path
    db_path: Path


@dataclass
class AssetReference:
    entity_type: str
    record_key: str
    asset_type: str
    original_path: str
    absolute_path: Path


@dataclass
class BundleAnalysis:
    manifest: dict
    data_by_type: Dict[str, List[dict]]
    assets: List[dict]
    temp_dir: Path
    duplicates: Dict[str, List[str]]


def _resolve_active_campaign() -> CampaignDatabase:
    db_path_value = ConfigHelper.get("Database", "path", fallback="default_campaign.db") or "default_campaign.db"
    db_path = Path(db_path_value)
    if not db_path.is_absolute():
        db_path = (Path(ConfigHelper.get_campaign_dir()) / db_path).resolve()
    root = db_path.parent.resolve()
    return CampaignDatabase(name=root.name or db_path.stem, root=root, db_path=db_path)


def get_active_campaign() -> CampaignDatabase:
    return _resolve_active_campaign()


def list_sibling_campaigns(include_current: bool = False) -> List[CampaignDatabase]:
    active = _resolve_active_campaign()
    campaign_dir = active.root
    parent = campaign_dir.parent
    if not parent.exists():
        return [active] if include_current else []

    candidates: List[CampaignDatabase] = []
    for entry in sorted(parent.iterdir()):
        if not entry.is_dir():
            continue
        db_files = list(entry.glob("*.db"))
        if not db_files:
            continue
        for db_path in db_files:
            if not include_current and db_path.resolve() == active.db_path.resolve():
                continue
            candidates.append(
                CampaignDatabase(name=f"{entry.name} ({db_path.name})", root=entry.resolve(), db_path=db_path.resolve())
            )

    if include_current:
        candidates.insert(0, active)
    return candidates


def discover_databases_in_directory(directory: Path) -> List[CampaignDatabase]:
    directory = directory.resolve()
    db_files = list(directory.glob("*.db"))
    results: List[CampaignDatabase] = []
    for db_path in db_files:
        results.append(CampaignDatabase(name=f"{directory.name} ({db_path.name})", root=directory, db_path=db_path.resolve()))
    return results


def load_entities(entity_type: str, db_path: Path) -> List[dict]:
    wrapper = GenericModelWrapper(entity_type, db_path=str(db_path))
    return wrapper.load_items()


def save_entities(entity_type: str, db_path: Path, items: List[dict], *, replace: bool = True) -> None:
    wrapper = GenericModelWrapper(entity_type, db_path=str(db_path))
    wrapper.save_items(items, replace=replace)


def _determine_record_key(record: dict) -> str:
    for field in ("Name", "Title", "id", "ID"):
        value = record.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return str(record.get("rowid") or record.get("_id") or id(record))


def _collect_portrait(entity_type: str, record: dict, campaign_dir: Path) -> Optional[AssetReference]:
    portrait = (record.get("Portrait") or "").strip()
    if not portrait:
        return None
    absolute = _campaign_join(campaign_dir, portrait)
    if not absolute.exists():
        log_warning(
            f"Portrait missing for record {_determine_record_key(record)}: {portrait}",
            func_name="modules.generic.cross_campaign_asset_service._collect_portrait",
        )
        return None
    return AssetReference(
        entity_type=entity_type,
        record_key=_determine_record_key(record),
        asset_type="portrait",
        original_path=portrait,
        absolute_path=absolute,
    )


def _collect_audio_asset(entity_type: str, record: dict, campaign_dir: Path) -> Optional[AssetReference]:
    raw_value = record.get("Audio")
    normalized = normalize_audio_reference(raw_value)
    if not normalized:
        return None
    absolute = _campaign_join(campaign_dir, normalized)
    if not absolute.exists():
        log_warning(
            f"Audio missing for record {_determine_record_key(record)}: {normalized}",
            func_name="modules.generic.cross_campaign_asset_service._collect_audio_asset",
        )
        return None
    return AssetReference(
        entity_type=entity_type,
        record_key=_determine_record_key(record),
        asset_type="audio",
        original_path=normalized,
        absolute_path=absolute,
    )


def _collect_attachment_asset(
    entity_type: str, record: dict, campaign_dir: Path, field_name: str
) -> Optional[AssetReference]:
    raw_value = record.get(field_name)
    if raw_value is None:
        return None
    try:
        normalized = str(raw_value).strip()
    except Exception:
        return None
    if not normalized:
        return None

    absolute = _campaign_join(campaign_dir, normalized)
    if not absolute.exists() and not Path(normalized).is_absolute():
        uploads_candidate = campaign_dir / "assets" / "uploads" / normalized
        if uploads_candidate.exists():
            absolute = uploads_candidate
    if not absolute.exists():
        log_warning(
            f"Attachment missing for record {_determine_record_key(record)}: {normalized}",
            func_name="modules.generic.cross_campaign_asset_service._collect_attachment_asset",
        )
        return None

    return AssetReference(
        entity_type=entity_type,
        record_key=_determine_record_key(record),
        asset_type="attachment",
        original_path=normalized,
        absolute_path=absolute,
    )


def _campaign_join(campaign_dir: Path, path_value: str) -> Path:
    normalized = str(path_value).strip().replace("\\", "/")
    if not normalized:
        return campaign_dir
    path_obj = Path(normalized)
    if path_obj.is_absolute():
        return path_obj
    return (campaign_dir / normalized).resolve()


def _collect_map_assets(record: dict, campaign_dir: Path) -> Iterable[AssetReference]:
    key = _determine_record_key(record)
    image = (record.get("Image") or "").strip()
    if image:
        absolute = _campaign_join(campaign_dir, image)
        if absolute.exists():
            yield AssetReference("maps", key, "map_image", image, absolute)
        else:
            log_warning(
                f"Map image missing for {key}: {image}",
                func_name="modules.generic.cross_campaign_asset_service._collect_map_assets",
            )

    fog = (record.get("FogMaskPath") or "").strip()
    if fog:
        absolute = _campaign_join(campaign_dir, fog)
        if absolute.exists():
            yield AssetReference("maps", key, "map_mask", fog, absolute)
        else:
            log_warning(
                f"Fog mask missing for {key}: {fog}",
                func_name="modules.generic.cross_campaign_asset_service._collect_map_assets",
            )


def _deserialize_tokens(raw) -> Tuple[List[dict], type]:
    if isinstance(raw, list):
        return raw, list
    if isinstance(raw, str):
        trimmed = raw.strip()
        if not trimmed:
            return [], str
        try:
            parsed = json.loads(trimmed)
            if isinstance(parsed, list):
                return parsed, str
        except json.JSONDecodeError:
            pass
        try:
            parsed = eval(trimmed, {"__builtins__": {}})
            if isinstance(parsed, list):
                return parsed, str
        except Exception:
            return [], str
        return [], str
    return [], type(raw)


def _collect_token_assets(record: dict, campaign_dir: Path) -> Iterable[AssetReference]:
    tokens_raw = record.get("Tokens")
    tokens, _ = _deserialize_tokens(tokens_raw)
    if not tokens:
        return []

    key = _determine_record_key(record)
    assets: List[AssetReference] = []
    for token in tokens:
        if not isinstance(token, dict):
            continue
        for field, asset_type in ("image_path", "token_image"), ("video_path", "token_video"):
            path_value = token.get(field)
            if not path_value:
                continue
            absolute = _campaign_join(campaign_dir, path_value)
            if not absolute.exists():
                log_warning(
                    f"Token asset missing for {key}: {path_value}",
                    func_name="modules.generic.cross_campaign_asset_service._collect_token_assets",
                )
                continue
            assets.append(
                AssetReference(
                    entity_type="maps",
                    record_key=key,
                    asset_type=asset_type,
                    original_path=str(path_value),
                    absolute_path=absolute,
                )
            )
    return assets


def collect_assets(entity_type: str, records: Iterable[dict], campaign_dir: Path) -> List[AssetReference]:
    collected: List[AssetReference] = []
    if entity_type == "maps":
        for record in records:
            collected.extend(_collect_map_assets(record, campaign_dir))
            collected.extend(_collect_token_assets(record, campaign_dir))
        return collected

    attachment_field = ATTACHMENT_FIELDS.get(entity_type)
    for record in records:
        if entity_type in PORTRAIT_ENTITY_TYPES:
            portrait = _collect_portrait(entity_type, record, campaign_dir)
            if portrait:
                collected.append(portrait)
        if entity_type in AUDIO_ENTITY_TYPES:
            audio = _collect_audio_asset(entity_type, record, campaign_dir)
            if audio:
                collected.append(audio)
        if attachment_field:
            attachment = _collect_attachment_asset(entity_type, record, campaign_dir, attachment_field)
            if attachment:
                collected.append(attachment)
    return collected


def _ensure_unique_bundle_path(bundle_path: Path, existing: Dict[str, Path]) -> Path:
    base = bundle_path
    counter = 1
    while bundle_path.as_posix() in existing:
        bundle_path = base.with_name(f"{base.stem}_{counter}{base.suffix}")
        counter += 1
    return bundle_path


def _bundle_path_for_asset(asset: AssetReference) -> Path:
    original = asset.original_path.replace("\\", "/").lstrip("./")
    if Path(original).is_absolute():
        return Path("assets") / "external" / Path(original).name
    return Path("assets") / Path(original)


def export_bundle(
    destination: Path,
    source_campaign: CampaignDatabase,
    selected_records: Dict[str, List[dict]],
    progress_callback=None,
) -> dict:
    destination = destination.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)

    _call_progress(progress_callback, "Collecting records...", 0.05)

    data_dir = Path(tempfile.mkdtemp(prefix="asset_export_"))
    temp_root = Path(data_dir)
    manifest: dict = {
        "version": BUNDLE_VERSION,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "source_campaign": {
            "name": source_campaign.name,
            "path": str(source_campaign.root),
            "database": str(source_campaign.db_path),
        },
        "entities": {},
        "assets": [],
    }

    assets_lookup: Dict[str, Path] = {}

    try:
        (temp_root / "data").mkdir(parents=True, exist_ok=True)
        for entity_type, records in selected_records.items():
            if not records:
                continue
            data_path = temp_root / "data" / f"{entity_type}.json"
            with data_path.open("w", encoding="utf-8") as fh:
                json.dump(records, fh, indent=2, ensure_ascii=False)
            manifest["entities"][entity_type] = {
                "count": len(records),
                "data_path": f"data/{entity_type}.json",
            }

            asset_refs = collect_assets(entity_type, records, source_campaign.root)
            for asset in asset_refs:
                bundle_path = _bundle_path_for_asset(asset)
                bundle_path = _ensure_unique_bundle_path(bundle_path, assets_lookup)
                bundle_abs = temp_root / bundle_path
                bundle_abs.parent.mkdir(parents=True, exist_ok=True)
                try:
                    shutil.copy2(asset.absolute_path, bundle_abs)
                except Exception as exc:
                    log_warning(
                        f"Unable to bundle asset {asset.absolute_path}: {exc}",
                        func_name="modules.generic.cross_campaign_asset_service.export_bundle",
                    )
                    continue
                assets_lookup[bundle_path.as_posix()] = bundle_abs
                manifest["assets"].append(
                    {
                        "entity_type": asset.entity_type,
                        "record_key": asset.record_key,
                        "asset_type": asset.asset_type,
                        "original_path": asset.original_path,
                        "bundle_path": bundle_path.as_posix(),
                    }
                )

        _call_progress(progress_callback, "Writing bundle archive...", 0.8)
        archive_path = temp_root / "manifest.json"
        archive_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

        with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for file_path in temp_root.rglob("*"):
                if file_path.is_dir():
                    continue
                arcname = file_path.relative_to(temp_root).as_posix()
                zf.write(file_path, arcname)

        _call_progress(progress_callback, "Export completed", 1.0)
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)

    manifest["archive_path"] = str(destination)
    return manifest


def _call_progress(callback, message: str, fraction: float) -> None:
    if callback is None:
        return
    try:
        callback(message, fraction)
    except Exception:
        pass


def analyze_bundle(bundle_path: Path, target_db: Path) -> BundleAnalysis:
    bundle_path = bundle_path.resolve()
    if not bundle_path.exists():
        raise FileNotFoundError(bundle_path)

    temp_dir = Path(tempfile.mkdtemp(prefix="asset_import_"))
    try:
        with zipfile.ZipFile(bundle_path, "r") as zf:
            zf.extractall(temp_dir)

        manifest_path = temp_dir / "manifest.json"
        if not manifest_path.exists():
            raise ValueError("Bundle manifest missing")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        version = manifest.get("version")
        if version != BUNDLE_VERSION:
            raise ValueError(f"Unsupported bundle version: {version}")

        data_by_type: Dict[str, List[dict]] = {}
        for entity_type, meta in manifest.get("entities", {}).items():
            data_file = meta.get("data_path")
            if not data_file:
                continue
            file_path = temp_dir / data_file
            if not file_path.exists():
                log_warning(
                    f"Missing data file in bundle: {data_file}",
                    func_name="modules.generic.cross_campaign_asset_service.analyze_bundle",
                )
                continue
            try:
                records = json.loads(file_path.read_text(encoding="utf-8"))
                if isinstance(records, list):
                    data_by_type[entity_type] = records
            except json.JSONDecodeError as exc:
                log_exception(
                    f"Failed to parse {data_file}: {exc}",
                    func_name="modules.generic.cross_campaign_asset_service.analyze_bundle",
                )

        duplicates: Dict[str, List[str]] = {}
        for entity_type, records in data_by_type.items():
            try:
                existing = load_entities(entity_type, target_db)
            except Exception as exc:
                log_warning(
                    f"Unable to load existing {entity_type}: {exc}",
                    func_name="modules.generic.cross_campaign_asset_service.analyze_bundle",
                )
                existing = []
            existing_lookup = {_determine_record_key(item): item for item in existing}
            dupes: List[str] = []
            for record in records:
                key = _determine_record_key(record)
                if key in existing_lookup:
                    dupes.append(key)
            if dupes:
                duplicates[entity_type] = dupes

        return BundleAnalysis(
            manifest=manifest,
            data_by_type=data_by_type,
            assets=manifest.get("assets", []),
            temp_dir=temp_dir,
            duplicates=duplicates,
        )
    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise


def _determine_target_path(asset_type: str, original_path: str, campaign_dir: Path) -> Tuple[Path, str]:
    original = (original_path or "").replace("\\", "/")
    name = Path(original).name or "asset"

    if asset_type == "portrait":
        base = campaign_dir / "assets" / "portraits"
        relative_base = Path("assets/portraits")
    elif asset_type == "map_image":
        base = campaign_dir / "assets" / "images" / "map_images"
        relative_base = Path("assets/images/map_images")
    elif asset_type == "map_mask":
        base = campaign_dir / "masks"
        relative_base = Path("masks")
    elif asset_type == "audio":
        base = campaign_dir / "assets" / "audio"
        relative_base = Path("assets/audio")
    elif asset_type == "attachment":
        base = campaign_dir / "assets" / "uploads"
        relative_base = Path(".")
    else:  # token assets
        if original and not Path(original).is_absolute():
            rel = Path(original.lstrip("./"))
            base = campaign_dir / rel.parent
            relative_base = rel.parent
            name = rel.name
        else:
            base = campaign_dir / "assets" / "tokens"
            relative_base = Path("assets/tokens")

    base.mkdir(parents=True, exist_ok=True)

    candidate = base / name
    relative = (relative_base / name).as_posix()
    counter = 1
    while candidate.exists():
        candidate = base / f"{Path(name).stem}_{counter}{Path(name).suffix}"
        relative = (relative_base / candidate.name).as_posix()
        counter += 1

    return candidate, relative


def apply_import(
    analysis: BundleAnalysis,
    target_campaign: CampaignDatabase,
    *,
    overwrite: bool,
    progress_callback=None,
) -> Dict[str, int]:
    replacements: Dict[str, str] = {}

    assets_dir = Path(analysis.temp_dir)
    summary: Dict[str, int] = {"imported": 0, "skipped": 0, "updated": 0}

    try:
        total_assets = len(analysis.assets) or 1
        for index, asset in enumerate(analysis.assets, start=1):
            bundle_path = asset.get("bundle_path")
            source = assets_dir / bundle_path if bundle_path else None
            if not source or not source.exists():
                log_warning(
                    f"Bundle asset missing: {bundle_path}",
                    func_name="modules.generic.cross_campaign_asset_service.apply_import",
                )
                continue
            target_path, relative = _determine_target_path(
                asset.get("asset_type", ""), asset.get("original_path", ""), target_campaign.root
            )
            try:
                shutil.copy2(source, target_path)
                replacements[asset.get("original_path", "")] = relative
            except Exception as exc:
                log_warning(
                    f"Failed to copy asset {source}: {exc}",
                    func_name="modules.generic.cross_campaign_asset_service.apply_import",
                )
            _call_progress(progress_callback, f"Copying assets ({index}/{total_assets})", index / total_assets)

        for entity_type, records in analysis.data_by_type.items():
            if not records:
                continue
            existing = load_entities(entity_type, target_campaign.db_path)
            existing_map = {_determine_record_key(item): item for item in existing}

            merged: Dict[str, dict] = {key: item for key, item in existing_map.items()}
            for record in records:
                key = _determine_record_key(record)
                updated_record = _rewrite_record_paths(entity_type, record, replacements)
                if key in existing_map:
                    if not overwrite:
                        summary["skipped"] += 1
                        continue
                    merged[key] = updated_record
                    summary["updated"] += 1
                else:
                    merged[key] = updated_record
                    summary["imported"] += 1

            save_entities(entity_type, target_campaign.db_path, list(merged.values()), replace=False)
    finally:
        shutil.rmtree(analysis.temp_dir, ignore_errors=True)

    _call_progress(progress_callback, "Import complete", 1.0)
    return summary


def _rewrite_record_paths(entity_type: str, record: dict, replacements: Dict[str, str]) -> dict:
    updated = copy.deepcopy(record)

    if entity_type in PORTRAIT_ENTITY_TYPES:
        portrait = updated.get("Portrait")
        if portrait in replacements:
            updated["Portrait"] = replacements[portrait]

    if entity_type in AUDIO_ENTITY_TYPES:
        audio = updated.get("Audio")
        if audio in replacements:
            updated["Audio"] = replacements[audio]

    attachment_field = ATTACHMENT_FIELDS.get(entity_type)
    if attachment_field:
        attachment_value = updated.get(attachment_field)
        if attachment_value in replacements:
            updated[attachment_field] = replacements[attachment_value]

    if entity_type == "maps":
        image = updated.get("Image")
        if image in replacements:
            updated["Image"] = replacements[image]
        mask = updated.get("FogMaskPath")
        if mask in replacements:
            updated["FogMaskPath"] = replacements[mask]
        tokens_raw = updated.get("Tokens")
        tokens, container = _deserialize_tokens(tokens_raw)
        changed = False
        for token in tokens:
            if not isinstance(token, dict):
                continue
            for field in ("image_path", "video_path"):
                original = token.get(field)
                if original in replacements:
                    token[field] = replacements[original]
                    changed = True
        if changed:
            if container is str:
                updated["Tokens"] = json.dumps(tokens)
            else:
                updated["Tokens"] = tokens

    return updated


def cleanup_analysis(analysis: BundleAnalysis) -> None:
    shutil.rmtree(analysis.temp_dir, ignore_errors=True)

