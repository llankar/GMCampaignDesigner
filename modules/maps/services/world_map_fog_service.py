import io
import os
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageTk

from modules.helpers.config_helper import ConfigHelper
from modules.helpers.logging_helper import log_warning
from modules.maps.services.fog_manager import apply_fog_rectangle


def init_world_map_fog(panel) -> None:
    panel.fog_mode = None
    panel.brush_size = 32
    panel.brush_size_options = list(range(4, 129, 4))
    panel.brush_shape = "rectangle"
    panel.mask_img = None
    panel.mask_tk = None
    panel.mask_id = None
    panel.fog_history = []
    panel._fog_history_bytes = 0
    panel._fog_action_active = False
    panel._fog_rect_start_world = None
    panel._fog_rect_preview_id = None
    panel._fast_resample = Image.BILINEAR


def _fog_mask_records(panel):
    record = panel.maps_wrapper_data.get(panel.current_map_name) if panel.current_map_name else None
    entry = panel.current_world_map if isinstance(panel.current_world_map, dict) else {}
    return record, entry


def _resolve_fog_mask_path(panel) -> str:
    record, entry = _fog_mask_records(panel)
    fog_rel = ""
    if isinstance(record, dict):
        fog_rel = str(record.get("FogMaskPath") or "").strip()
    if not fog_rel and isinstance(entry, dict):
        fog_rel = str(entry.get("fog_mask_path") or "").strip()
    if not fog_rel:
        return ""
    return fog_rel if os.path.isabs(fog_rel) else os.path.join(ConfigHelper.get_campaign_dir(), fog_rel)


def _mask_base_name(panel) -> str:
    record, entry = _fog_mask_records(panel)
    image_path = ""
    if isinstance(record, dict):
        image_path = str(record.get("Image") or "").strip()
    if not image_path and isinstance(entry, dict):
        image_path = str(entry.get("image") or "").strip()
    if image_path:
        base = os.path.splitext(os.path.basename(image_path))[0]
        if base:
            return base
    name = panel.current_map_name or "world_map"
    sanitized = re.sub(r"[^A-Za-z0-9_-]+", "_", name).strip("_")
    return sanitized or "world_map"


def load_world_map_fog(panel) -> None:
    if not panel.base_image or not panel.current_map_name:
        panel.mask_img = None
        panel.mask_tk = None
        panel.mask_id = None
        return

    fog_path = _resolve_fog_mask_path(panel)
    fog_img = None
    if fog_path and os.path.exists(fog_path):
        try:
            fog_img = Image.open(fog_path).convert("RGBA")
        except Exception:
            fog_img = None

    if fog_img is None:
        fog_img = Image.new("RGBA", panel.base_image.size, (0, 0, 0, 128))
    elif fog_img.size != panel.base_image.size:
        fog_img = fog_img.resize(panel.base_image.size, Image.LANCZOS)

    panel.mask_img = fog_img
    panel.mask_tk = None
    panel.mask_id = None
    panel.fog_history = []
    panel._fog_history_bytes = 0
    panel._fog_action_active = False
    panel._fog_rect_start_world = None
    panel._fog_rect_preview_id = None


def save_world_map_fog(panel) -> None:
    if not panel.current_map_name or panel.mask_img is None:
        return

    campaign_dir = ConfigHelper.get_campaign_dir()
    if not campaign_dir:
        return

    masks_dir = Path(campaign_dir) / "masks"
    masks_dir.mkdir(parents=True, exist_ok=True)
    mask_filename = f"{_mask_base_name(panel)}_mask.png"
    abs_mask_path = masks_dir / mask_filename
    rel_mask_path = (Path("masks") / mask_filename).as_posix()

    try:
        panel.mask_img.save(abs_mask_path, format="PNG")
    except Exception as exc:
        log_warning(f"Failed to save fog mask: {exc}", func_name="world_map_fog_service.save_world_map_fog")
        return

    record, entry = _fog_mask_records(panel)
    if isinstance(record, dict):
        record["FogMaskPath"] = rel_mask_path
        panel.maps_wrapper_data[panel.current_map_name] = record
        try:
            panel.maps_wrapper.save_item(record, key_field="Name")
        except Exception as exc:
            log_warning(f"Failed to persist fog mask path to map record: {exc}")

    if isinstance(entry, dict):
        entry["fog_mask_path"] = rel_mask_path
        panel.current_world_map = entry
        panel.world_maps[panel.current_map_name] = entry
        panel._save_world_map_store()


def _fog_event_to_world(panel, event):
    if not panel.render_params:
        return None
    scale, offset_x, offset_y, _, _ = panel.render_params
    if scale == 0:
        return None
    return (event.x - offset_x) / scale, (event.y - offset_y) / scale


def update_world_map_fog_canvas(panel, *, resample=None) -> None:
    if not panel.mask_img or not panel.render_params:
        return
    canvas = getattr(panel, "canvas", None)
    if not canvas or not canvas.winfo_exists():
        return

    scale, offset_x, offset_y, base_w, base_h = panel.render_params
    sw, sh = int(base_w * scale), int(base_h * scale)
    if sw <= 0 or sh <= 0:
        return

    resample = resample or getattr(panel, "_fast_resample", Image.BILINEAR)
    mask_resized = panel.mask_img.resize((sw, sh), resample=resample)
    panel.mask_tk = ImageTk.PhotoImage(mask_resized)

    if panel.mask_id:
        try:
            canvas.itemconfig(panel.mask_id, image=panel.mask_tk)
            canvas.coords(panel.mask_id, offset_x, offset_y)
        except Exception:
            panel.mask_id = None

    if not panel.mask_id:
        panel.mask_id = canvas.create_image(offset_x, offset_y, image=panel.mask_tk, anchor="nw")

    panel._update_player_display()


