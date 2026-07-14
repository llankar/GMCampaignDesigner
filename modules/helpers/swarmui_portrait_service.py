"""UI-independent SwarmUI portrait generation service."""
from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from typing import Any, Protocol

from PIL import Image
import requests

from modules.helpers import text_helpers
from modules.helpers.config_helper import ConfigHelper
from modules.helpers.filename_helper import safe_filename_component

SWARM_API_URL = "http://127.0.0.1:7801"
NEGATIVE_PROMPT = (
    "blurry, low quality, comics style, mangastyle, paint style, watermark, "
    "ugly, monstrous, too many fingers, too many legs, too many arms, bad hands, "
    "unrealistic weapons, bad grip on equipment, nude"
)

_SWARMUI_PROCESS: subprocess.Popen | None = None


class HttpClient(Protocol):
    """Small protocol for mocking SwarmUI HTTP calls in tests."""

    def post(self, url: str, **kwargs): ...
    def get(self, url: str, **kwargs): ...


@dataclass(frozen=True)
class SwarmUIPortraitSettings:
    """SwarmUI generation settings selected by the user."""

    model: str
    image_count: int
    cfgscale: float
    width: int = 1024
    height: int = 1024
    steps: int = 20
    seed: int = -1


@dataclass(frozen=True)
class PortraitGenerationSource:
    """Generic source data used to assemble a portrait prompt and filename."""

    name: str
    record: dict[str, Any]
    key_field: str = "Name"


@dataclass(frozen=True)
class GeneratedPortraitCandidate:
    """A downloaded SwarmUI portrait candidate before user selection."""

    image_bytes: bytes
    thumbnail: Image.Image


@dataclass(frozen=True)
class GeneratedPortraitResult:
    """Paths produced by a successful portrait generation."""

    portrait_paths: list[str]
    generated_asset_paths: list[str]


class SwarmUIPortraitError(RuntimeError):
    """Raised when SwarmUI portrait generation or persistence fails."""


def launch_swarmui(*, startup_delay: float = 120.0) -> None:
    """Launch SwarmUI when it is not already running."""
    global _SWARMUI_PROCESS
    swarmui_path = ConfigHelper.get("Paths", "swarmui_path", fallback=r"E:\SwarmUI\SwarmUI")
    swarmui_cmd = os.path.join(swarmui_path, "launch-windows.bat")
    env = os.environ.copy()
    env.pop("VIRTUAL_ENV", None)
    if _SWARMUI_PROCESS is None or _SWARMUI_PROCESS.poll() is not None:
        _SWARMUI_PROCESS = subprocess.Popen(swarmui_cmd, shell=True, cwd=swarmui_path, env=env)
        if startup_delay > 0:
            time.sleep(startup_delay)


def cleanup_swarmui() -> None:
    """Terminate the SwarmUI process if this service started it."""
    global _SWARMUI_PROCESS
    if _SWARMUI_PROCESS is not None and _SWARMUI_PROCESS.poll() is None:
        _SWARMUI_PROCESS.terminate()


def build_portrait_prompt(
    source: PortraitGenerationSource,
    template: dict[str, Any] | None = None,
    *,
    prompt_fields: list[str] | None = None,
) -> str:
    """Build a reusable SwarmUI portrait prompt from source data."""
    fields = prompt_fields or _default_prompt_fields(source, template)
    parts: list[str] = []
    for field_name in fields:
        if field_name == "Portrait":
            continue
        value = source.record.get(field_name)
        if value in (None, ""):
            continue
        text = text_helpers.format_longtext(value).strip()
        if text:
            parts.append(text)
    return " ".join(parts) or source.name or "fantasy portrait"


def generate_portrait_candidates(
    source: PortraitGenerationSource,
    settings: SwarmUIPortraitSettings,
    *,
    template: dict[str, Any] | None = None,
    prompt_fields: list[str] | None = None,
    http_client: HttpClient = requests,
) -> list[GeneratedPortraitCandidate]:
    """Generate and download SwarmUI portrait candidates without UI side effects."""
    session_id = create_swarm_session(http_client=http_client)
    prompt = build_portrait_prompt(source, template, prompt_fields=prompt_fields)
    image_paths = request_text_to_image(session_id, prompt, settings, http_client=http_client)
    image_bytes = download_generated_images(image_paths, http_client=http_client)
    if not image_bytes:
        raise SwarmUIPortraitError("Failed to download generated images.")
    return [GeneratedPortraitCandidate(content, make_thumbnail(content)) for content in image_bytes]


