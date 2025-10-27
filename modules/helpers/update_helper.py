from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Sequence

import requests
from packaging.version import Version, InvalidVersion

from modules.helpers.logging_helper import (
    log_debug,
    log_exception,
    log_info,
    log_module_import,
    log_warning,
)

ProgressCallback = Callable[[str, float], None]

__all__ = [
    "UpdateCandidate",
    "check_for_update",
    "download_release_asset",
    "prepare_staging_area",
    "launch_installer",
]


@dataclass(frozen=True)
class UpdateCandidate:
    version: Version
    tag: str
    asset_url: str
    asset_name: str
    asset_size: int
    release_notes: str
    channel: str


_REPO = os.environ.get("GMCD_UPDATES_REPO", "llankar/GMCampaignDesigner")
_RELEASES_ENDPOINT = f"https://api.github.com/repos/{_REPO}/releases"
_REQUEST_TIMEOUT = int(os.environ.get("GMCD_UPDATES_TIMEOUT", "30"))
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_VERSION_FILE = _PROJECT_ROOT / "version.txt"
_INSTALL_HELPER = _PROJECT_ROOT / "scripts" / "apply_update.py"
_FROZEN_INSTALL_HELPER_NAME = "RPGCampaignUpdater.exe" if os.name == "nt" else "RPGCampaignUpdater"
_VERSION_PATTERN = re.compile(r"(\d+(?:\.\d+)+)")


def read_installed_version(path: Path = _VERSION_FILE) -> Version:
    if not path.exists():
        raise RuntimeError(f"version manifest not found: {path}")

    text = path.read_text(encoding="utf-8", errors="ignore")
    for line in text.splitlines():
        line = line.strip()
        if "FileVersion" in line or "ProductVersion" in line or line.startswith("filevers="):
            digits = _extract_version_string(line)
            if digits:
                try:
                    version = Version(digits)
                except InvalidVersion as exc:
                    raise RuntimeError(f"Invalid version value '{digits}' in {path}") from exc
                log_debug(
                    f"Detected installed version {version}",
                    func_name="modules.helpers.update_helper.read_installed_version",
                )
                return version
    raise RuntimeError("Unable to locate installed version string in version.txt")


def _extract_version_string(line: str) -> Optional[str]:
    match = _VERSION_PATTERN.search(line)
    if match:
        return match.group(1)
    if "filevers" in line or "prodvers" in line:
        digits = [token.strip() for token in line.split("(")[-1].split(")")[0].split(",") if token.strip().isdigit()]
        if digits:
            return ".".join(digits)
    return None


def check_for_update(
    *,
    channel: str = "stable",
    preferred_asset: Optional[str] = None,
    session: Optional[requests.Session] = None,
) -> tuple[Version, Optional[UpdateCandidate]]:
    current_version = read_installed_version()
    close_session = False
    if session is None:
        session = requests.Session()
        close_session = True
    session.headers.setdefault("User-Agent", "GMCampaignDesigner-Updater")
    session.headers.setdefault("Accept", "application/vnd.github+json")

    try:
        response = session.get(_RELEASES_ENDPOINT, timeout=_REQUEST_TIMEOUT)
        response.raise_for_status()
    except Exception as exc:
        log_warning(
            f"Unable to fetch releases: {exc}",
            func_name="modules.helpers.update_helper.check_for_update",
        )
        raise
    finally:
        if close_session:
            session.close()

    releases = response.json()
    if not isinstance(releases, list):
        raise RuntimeError("Unexpected response payload from releases API")

    for release in releases:
        if not isinstance(release, dict):
            continue
        if release.get("draft"):
            continue
        if channel.lower() == "stable" and release.get("prerelease"):
            continue
        tag_name = release.get("tag_name") or ""
        try:
            candidate_version = _normalize_tag(tag_name)
        except Exception as exc:
            log_warning(
                f"Skipping release with invalid tag '{tag_name}': {exc}",
                func_name="modules.helpers.update_helper.check_for_update",
            )
            continue
        if candidate_version <= current_version:
            log_debug(
                f"Ignoring release {candidate_version} (not newer)",
                func_name="modules.helpers.update_helper.check_for_update",
            )
            continue

        assets = release.get("assets") or []
        asset = _select_asset(assets, preferred_asset)
        if not asset:
            log_warning(
                f"Release {tag_name} has no downloadable assets",
                func_name="modules.helpers.update_helper.check_for_update",
            )
            continue
        asset_url = asset.get("browser_download_url")
        asset_name = asset.get("name") or ""
        if not asset_url or not asset_name:
            log_warning(
                f"Release {tag_name} asset missing download metadata",
                func_name="modules.helpers.update_helper.check_for_update",
            )
            continue
        size = asset.get("size")
        asset_size = int(size) if isinstance(size, int) else int(size or 0)
        candidate = UpdateCandidate(
            version=candidate_version,
            tag=tag_name,
            asset_url=asset_url,
            asset_name=asset_name,
            asset_size=asset_size,
            release_notes=release.get("body") or "",
            channel=channel,
        )
        log_info(
            f"Found update candidate {candidate.version} (asset {candidate.asset_name})",
            func_name="modules.helpers.update_helper.check_for_update",
        )
        return current_version, candidate

    log_info(
        "No newer releases available",
        func_name="modules.helpers.update_helper.check_for_update",
    )
    return current_version, None


