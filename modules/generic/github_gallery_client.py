"""Utilities for publishing and retrieving asset bundles via GitHub Releases."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional
from urllib.parse import quote

import requests

from modules.helpers.config_helper import ConfigHelper
from modules.helpers.logging_helper import log_exception, log_info, log_module_import, log_warning
from modules.helpers.secret_helper import decrypt_secret

ProgressCallback = Callable[[str, float], None]

BODY_PREFIX = "GMCD-BUNDLE\n"
DEFAULT_REPO = "llankar/GMCampaignDesigner"
REQUEST_TIMEOUT = 45
DOWNLOAD_CHUNK_SIZE = 1 << 20


@dataclass(frozen=True)
class GalleryBundleSummary:
    """Summary metadata for a published bundle."""

    release_id: int
    asset_id: int
    release_name: str
    tag: str
    asset_name: str
    download_url: str
    size: int
    published_at: Optional[datetime]
    author: str
    description: str
    entity_counts: Dict[str, int]
    source_campaign: str
    manifest_created_at: str
    metadata: Dict[str, object]
    html_url: str
    is_draft: bool
    asset_count: int
    asset_download_count: int

    @property
    def display_title(self) -> str:
        return self.release_name or self.tag or self.asset_name

    @property
    def is_full_campaign(self) -> bool:
        metadata = self.metadata if isinstance(self.metadata, dict) else {}
        mode = str(metadata.get("bundle_mode") or "").lower()
        if mode == "full_campaign":
            return True
        database_meta = metadata.get("database")
        return isinstance(database_meta, dict) and bool(database_meta)


class GithubGalleryClient:
    """Client that wraps GitHub's release API for bundle distribution."""

    def __init__(self, repo: Optional[str] = None, token: Optional[str] = None, timeout: Optional[int] = None):
        repo_config = (ConfigHelper.get("Gallery", "github_repo", fallback="") or "").strip()
        repo_env = os.environ.get("GMCD_GALLERY_REPO", "").strip()
        token_config_raw = (ConfigHelper.get("Gallery", "github_token", fallback="") or "").strip()
        token_config = decrypt_secret(token_config_raw)
        token_env = os.environ.get("GMCD_GALLERY_TOKEN", "").strip()

        self._repo = repo or repo_config or repo_env or DEFAULT_REPO
        self._token = token or token_config or token_env or None
        self._timeout = timeout or int(os.environ.get("GMCD_GALLERY_TIMEOUT", str(REQUEST_TIMEOUT)))
        self._api_base = "https://api.github.com"
        self._upload_base = "https://uploads.github.com"

    # ------------------------------------------------------------------ Props
    @property
    def repo(self) -> str:
        return self._repo

    @property
    def can_publish(self) -> bool:
        return bool(self._token)

    @property
    def timeout(self) -> int:
        return self._timeout

    # --------------------------------------------------------- Credentials
    def set_token(self, token: Optional[str]) -> None:
        if token is not None:
            self._token = token or None
            return

        token_config_raw = (ConfigHelper.get("Gallery", "github_token", fallback="") or "").strip()
        token_config = decrypt_secret(token_config_raw)
        token_env = os.environ.get("GMCD_GALLERY_TOKEN", "").strip()
        self._token = token_config or token_env or None

    # ----------------------------------------------------------------- Session
    def _create_session(self, *, auth: bool = False) -> requests.Session:
        session = requests.Session()
        session.headers.setdefault("User-Agent", "GMCampaignDesigner-Gallery")
        session.headers.setdefault("Accept", "application/vnd.github+json")
        if auth:
            if not self._token:
                raise RuntimeError("GitHub token not configured for gallery publishing.")
            session.headers["Authorization"] = f"Bearer {self._token}"
        elif self._token:
            session.headers.setdefault("Authorization", f"Bearer {self._token}")
        return session

    # ------------------------------------------------------------ List bundles
    def list_bundles(self, *, include_drafts: bool = False) -> List[GalleryBundleSummary]:
        if not self._repo:
            raise RuntimeError("GitHub repository for gallery is not configured.")

        session = self._create_session()
        try:
            params = {"per_page": 100}
            response = session.get(
                f"{self._api_base}/repos/{self._repo}/releases",
                params=params,
                timeout=self._timeout,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception:
            log_exception(
                "Failed to fetch releases for online gallery.",
                func_name="modules.generic.github_gallery_client.GithubGalleryClient.list_bundles",
            )
            raise
        finally:
            session.close()

        if not isinstance(payload, list):
            raise RuntimeError("Unexpected response payload from GitHub releases API")

        results: List[GalleryBundleSummary] = []
        for release in payload:
            if not isinstance(release, dict):
                continue
            if release.get("draft") and not include_drafts:
                continue
            asset = self._select_asset(release)
            if not asset:
                continue
            metadata = self._parse_metadata(release.get("body"))
            try:
                summary = self._build_summary(release, asset, metadata)
            except Exception as exc:
                log_warning(
                    f"Skipping release {release.get('id')} due to parse error: {exc}",
                    func_name="modules.generic.github_gallery_client.GithubGalleryClient.list_bundles",
                )
                continue
            results.append(summary)

        results.sort(key=lambda item: item.published_at or datetime.min, reverse=True)
        log_info(
            f"Fetched {len(results)} gallery releases from {self._repo}",
            func_name="modules.generic.github_gallery_client.GithubGalleryClient.list_bundles",
        )
        return results

    # ----------------------------------------------------------- Downloading
    def download_bundle(
        self,
        bundle: GalleryBundleSummary,
        destination: Path,
        *,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> Path:
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)

        session = self._create_session()
        try:
            if progress_callback:
                progress_callback(f"Downloading {bundle.asset_name}…", 0.0)
            with session.get(bundle.download_url, stream=True, timeout=self._timeout) as response:
                response.raise_for_status()
                total = int(response.headers.get("Content-Length") or 0)
                downloaded = 0
                with destination.open("wb") as handle:
                    for chunk in response.iter_content(chunk_size=DOWNLOAD_CHUNK_SIZE):
                        if not chunk:
                            continue
                        handle.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback and total:
                            fraction = min(downloaded / total, 1.0)
                            progress_callback(
                                f"Downloading {bundle.asset_name}…",
                                fraction * 0.98,
                            )
            if progress_callback:
                progress_callback("Download complete.", 1.0)
            return destination
        except Exception:
            log_exception(
                f"Failed to download bundle asset {bundle.asset_id} from release {bundle.release_id}.",
                func_name="modules.generic.github_gallery_client.GithubGalleryClient.download_bundle",
            )
            raise
        finally:
            session.close()

    # ------------------------------------------------------------- Publishing
    def publish_bundle(
        self,
        archive_path: Path,
        manifest: dict,
        *,
        title: str,
        description: str = "",
        progress_callback: Optional[ProgressCallback] = None,
    ) -> GalleryBundleSummary:
        archive_path = Path(archive_path)
        if not archive_path.exists():
            raise FileNotFoundError(archive_path)
        session = self._create_session(auth=True)
        metadata = self._metadata_from_manifest(manifest, title, description)
        tag_slug = _slugify(title or archive_path.stem)
        tag_name = f"bundle-{tag_slug}-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
        payload = {
            "tag_name": tag_name,
            "name": title,
            "body": self._serialize_body(metadata),
            "draft": False,
            "prerelease": False,
        }

        try:
            if progress_callback:
                progress_callback("Creating GitHub release…", 0.85)
            response = session.post(
                f"{self._api_base}/repos/{self._repo}/releases",
                json=payload,
                timeout=self._timeout,
            )
            response.raise_for_status()
            release = response.json()
            upload_url = release.get("upload_url")
            if not upload_url:
                raise RuntimeError("Release response missing upload_url")
            upload_base = upload_url.split("{")[0]
            upload_endpoint = f"{upload_base}?name={quote(archive_path.name)}"
            headers = {"Content-Type": "application/zip"}
            if progress_callback:
                progress_callback("Uploading bundle archive…", 0.9)
            with archive_path.open("rb") as handle:
                upload_response = session.post(
                    upload_endpoint,
                    data=handle,
                    headers=headers,
                    timeout=self._timeout,
                )
            upload_response.raise_for_status()
            asset = upload_response.json()
            release.setdefault("assets", []).append(asset)
            if progress_callback:
                progress_callback("Release published.", 1.0)
            summary = self._build_summary(release, asset, metadata)
            log_info(
                f"Published gallery bundle '{summary.display_title}' as {summary.tag}",
                func_name="modules.generic.github_gallery_client.GithubGalleryClient.publish_bundle",
            )
            return summary
        except Exception:
            log_exception(
                f"Failed to publish bundle {archive_path.name} to GitHub releases.",
                func_name="modules.generic.github_gallery_client.GithubGalleryClient.publish_bundle",
            )
            raise
        finally:
            session.close()

    # --------------------------------------------------------------- Deletion
    def delete_bundle(
        self,
        bundle: GalleryBundleSummary,
        *,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> None:
        session = self._create_session(auth=True)
        try:
            if progress_callback:
                progress_callback("Removing release asset…", 0.5)
            asset_url = f"{self._api_base}/repos/{self._repo}/releases/assets/{bundle.asset_id}"
            asset_response = session.delete(asset_url, timeout=self._timeout)
            if asset_response.status_code not in (204, 404):
                asset_response.raise_for_status()
            if progress_callback:
                progress_callback("Removing release…", 0.9)
            release_url = f"{self._api_base}/repos/{self._repo}/releases/{bundle.release_id}"
            release_response = session.delete(release_url, timeout=self._timeout)
            if release_response.status_code not in (204, 404):
                release_response.raise_for_status()
            if progress_callback:
                progress_callback("Bundle removed.", 1.0)
            log_info(
                f"Deleted gallery bundle {bundle.display_title} (release {bundle.release_id}).",
                func_name="modules.generic.github_gallery_client.GithubGalleryClient.delete_bundle",
            )
        except Exception:
            log_exception(
                f"Failed to delete gallery bundle {bundle.display_title}",
                func_name="modules.generic.github_gallery_client.GithubGalleryClient.delete_bundle",
            )
            raise
        finally:
            session.close()

    # ------------------------------------------------------------ Build data
    def _build_summary(
        self,
        release: Dict[str, object],
        asset: Dict[str, object],
        metadata: Dict[str, object],
    ) -> GalleryBundleSummary:
        published_at = self._parse_datetime(
            str(release.get("published_at") or release.get("created_at") or "")
        )
        author = ""
        author_data = release.get("author")
        if isinstance(author_data, dict):
            author = str(author_data.get("login") or "")
        description = ""
        entity_counts: Dict[str, int] = {}
        source_campaign = ""
        manifest_created_at = ""
        if isinstance(metadata, dict):
            description = str(metadata.get("description") or "")
            counts = metadata.get("entity_counts")
            if isinstance(counts, dict):
                entity_counts = {
                    str(key): int(value)
                    for key, value in counts.items()
                    if isinstance(value, (int, float))
                }
            source_data = metadata.get("source_campaign")
            if isinstance(source_data, dict):
                source_campaign = str(source_data.get("name") or "")
            elif isinstance(source_data, str):
                source_campaign = source_data
            manifest_created_at = str(metadata.get("created_at") or "")

        summary = GalleryBundleSummary(
            release_id=int(release.get("id") or 0),
            asset_id=int(asset.get("id") or 0),
            release_name=str(release.get("name") or ""),
            tag=str(release.get("tag_name") or ""),
            asset_name=str(asset.get("name") or ""),
            download_url=str(asset.get("browser_download_url") or ""),
            size=int(asset.get("size") or 0),
            published_at=published_at,
            author=author,
            description=description,
            entity_counts=entity_counts,
            source_campaign=source_campaign,
            manifest_created_at=manifest_created_at,
            metadata=metadata,
            html_url=str(release.get("html_url") or ""),
            is_draft=bool(release.get("draft")),
            asset_count=len(release.get("assets") or []),
            asset_download_count=int(asset.get("download_count") or 0),
        )
        if not summary.download_url:
            raise RuntimeError("Bundle asset missing download URL")
        return summary

    def _parse_metadata(self, body: Optional[str]) -> Dict[str, object]:
        if not body:
            return {}
        text = str(body)
        if text.startswith(BODY_PREFIX):
            payload = text[len(BODY_PREFIX) :].strip()
            try:
                data = json.loads(payload)
                if isinstance(data, dict):
                    return data
            except Exception as exc:
                log_warning(
                    f"Unable to parse gallery metadata JSON: {exc}",
                    func_name="modules.generic.github_gallery_client.GithubGalleryClient._parse_metadata",
                )
        return {}

    def _serialize_body(self, metadata: Dict[str, object]) -> str:
        return BODY_PREFIX + json.dumps(metadata, indent=2, ensure_ascii=False)

    @staticmethod
    def _parse_datetime(value: str) -> Optional[datetime]:
        value = value.strip()
        if not value:
            return None
        try:
            if value.endswith("Z"):
                value = value[:-1] + "+00:00"
            return datetime.fromisoformat(value)
        except Exception:
            return None

    @staticmethod
    def _select_asset(release: Dict[str, object]) -> Optional[Dict[str, object]]:
        assets = release.get("assets")
        if not isinstance(assets, list):
            return None
        for asset in assets:
            if not isinstance(asset, dict):
                continue
            name = str(asset.get("name") or "")
            if name.lower().endswith(".zip"):
                return asset
        return assets[0] if assets else None

    @staticmethod
    def _metadata_from_manifest(manifest: dict, title: str, description: str) -> Dict[str, object]:
        entities_meta = {}
        for entity_type, meta in (manifest.get("entities") or {}).items():
            if isinstance(meta, dict):
                entities_meta[str(entity_type)] = int(meta.get("count") or 0)
        metadata: Dict[str, object] = {
            "title": title,
            "description": description or "",
            "entity_counts": entities_meta,
            "created_at": manifest.get("created_at") or "",
            "source_campaign": manifest.get("source_campaign") or {},
            "bundle_version": manifest.get("version"),
            "asset_count": len(manifest.get("assets") or []),
            "bundle_mode": manifest.get("bundle_mode") or "asset_bundle",
        }
        database_entry = manifest.get("database")
        if isinstance(database_entry, dict):
            metadata["database"] = {
                "file_name": str(database_entry.get("file_name") or ""),
                "size": int(database_entry.get("size") or 0),
            }
        return metadata


def _slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value or "bundle"


log_module_import(__name__)
