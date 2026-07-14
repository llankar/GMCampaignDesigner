"""Reusable SwarmUI portrait generation for scenario portrait workflows."""
from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from typing import Any, Callable

import customtkinter as ctk
from PIL import Image
import requests

from modules.generic.portrait_manager.entity_portrait_actions import (
    ScenarioPortraitEntity,
    copy_portrait_to_campaign,
)
from modules.helpers import text_helpers
from modules.helpers.config_helper import ConfigHelper
from modules.helpers.filename_helper import safe_filename_component


SWARM_API_URL = "http://127.0.0.1:7801"
NEGATIVE_PROMPT = (
    "blurry, low quality, comics style, mangastyle, paint style, watermark, "
    "ugly, monstrous, too many fingers, too many legs, too many arms, bad hands, "
    "unrealistic weapons, bad grip on equipment, nude"
)

SWARMUI_PROCESS = None


@dataclass(frozen=True)
class SwarmUIPortraitSettings:
    """SwarmUI generation settings selected by the user."""

    model: str
    image_count: int
    cfgscale: float


@dataclass(frozen=True)
class GeneratedPortraitResult:
    """Paths produced by a successful portrait generation."""

    portrait_paths: list[str]
    generated_asset_paths: list[str]


def launch_swarmui() -> None:
    """Launch SwarmUI when it is not already running."""
    global SWARMUI_PROCESS
    swarmui_path = ConfigHelper.get("Paths", "swarmui_path", fallback=r"E:\SwarmUI\SwarmUI")
    swarmui_cmd = os.path.join(swarmui_path, "launch-windows.bat")
    env = os.environ.copy()
    env.pop("VIRTUAL_ENV", None)
    if SWARMUI_PROCESS is None or SWARMUI_PROCESS.poll() is not None:
        SWARMUI_PROCESS = subprocess.Popen(
            swarmui_cmd,
            shell=True,
            cwd=swarmui_path,
            env=env,
        )
        time.sleep(120.0)


def build_portrait_prompt(
    entity: ScenarioPortraitEntity,
    template: dict[str, Any] | None = None,
    *,
    prompt_fields: list[str] | None = None,
) -> str:
    """Build a SwarmUI prompt from an entity record and its template fields."""
    fields = prompt_fields or _default_prompt_fields(entity, template)
    parts: list[str] = []
    for field_name in fields:
        if field_name == "Portrait":
            continue
        value = entity.record.get(field_name)
        if value in (None, ""):
            continue
        if isinstance(value, str):
            text = text_helpers.format_longtext(value).strip()
        else:
            text = text_helpers.format_longtext(value).strip()
        if text:
            parts.append(text)
    return " ".join(parts) or entity.name or "fantasy portrait"


def generate_scenario_portrait(
    parent,
    entity: ScenarioPortraitEntity,
    settings: SwarmUIPortraitSettings,
    *,
    template: dict[str, Any] | None = None,
    prompt_fields: list[str] | None = None,
    on_generated: Callable[[GeneratedPortraitResult], None] | None = None,
) -> GeneratedPortraitResult | None:
    """Generate, select, and persist generated portrait assets for a scenario entity.

    Returns campaign-relative portrait paths suitable for ``set_entity_portraits``.
    """
    session_id = _get_swarm_session_id()
    prompt = build_portrait_prompt(entity, template, prompt_fields=prompt_fields)
    image_paths = _request_swarm_images(session_id, prompt, settings)
    image_bytes = _download_generated_images(image_paths)
    if not image_bytes:
        raise RuntimeError("Failed to download generated images.")

    thumbs = [_make_thumbnail(content) for content in image_bytes]
    chosen_index = show_image_selection_window(parent, thumbs)
    if chosen_index is None:
        return None
    if chosen_index < 0 or chosen_index >= len(image_bytes):
        return None

    portrait_path, generated_path = _store_selected_portrait(entity, image_bytes[chosen_index])
    result = GeneratedPortraitResult(
        portrait_paths=[portrait_path],
        generated_asset_paths=[generated_path] if generated_path else [],
    )
    if callable(on_generated):
        on_generated(result)
    return result