def clear_world_map_fog(panel) -> None:
    if not panel.base_image:
        return
    panel.mask_img = Image.new("RGBA", panel.base_image.size, (0, 0, 0, 0))
    update_world_map_fog_canvas(panel, resample=Image.LANCZOS)


def reset_world_map_fog(panel) -> None:
    if not panel.base_image:
        return
    panel.mask_img = Image.new("RGBA", panel.base_image.size, (0, 0, 0, 128))
    update_world_map_fog_canvas(panel, resample=Image.LANCZOS)


def paint_world_map_fog(panel, event) -> None:
    if panel.fog_mode not in ("add", "rem"):
        return
    if panel.mask_img is None:
        return
    coords = _fog_event_to_world(panel, event)
    if coords is None:
        return
    xw, yw = coords

    half = panel.brush_size / 2
    left = int(xw - half)
    top = int(yw - half)
    right = int(xw + half)
    bottom = int(yw + half)

    draw = ImageDraw.Draw(panel.mask_img)
    draw_color = (0, 0, 0, 128) if panel.fog_mode == "add" else (0, 0, 0, 0)
    if panel.brush_shape == "circle":
        draw.ellipse((left, top, right, bottom), fill=draw_color)
    else:
        draw.rectangle((left, top, right, bottom), fill=draw_color)

    update_world_map_fog_canvas(panel, resample=getattr(panel, "_fast_resample", Image.BILINEAR))


def update_fog_rectangle_preview(panel, event) -> None:
    if panel._fog_rect_start_world is None or panel.render_params is None:
        return
    coords = _fog_event_to_world(panel, event)
    if coords is None:
        return
    canvas = getattr(panel, "canvas", None)
    if not canvas or not canvas.winfo_exists():
        return

    scale, offset_x, offset_y, _, _ = panel.render_params
    start_world_x, start_world_y = panel._fog_rect_start_world
    current_world_x, current_world_y = coords

    left_world = min(start_world_x, current_world_x)
    right_world = max(start_world_x, current_world_x)
    top_world = min(start_world_y, current_world_y)
    bottom_world = max(start_world_y, current_world_y)

    screen_left = offset_x + left_world * scale
    screen_right = offset_x + right_world * scale
    screen_top = offset_y + top_world * scale
    screen_bottom = offset_y + bottom_world * scale

    outline_color = "#d7263d" if panel.fog_mode == "add_rect" else "#00a2ff"
    if panel._fog_rect_preview_id and canvas.type(panel._fog_rect_preview_id):
        canvas.coords(panel._fog_rect_preview_id, screen_left, screen_top, screen_right, screen_bottom)
        canvas.itemconfig(panel._fog_rect_preview_id, outline=outline_color)
    else:
        panel._fog_rect_preview_id = canvas.create_rectangle(
            screen_left,
            screen_top,
            screen_right,
            screen_bottom,
            outline=outline_color,
            width=2,
            dash=(3, 3),
            tags=("fog_preview",),
        )
    canvas.tag_raise(panel._fog_rect_preview_id)


def clear_fog_rectangle_preview(panel) -> None:
    canvas = getattr(panel, "canvas", None)
    if canvas and canvas.winfo_exists():
        canvas.delete("fog_preview")
    panel._fog_rect_preview_id = None


def push_fog_history(panel) -> None:
    if panel.mask_img is None:
        return

    buffer = io.BytesIO()
    try:
        panel.mask_img.save(buffer, format="PNG")
    except Exception as exc:
        log_warning(f"Failed to snapshot fog history: {exc}")
        return

    payload = buffer.getvalue()
    if not payload:
        return

    panel.fog_history.append(payload)
    panel._fog_history_bytes += len(payload)

    max_budget = fog_history_budget_bytes(panel)
    while panel.fog_history and panel._fog_history_bytes > max_budget:
        dropped = panel.fog_history.pop(0)
        panel._fog_history_bytes -= len(dropped)


def fog_history_budget_bytes(panel) -> int:
    if panel.mask_img is None:
        return 0
    pixel_count = max(1, panel.mask_img.width * panel.mask_img.height)
    min_budget = 4 * 1024 * 1024
    max_budget = 24 * 1024 * 1024
    estimated = pixel_count
    return max(min_budget, min(max_budget, estimated))


def undo_world_map_fog(panel, _event=None) -> None:
    if not panel.fog_history:
        return

    payload = panel.fog_history.pop()
    panel._fog_history_bytes -= len(payload)
    panel._fog_history_bytes = max(0, panel._fog_history_bytes)

    try:
        with Image.open(io.BytesIO(payload)) as restored:
            restored_img = restored.convert("RGBA")
    except Exception as exc:
        log_warning(f"Failed to restore fog history: {exc}")
        return

    if panel.base_image and restored_img.size != panel.base_image.size:
        restored_img = restored_img.resize(panel.base_image.size, Image.LANCZOS)
    panel.mask_img = restored_img
    update_world_map_fog_canvas(panel, resample=Image.LANCZOS)


def apply_world_map_fog_rectangle(panel, start_world, end_world) -> None:
    if panel.mask_img is None:
        return
    if start_world is None or end_world is None:
        return
    start_world_x, start_world_y = start_world
    end_world_x, end_world_y = end_world
    apply_fog_rectangle(
        panel,
        (
            int(round(start_world_x)),
            int(round(start_world_y)),
            int(round(end_world_x)),
            int(round(end_world_y)),
        ),
        panel.fog_mode,
    )
    update_world_map_fog_canvas(panel, resample=Image.LANCZOS)