def create_swarm_session(*, http_client: HttpClient = requests) -> str:
    """Create a SwarmUI API session and return its session id."""
    response = http_client.post(f"{SWARM_API_URL}/API/GetNewSession", json={}, headers={"Content-Type": "application/json"})
    response.raise_for_status()
    session_id = response.json().get("session_id")
    if not session_id:
        raise SwarmUIPortraitError("Failed to obtain session ID from Swarm API.")
    return str(session_id)


def request_text_to_image(
    session_id: str,
    prompt: str,
    settings: SwarmUIPortraitSettings,
    *,
    http_client: HttpClient = requests,
) -> list[str]:
    """Submit a GenerateText2Image request and return generated image paths."""
    payload = {
        "session_id": session_id,
        "images": settings.image_count,
        "prompt": prompt,
        "negativeprompt": NEGATIVE_PROMPT,
        "model": settings.model,
        "width": settings.width,
        "height": settings.height,
        "cfgscale": settings.cfgscale,
        "steps": settings.steps,
        "seed": settings.seed,
    }
    response = http_client.post(f"{SWARM_API_URL}/API/GenerateText2Image", json=payload, headers={"Content-Type": "application/json"})
    response.raise_for_status()
    images = response.json().get("images")
    if not images:
        raise SwarmUIPortraitError("Image generation failed. Check API response.")
    return [str(image) for image in images]


def download_generated_images(image_paths: list[str], *, http_client: HttpClient = requests) -> list[bytes]:
    """Download generated images, skipping individual failed downloads."""
    images_bytes: list[bytes] = []
    for rel_path in image_paths:
        try:
            response = http_client.get(f"{SWARM_API_URL}/{rel_path}")
            response.raise_for_status()
            images_bytes.append(response.content)
        except Exception:
            continue
    return images_bytes


def make_thumbnail(content: bytes, size: tuple[int, int] = (256, 256)) -> Image.Image:
    """Create a PIL thumbnail for a generated image."""
    image = Image.open(BytesIO(content)).convert("RGB")
    thumbnail = image.copy()
    thumbnail.thumbnail(size)
    return thumbnail


def save_generated_portrait_candidate(
    source: PortraitGenerationSource,
    candidate: GeneratedPortraitCandidate,
    *,
    copy_portrait,
) -> GeneratedPortraitResult:
    """Persist a selected candidate to portraits and assets/generated."""
    portrait_path, generated_path = store_generated_portrait_bytes(
        source.name,
        candidate.image_bytes,
        copy_portrait=copy_portrait,
    )
    return GeneratedPortraitResult([portrait_path], [generated_path] if generated_path else [])


def store_generated_portrait_bytes(entity_name: str, content: bytes, *, copy_portrait) -> tuple[str, str]:
    """Copy selected generated bytes to campaign portrait and generated folders."""
    campaign_dir = Path(ConfigHelper.get_campaign_dir())
    generated_folder = campaign_dir / "assets" / "generated"
    generated_folder.mkdir(parents=True, exist_ok=True)
    filename = create_generated_portrait_filename(entity_name)
    generated_path = generated_folder / filename

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_file:
        temp_file.write(content)
        temp_path = temp_file.name

    try:
        portrait_path = copy_portrait(temp_path, entity_name)
        shutil.copy(temp_path, generated_path)
    finally:
        try:
            os.remove(temp_path)
        except OSError:
            pass

    try:
        generated_relative = generated_path.relative_to(campaign_dir).as_posix()
    except ValueError:
        generated_relative = generated_path.as_posix()
    return portrait_path, generated_relative


def create_generated_portrait_filename(entity_name: str, *, suffix: str = ".png") -> str:
    """Create a safe unique filename for a generated portrait."""
    safe_name = safe_filename_component(entity_name, fallback="Unknown")
    return f"{safe_name}_portrait_{time.time_ns()}{suffix}"


def _default_prompt_fields(source: PortraitGenerationSource, template: dict[str, Any] | None) -> list[str]:
    preferred = [
        "Description", "Role", "Title", "Archetype", "Factions", "Objects", "Personality",
        "Traits", "Background", "Motivation", "CurrentObjective", "Scheme", "Notes",
    ]
    template_names = [
        str(field.get("name"))
        for field in (template or {}).get("fields", [])
        if isinstance(field, dict) and field.get("name")
    ]
    selected = [name for name in preferred if name in source.record]
    selected.extend(name for name in template_names if name not in selected and name in source.record)
    if source.key_field in source.record and source.key_field not in selected:
        selected.insert(0, source.key_field)
    elif "Name" in source.record and "Name" not in selected:
        selected.insert(0, "Name")
    return selected