def _default_prompt_fields(
    entity: ScenarioPortraitEntity,
    template: dict[str, Any] | None,
) -> list[str]:
    preferred = [
        "Description",
        "Role",
        "Title",
        "Archetype",
        "Factions",
        "Objects",
        "Personality",
        "Traits",
        "Background",
        "Motivation",
        "CurrentObjective",
        "Scheme",
        "Notes",
    ]
    template_names = [
        str(field.get("name"))
        for field in (template or {}).get("fields", [])
        if isinstance(field, dict) and field.get("name")
    ]
    selected = [name for name in preferred if name in entity.record]
    selected.extend(name for name in template_names if name not in selected and name in entity.record)
    key_field = entity.key_field
    if key_field in entity.record and key_field not in selected:
        selected.insert(0, key_field)
    elif "Name" in entity.record and "Name" not in selected:
        selected.insert(0, "Name")
    return selected


def _get_swarm_session_id() -> str:
    session_url = f"{SWARM_API_URL}/API/GetNewSession"
    response = requests.post(session_url, json={}, headers={"Content-Type": "application/json"})
    response.raise_for_status()
    session_id = response.json().get("session_id")
    if not session_id:
        raise RuntimeError("Failed to obtain session ID from Swarm API.")
    return session_id


def _request_swarm_images(
    session_id: str,
    prompt: str,
    settings: SwarmUIPortraitSettings,
) -> list[str]:
    prompt_data = {
        "session_id": session_id,
        "images": settings.image_count,
        "prompt": prompt,
        "negativeprompt": NEGATIVE_PROMPT,
        "model": settings.model,
        "width": 1024,
        "height": 1024,
        "cfgscale": settings.cfgscale,
        "steps": 20,
        "seed": -1,
    }
    generate_url = f"{SWARM_API_URL}/API/GenerateText2Image"
    response = requests.post(generate_url, json=prompt_data, headers={"Content-Type": "application/json"})
    response.raise_for_status()
    images = response.json().get("images")
    if not images:
        raise RuntimeError("Image generation failed. Check API response.")
    return list(images)


def _download_generated_images(image_paths: list[str]) -> list[bytes]:
    images_bytes: list[bytes] = []
    for rel_path in image_paths:
        try:
            response = requests.get(f"{SWARM_API_URL}/{rel_path}")
            response.raise_for_status()
            images_bytes.append(response.content)
        except Exception:
            continue
    return images_bytes


def _make_thumbnail(content: bytes) -> Image.Image:
    image = Image.open(BytesIO(content)).convert("RGB")
    thumb = image.copy()
    thumb.thumbnail((256, 256))
    return thumb


def _store_selected_portrait(entity: ScenarioPortraitEntity, content: bytes) -> tuple[str, str]:
    campaign_dir = Path(ConfigHelper.get_campaign_dir())
    generated_folder = campaign_dir / "assets" / "generated"
    generated_folder.mkdir(parents=True, exist_ok=True)
    output_filename = f"{safe_filename_component(entity.name, fallback='Unknown')}_portrait_{time.time_ns()}.png"
    generated_path = generated_folder / output_filename

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_file:
        temp_file.write(content)
        temp_path = temp_file.name

    try:
        portrait_path = copy_portrait_to_campaign(temp_path, entity.name)
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


def show_image_selection_window(parent, pil_images: list[Image.Image]) -> int | None:
    """Display generated portrait thumbnails and return the selected index."""
    if not pil_images:
        return None

    top = ctk.CTkToplevel(parent)
    top.title("Choose a Portrait")
    top.transient(parent)
    top.grab_set()

    container = ctk.CTkFrame(top)
    container.pack(padx=10, pady=10, fill="both", expand=True)

    ctk_images = []
    selected = {"idx": None}

    def on_choose(index: int) -> None:
        selected["idx"] = index
        top.destroy()

    cols = min(5, max(1, len(pil_images)))
    for index, image in enumerate(pil_images):
        ctk_image = ctk.CTkImage(light_image=image, size=(180, 180))
        ctk_images.append(ctk_image)
        button = ctk.CTkButton(
            container,
            image=ctk_image,
            text=f"#{index + 1}",
            compound="top",
            width=188,
            height=214,
            command=lambda idx=index: on_choose(idx),
        )
        button.grid(row=index // cols, column=index % cols, padx=6, pady=6, sticky="nsew")

    def cancel() -> None:
        selected["idx"] = None
        top.destroy()

    ctk.CTkButton(top, text="Cancel", command=cancel).pack(pady=5)

    top.update_idletasks()
    rows = (len(pil_images) + cols - 1) // cols
    total_w = cols * (188 + 14) + 40
    total_h = rows * (214 + 14) + 90
    try:
        top.geometry(f"{total_w}x{total_h}")
    except Exception:
        pass

    top.wait_window()
    return selected["idx"]
