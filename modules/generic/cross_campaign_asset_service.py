"""Service layer for exporting and importing assets between campaigns."""

from __future__ import annotations

import copy
import json
import os
import shutil
import sqlite3
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from modules.audio.entity_audio import normalize_audio_reference
from modules.generic.generic_model_wrapper import GenericModelWrapper
from modules.helpers.config_helper import ConfigHelper
from modules.helpers.portrait_helper import parse_portrait_value, serialize_portrait_value
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
    "books": "Attachment",
    "puzzles": "Handout",
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
    database: Optional[dict] = None
    world_maps: Optional[Dict[str, dict]] = None
    systems: Optional[List[dict]] = None


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
    try:
        return wrapper.load_items()
    except sqlite3.OperationalError as exc:
        if "no such table" in str(exc).lower():
            log_warning(
                f"Skipping entity type '{entity_type}' in {db_path}: {exc}",
                func_name="modules.generic.cross_campaign_asset_service.load_entities",
            )
            return []
        raise


def save_entities(entity_type: str, db_path: Path, items: List[dict], *, replace: bool = True) -> None:
    wrapper = GenericModelWrapper(entity_type, db_path=str(db_path))
    wrapper.save_items(items, replace=replace)


def _ensure_campaign_systems_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS campaign_systems (
            slug TEXT PRIMARY KEY,
            label TEXT NOT NULL,
            default_formula TEXT,
            supported_faces_json TEXT,
            analyzer_config_json TEXT
        )
        """
    )


def _load_campaign_systems(db_path: Path) -> List[dict]:
    if not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.execute(
            """
            SELECT slug, label, default_formula, supported_faces_json, analyzer_config_json
            FROM campaign_systems
            ORDER BY slug
            """
        )
        return [dict(row) for row in cursor.fetchall()]
    except sqlite3.OperationalError as exc:
        if "no such table" in str(exc).lower():
            log_warning(
                f"Skipping campaign systems export from {db_path}: {exc}",
                func_name="modules.generic.cross_campaign_asset_service._load_campaign_systems",
            )
            return []
        raise
    finally:
        conn.close()


def _determine_record_key(record: dict) -> str:
    for field in ("Name", "Title", "id", "ID"):
        value = record.get(field)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return str(record.get("rowid") or record.get("_id") or id(record))


def _collect_portraits(entity_type: str, record: dict, campaign_dir: Path) -> List[AssetReference]:
    portraits = parse_portrait_value(record.get("Portrait"))
    collected: List[AssetReference] = []
    for portrait in portraits:
        if not portrait:
            continue
        absolute = _campaign_join(campaign_dir, portrait)
        if not absolute.exists():
            log_warning(
                f"Portrait missing for record {_determine_record_key(record)}: {portrait}",
                func_name="modules.generic.cross_campaign_asset_service._collect_portraits",
            )
            continue
        collected.append(
            AssetReference(
                entity_type=entity_type,
                record_key=_determine_record_key(record),
                asset_type="portrait",
                original_path=portrait,
                absolute_path=absolute,
            )
        )
    return collected


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


def _resolve_campaign_dir(campaign_dir: Optional[Path]) -> Path:
    base_dir = ConfigHelper.get_campaign_dir() or ""
    base_path = Path(base_dir).resolve() if base_dir else Path.cwd()

    if campaign_dir is None:
        return base_path

    candidate = Path(campaign_dir)
    if not candidate.is_absolute():
        candidate = (base_path / candidate).resolve()
    return candidate


def _world_map_store_path(campaign_dir: Optional[Path]) -> Path:
    root = _resolve_campaign_dir(campaign_dir)
    return (root / "world_maps" / "world_map_data.json").resolve()


def load_world_map_store(campaign_dir: Optional[Path]) -> Dict[str, dict]:
    path = _world_map_store_path(campaign_dir)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        log_warning(
            f"Failed to load world map store at {path}: {exc}",
            func_name="modules.generic.cross_campaign_asset_service.load_world_map_store",
        )
        return {}

    maps = payload.get("maps") if isinstance(payload, dict) else payload
    return maps if isinstance(maps, dict) else {}


def save_world_map_store(campaign_dir: Optional[Path], maps: Dict[str, dict]) -> None:
    path = _world_map_store_path(campaign_dir)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"maps": maps}
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as exc:
        log_warning(
            f"Failed to save world map store at {path}: {exc}",
            func_name="modules.generic.cross_campaign_asset_service.save_world_map_store",
        )


def _collect_world_map_entries(records: Iterable[dict], campaign_dir: Path) -> Dict[str, dict]:
    store = load_world_map_store(campaign_dir)
    if not store:
        return {}

    collected: Dict[str, dict] = {}
    for record in records:
        key = _determine_record_key(record)
        entry = store.get(key)
        if not isinstance(entry, dict):
            continue
        collected[key] = copy.deepcopy(entry)
    return collected


def _rewrite_world_map_entries(
    entries: Dict[str, dict], replacements: Dict[str, str]
) -> Dict[str, dict]:
    rewritten: Dict[str, dict] = {}
    for name, entry in entries.items():
        if not isinstance(entry, dict):
            continue
        updated = copy.deepcopy(entry)
        image_path = updated.get("image")
        if isinstance(image_path, str) and image_path in replacements:
            updated["image"] = replacements[image_path]

        tokens = updated.get("tokens")
        if isinstance(tokens, list):
            for token in tokens:
                if not isinstance(token, dict):
                    continue
                for field in ("portrait_path", "image_path", "token_image", "video_path"):
                    value = token.get(field)
                    if isinstance(value, str) and value in replacements:
                        token[field] = replacements[value]

        rewritten[name] = updated
    return rewritten


def _merge_world_map_entries(target_dir: Path, entries: Dict[str, dict]) -> None:
    if not entries:
        return

    store = load_world_map_store(target_dir)
    merged = {key: copy.deepcopy(value) for key, value in store.items()}

    changed = False
    for name, entry in entries.items():
        if not isinstance(entry, dict):
            continue
        existing = merged.get(name, {})
        combined = copy.deepcopy(existing)
        combined.update(copy.deepcopy(entry))
        if combined != existing:
            merged[name] = combined
            changed = True
        elif name not in merged:
            merged[name] = copy.deepcopy(entry)
            changed = True

    if changed:
        save_world_map_store(target_dir, merged)


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
            collected.extend(_collect_portraits(entity_type, record, campaign_dir))
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
    *,
    include_database: bool = False,
    include_systems: bool = True,
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
        "bundle_mode": "full_campaign" if include_database else "asset_bundle",
    }

    assets_lookup: Dict[str, Path] = {}

    bundled_world_maps: Dict[str, dict] = {}

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

            if entity_type == "maps":
                bundled_world_maps.update(_collect_world_map_entries(records, source_campaign.root))

        if include_systems:
            systems = _load_campaign_systems(source_campaign.db_path)
            systems_path = temp_root / "data" / "campaign_systems.json"
            with systems_path.open("w", encoding="utf-8") as fh:
                json.dump(systems, fh, indent=2, ensure_ascii=False)
            manifest["systems"] = {
                "count": len(systems),
                "data_path": "data/campaign_systems.json",
            }

        if bundled_world_maps:
            world_map_path = temp_root / "data" / "world_maps.json"
            with world_map_path.open("w", encoding="utf-8") as fh:
                json.dump({"maps": bundled_world_maps}, fh, indent=2, ensure_ascii=False)
            manifest["world_maps"] = {
                "count": len(bundled_world_maps),
                "data_path": "data/world_maps.json",
            }

        if include_database:
            try:
                if not source_campaign.db_path.exists():
                    raise FileNotFoundError(source_campaign.db_path)
                db_dir = temp_root / "database"
                db_dir.mkdir(parents=True, exist_ok=True)
                db_destination = db_dir / source_campaign.db_path.name
                shutil.copy2(source_campaign.db_path, db_destination)
                stat = source_campaign.db_path.stat()
                manifest["database"] = {
                    "file_name": source_campaign.db_path.name,
                    "relative_path": f"database/{source_campaign.db_path.name}",
                    "size": int(stat.st_size),
                    "modified_at": datetime.utcfromtimestamp(stat.st_mtime).isoformat() + "Z",
                }
            except Exception as exc:
                log_exception(
                    f"Unable to include campaign database in bundle: {exc}",
                    func_name="modules.generic.cross_campaign_asset_service.export_bundle",
                )
                raise
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

        database_entry = manifest.get("database")
        if not isinstance(database_entry, dict):
            database_entry = None

        world_maps_manifest = manifest.get("world_maps")
        world_maps: Dict[str, dict] = {}
        if isinstance(world_maps_manifest, dict):
            data_file = world_maps_manifest.get("data_path") or world_maps_manifest.get("path")
            if data_file:
                file_path = temp_dir / data_file
                if file_path.exists():
                    try:
                        payload = json.loads(file_path.read_text(encoding="utf-8"))
                        maps = payload.get("maps") if isinstance(payload, dict) else payload
                        if isinstance(maps, dict):
                            world_maps = maps
                    except json.JSONDecodeError as exc:
                        log_exception(
                            f"Failed to parse world map data {data_file}: {exc}",
                            func_name="modules.generic.cross_campaign_asset_service.analyze_bundle",
                        )

        systems_manifest = manifest.get("systems")
        systems: Optional[List[dict]] = None
        if isinstance(systems_manifest, dict):
            data_file = systems_manifest.get("data_path") or systems_manifest.get("path")
            if data_file:
                file_path = temp_dir / data_file
                if file_path.exists():
                    try:
                        payload = json.loads(file_path.read_text(encoding="utf-8"))
                        if isinstance(payload, list):
                            systems = payload
                    except json.JSONDecodeError as exc:
                        log_exception(
                            f"Failed to parse campaign systems data {data_file}: {exc}",
                            func_name="modules.generic.cross_campaign_asset_service.analyze_bundle",
                        )

        return BundleAnalysis(
            manifest=manifest,
            data_by_type=data_by_type,
            assets=manifest.get("assets", []),
            temp_dir=temp_dir,
            duplicates=duplicates,
            database=database_entry,
            world_maps=world_maps or None,
            systems=systems,
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
        relative_base = Path("assets/uploads")
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


def detect_duplicates(
    selected_records: Dict[str, List[dict]], target_campaign: CampaignDatabase
) -> Dict[str, List[str]]:
    duplicates: Dict[str, List[str]] = {}
    for entity_type, records in selected_records.items():
        if not records:
            continue
        try:
            existing = load_entities(entity_type, target_campaign.db_path)
        except Exception as exc:
            log_warning(
                f"Unable to load existing {entity_type}: {exc}",
                func_name="modules.generic.cross_campaign_asset_service.detect_duplicates",
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
    return duplicates


def apply_import(
    analysis: BundleAnalysis,
    target_campaign: CampaignDatabase,
    *,
    overwrite: bool,
    progress_callback=None,
) -> Dict[str, int]:
    replacements: Dict[str, str] = {}

    assets_dir = Path(analysis.temp_dir)
    summary: Dict[str, int] = {
        "imported": 0,
        "skipped": 0,
        "updated": 0,
        "systems_imported": 0,
        "systems_skipped": 0,
        "systems_updated": 0,
    }

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

        if analysis.systems:
            conn = sqlite3.connect(str(target_campaign.db_path))
            try:
                _ensure_campaign_systems_table(conn)
                conn.row_factory = sqlite3.Row
                existing_slugs = {
                    row["slug"]
                    for row in conn.execute("SELECT slug FROM campaign_systems").fetchall()
                    if row["slug"]
                }
                for system in analysis.systems:
                    slug = str(system.get("slug") or "").strip()
                    if not slug:
                        continue
                    label = system.get("label")
                    default_formula = system.get("default_formula")
                    supported_faces_json = system.get("supported_faces_json")
                    analyzer_config_json = system.get("analyzer_config_json")
                    if slug in existing_slugs:
                        if not overwrite:
                            summary["systems_skipped"] += 1
                            continue
                        conn.execute(
                            """
                            UPDATE campaign_systems
                            SET label = ?, default_formula = ?, supported_faces_json = ?, analyzer_config_json = ?
                            WHERE slug = ?
                            """,
                            (label, default_formula, supported_faces_json, analyzer_config_json, slug),
                        )
                        summary["systems_updated"] += 1
                    else:
                        conn.execute(
                            """
                            INSERT INTO campaign_systems (
                                slug, label, default_formula, supported_faces_json, analyzer_config_json
                            ) VALUES (?, ?, ?, ?, ?)
                            """,
                            (slug, label, default_formula, supported_faces_json, analyzer_config_json),
                        )
                        summary["systems_imported"] += 1
                conn.commit()
            finally:
                conn.close()

        if analysis.world_maps:
            rewritten_world_maps = _rewrite_world_map_entries(analysis.world_maps, replacements)
            _merge_world_map_entries(target_campaign.root, rewritten_world_maps)
    finally:
        shutil.rmtree(analysis.temp_dir, ignore_errors=True)

    _call_progress(progress_callback, "Import complete", 1.0)
    return summary


def install_full_campaign_bundle(
    bundle_path: Path,
    target_dir: Path,
    *,
    progress_callback=None,
) -> CampaignDatabase:
    """Install a full campaign bundle by extracting its database and assets."""

    bundle_path = Path(bundle_path).resolve()
    target_dir = Path(target_dir).resolve()

    temp_dir = Path(tempfile.mkdtemp(prefix="campaign_install_"))
    try:
        with zipfile.ZipFile(bundle_path, "r") as zf:
            zf.extractall(temp_dir)

        manifest_path = temp_dir / "manifest.json"
        if not manifest_path.exists():
            raise ValueError("Bundle manifest missing")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        database_entry = manifest.get("database")
        if isinstance(database_entry, str):
            database_entry = {"relative_path": database_entry}
        if not isinstance(database_entry, dict):
            raise ValueError("Bundle does not contain a campaign database")

        relative_path = str(database_entry.get("relative_path") or "").strip()
        if not relative_path:
            relative_path = database_entry.get("path") or database_entry.get("file_name") or ""
        if not relative_path:
            raise ValueError("Bundle database entry is missing a path")

        db_source = (temp_dir / relative_path).resolve()
        if not db_source.exists():
            raise FileNotFoundError(db_source)

        db_name = str(database_entry.get("file_name") or Path(relative_path).name or "campaign.db")

        if not target_dir.exists():
            target_dir.mkdir(parents=True, exist_ok=True)

        db_destination = target_dir / db_name
        shutil.copy2(db_source, db_destination)

        assets = manifest.get("assets") or []
        total_steps = max(len(assets) + 1, 1)
        _call_progress(progress_callback, "Copying database", 1 / total_steps)

        target_root = target_dir.resolve()
        for index, asset in enumerate(assets, start=1):
            bundle_rel = asset.get("bundle_path")
            if not bundle_rel:
                continue
            source_asset = (temp_dir / bundle_rel).resolve()
            if not source_asset.exists():
                log_warning(
                    f"Missing asset in bundle: {bundle_rel}",
                    func_name="modules.generic.cross_campaign_asset_service.install_full_campaign_bundle",
                )
                continue

            original_path = str(asset.get("original_path") or "").replace("\\", "/").strip()
            relative_parts = [part for part in Path(original_path).parts if part not in ("", ".", "..")]
            relative = Path(*relative_parts) if relative_parts else Path(source_asset.name)
            destination = (target_root / relative).resolve()
            if not str(destination).startswith(str(target_root)):
                destination = target_root / source_asset.name

            destination.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(source_asset, destination)
            except Exception as exc:
                log_warning(
                    f"Failed to copy asset {source_asset}: {exc}",
                    func_name="modules.generic.cross_campaign_asset_service.install_full_campaign_bundle",
                )
                continue

            _call_progress(
                progress_callback,
                f"Copying assets ({index}/{len(assets)})",
                min((index + 1) / total_steps, 1.0),
            )

        campaign_name = str(manifest.get("source_campaign", {}).get("name") or target_dir.name)
        return CampaignDatabase(name=campaign_name, root=target_dir, db_path=db_destination)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def apply_direct_copy(
    selected_records: Dict[str, List[dict]],
    *,
    source_campaign: CampaignDatabase,
    target_campaign: CampaignDatabase,
    overwrite: bool,
    progress_callback=None,
) -> Dict[str, int]:
    replacements: Dict[str, str] = {}
    summary: Dict[str, int] = {"imported": 0, "updated": 0, "skipped": 0}

    asset_refs: List[AssetReference] = []
    for entity_type, records in selected_records.items():
        asset_refs.extend(collect_assets(entity_type, records, source_campaign.root))

    world_map_entries: Dict[str, dict] = {}
    map_records = selected_records.get("maps")
    if map_records:
        world_map_entries = _collect_world_map_entries(map_records, source_campaign.root)

    total_assets = len(asset_refs) or 1
    for index, asset in enumerate(asset_refs, start=1):
        original = asset.original_path
        if original in replacements:
            _call_progress(progress_callback, f"Copying assets ({index}/{total_assets})", index / total_assets)
            continue
        target_path, relative = _determine_target_path(
            asset.asset_type, asset.original_path, target_campaign.root
        )
        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(asset.absolute_path, target_path)
            replacements[original] = relative
        except Exception as exc:
            log_warning(
                f"Failed to copy asset {asset.absolute_path}: {exc}",
                func_name="modules.generic.cross_campaign_asset_service.apply_direct_copy",
            )
        _call_progress(progress_callback, f"Copying assets ({index}/{total_assets})", index / total_assets)

    for entity_type, records in selected_records.items():
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

    if world_map_entries:
        rewritten_world_maps = _rewrite_world_map_entries(world_map_entries, replacements)
        _merge_world_map_entries(target_campaign.root, rewritten_world_maps)

    _call_progress(progress_callback, "Copy complete", 1.0)
    return summary


def _rewrite_record_paths(entity_type: str, record: dict, replacements: Dict[str, str]) -> dict:
    updated = copy.deepcopy(record)

    if entity_type in PORTRAIT_ENTITY_TYPES:
        portraits = parse_portrait_value(updated.get("Portrait"))
        if portraits:
            rewritten = [replacements.get(path, path) for path in portraits]
            updated["Portrait"] = serialize_portrait_value(rewritten)

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