def download_release_asset(
    candidate: UpdateCandidate,
    staging_root: Path | str,
    *,
    progress_callback: Optional[ProgressCallback] = None,
    session: Optional[requests.Session] = None,
    chunk_size: int = 1 << 20,
) -> Path:
    root = Path(staging_root)
    root.mkdir(parents=True, exist_ok=True)
    archive_path = root / candidate.asset_name
    close_session = False
    if session is None:
        session = requests.Session()
        close_session = True
    session.headers.setdefault("User-Agent", "GMCampaignDesigner-Updater")

    log_info(
        f"Downloading update asset {candidate.asset_name}",
        func_name="modules.helpers.update_helper.download_release_asset",
    )
    try:
        response = session.get(candidate.asset_url, stream=True, timeout=_REQUEST_TIMEOUT)
        response.raise_for_status()
    except Exception as exc:
        log_warning(
            f"Failed to download asset: {exc}",
            func_name="modules.helpers.update_helper.download_release_asset",
        )
        raise

    total = candidate.asset_size or int(response.headers.get("Content-Length", 0))
    downloaded = 0
    with archive_path.open("wb") as handle:
        for chunk in response.iter_content(chunk_size=chunk_size):
            if not chunk:
                continue
            handle.write(chunk)
            downloaded += len(chunk)
            fraction = downloaded / total if total else 0.0
            _emit_progress(
                progress_callback,
                f"Downloading {candidate.asset_name}",
                fraction,
            )
    _emit_progress(progress_callback, "Download complete", 1.0 if total else 0.0)

    if close_session:
        session.close()
    return archive_path


def prepare_staging_area(
    candidate: UpdateCandidate,
    *,
    progress_callback: Optional[ProgressCallback] = None,
    session: Optional[requests.Session] = None,
) -> tuple[Path, Path]:
    staging_root = Path(tempfile.mkdtemp(prefix="gmcampaign_stage_"))
    archive_path = download_release_asset(
        candidate,
        staging_root,
        progress_callback=progress_callback,
        session=session,
    )
    payload_root = staging_root / "payload"
    payload_root.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path) as archive:
        members = archive.infolist()
        total = len(members) or 1
        for index, member in enumerate(members, start=1):
            archive.extract(member, payload_root)
            _emit_progress(
                progress_callback,
                f"Extracting files ({index}/{total})",
                index / total,
            )
    return staging_root, _collapse_root(payload_root)


def launch_installer(
    payload_root: Path | str,
    *,
    install_root: Optional[Path | str] = None,
    restart_target: Optional[str] = None,
    wait_for_pid: Optional[int] = None,
    preserve: Optional[Sequence[str]] = None,
    cleanup_root: Optional[Path | str | Sequence[Path | str]] = None,
) -> subprocess.Popen:
    frozen = getattr(sys, "frozen", False)

    install_dir = Path(install_root) if install_root is not None else _PROJECT_ROOT
    cleanup_roots: list[str] = []
    if cleanup_root:
        if isinstance(cleanup_root, (str, os.PathLike)):
            cleanup_roots.append(str(Path(cleanup_root)))
        else:
            cleanup_roots.extend(str(Path(entry)) for entry in cleanup_root)
    if frozen:
        helper_path = Path(sys.executable).with_name(_FROZEN_INSTALL_HELPER_NAME)
        if not helper_path.exists():
            raise FileNotFoundError(f"Expected frozen installer helper at {helper_path}")
        temp_dir = Path(tempfile.mkdtemp(prefix="gmcd-update-helper-"))
        temp_helper_path = temp_dir / helper_path.name
        try:
            shutil.copy2(helper_path, temp_helper_path)
        except Exception:
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise
        cleanup_roots.append(str(temp_dir))
        args = [str(temp_helper_path)]
    else:
        if not _INSTALL_HELPER.exists():
            raise FileNotFoundError(f"Expected installer helper at {_INSTALL_HELPER}")
        args = [sys.executable, str(_INSTALL_HELPER)]

    args.extend(
        [
            "--source",
            str(Path(payload_root)),
            "--target",
            str(install_dir),
        ]
    )
    if wait_for_pid is None:
        wait_for_pid = os.getpid()
    if wait_for_pid:
        args.extend(["--wait-for-pid", str(wait_for_pid)])
    if restart_target:
        args.extend(["--restart-target", restart_target])
    if preserve:
        for entry in preserve:
            args.extend(["--preserve", entry])
    for root in cleanup_roots:
        args.extend(["--cleanup-root", root])

    log_info(
        f"Launching installer helper: {' '.join(args)}",
        func_name="modules.helpers.update_helper.launch_installer",
    )
    try:
        return subprocess.Popen(args, close_fds=os.name != "nt")
    except Exception as exc:
        log_exception(
            f"Failed to launch installer helper: {exc}",
            func_name="modules.helpers.update_helper.launch_installer",
        )
        raise


def _emit_progress(callback: Optional[ProgressCallback], message: str, fraction: float) -> None:
    if callback:
        try:
            callback(message, max(0.0, min(1.0, float(fraction))))
        except Exception:
            pass


def _normalize_tag(tag: str) -> Version:
    candidate = tag.strip()
    if not candidate:
        raise RuntimeError("Release tag is empty")
    if candidate.lower().startswith("v") and len(candidate) > 1:
        candidate = candidate[1:]
    return Version(candidate)


def _select_asset(assets: Sequence[dict], preferred_asset: Optional[str]) -> Optional[dict]:
    if not assets:
        return None
    if preferred_asset:
        for asset in assets:
            if asset.get("name") == preferred_asset:
                return asset
    for asset in assets:
        name = (asset.get("name") or "").lower()
        if name.endswith(('.zip', '.tar.gz', '.tar.xz')):
            return asset
    return assets[0]


def _collapse_root(root: Path) -> Path:
    entries = [child for child in root.iterdir() if not child.name.startswith("__MACOSX")]
    if len(entries) == 1 and entries[0].is_dir():
        return entries[0]
    return root


log_module_import(__name__)
