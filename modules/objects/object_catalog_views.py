import os
from functools import lru_cache
from typing import Callable, Iterable, Optional, Sequence


import customtkinter as ctk
from PIL import Image

from modules.helpers.config_helper import ConfigHelper
from modules.helpers.logging_helper import log_module_import


MERCHANT_HEADER_COLOR = "#2B2B2B"
MERCHANT_HEADER_BORDER = "#3C3C3C"
MERCHANT_BODY_COLOR = "#1E1E1E"
MERCHANT_TEXT_COLOR = "#FFFFFF"
MERCHANT_SUBTEXT_COLOR = "#B4B4B4"
MERCHANT_SECTION_GAP = 8

OBJECT_VIEW_SECTION = "ObjectCatalogView"
OBJECT_VIEW_KEY = "mode"
OBJECT_VIEW_CLASSIC = "classic"
OBJECT_VIEW_ACCORDION = "accordion"


def load_object_catalog_mode() -> str:
    """Return the persisted object catalog display mode."""

    cfg = ConfigHelper.load_campaign_config()
    if cfg.has_section(OBJECT_VIEW_SECTION):
        raw = cfg.get(OBJECT_VIEW_SECTION, OBJECT_VIEW_KEY, fallback="")
        normalized = raw.strip().lower()
        if normalized in {OBJECT_VIEW_CLASSIC, OBJECT_VIEW_ACCORDION}:
            return normalized
    return OBJECT_VIEW_CLASSIC


def save_object_catalog_mode(mode: str) -> None:
    """Persist the object catalog display mode to the campaign settings."""

    mode = (mode or "").strip().lower()
    if mode not in {OBJECT_VIEW_CLASSIC, OBJECT_VIEW_ACCORDION}:
        mode = OBJECT_VIEW_CLASSIC
    cfg = ConfigHelper.load_campaign_config()
    if not cfg.has_section(OBJECT_VIEW_SECTION):
        cfg.add_section(OBJECT_VIEW_SECTION)
    cfg.set(OBJECT_VIEW_SECTION, OBJECT_VIEW_KEY, mode)
    settings_path = ConfigHelper.get_campaign_settings_path()
    with open(settings_path, "w", encoding="utf-8") as f:
        cfg.write(f)
    try:
        ConfigHelper._campaign_mtime = os.path.getmtime(settings_path)
    except OSError:
        pass


class _CollapsibleSection(ctk.CTkFrame):
    """Fallback collapsible section for environments lacking CTkCollapsibleFrame."""

    def __init__(
        self,
        master,
        *,
        title: str,
        subtitle: str = "",
        category: str = "",
        on_open: Optional[Callable[[], None]] = None,
        merchant_palette: bool = True,
        **kwargs,
    ) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)
        self._body_visible = False
        self._on_open = on_open
        self._body_frame: Optional[ctk.CTkFrame] = None
        self._indicator_label: Optional[ctk.CTkLabel] = None
        self._merchant_palette = merchant_palette
        self._body_factory: Optional[Callable[[], Optional[ctk.CTkFrame]]] = None

        self.container = ctk.CTkFrame(
            self,
            corner_radius=10,
            fg_color=MERCHANT_HEADER_COLOR if merchant_palette else "#2B2B2B",
            border_width=1,
            border_color=MERCHANT_HEADER_BORDER if merchant_palette else "#444444",
        )
        self.container.pack(fill="x", padx=4, pady=(MERCHANT_SECTION_GAP, 0))
        self.container.grid_columnconfigure(0, weight=1)
        self.container.grid_columnconfigure(1, weight=0)

        title_font = ("Segoe UI", 15, "bold")
        subtitle_font = ("Segoe UI", 12)
        category_font = ("Segoe UI", 11, "bold")

        text_color = MERCHANT_TEXT_COLOR if merchant_palette else "white"
        subtext_color = MERCHANT_SUBTEXT_COLOR if merchant_palette else "#CCCCCC"

        self._title_label = ctk.CTkLabel(
            self.container,
            text=title,
            font=title_font,
            anchor="w",
            text_color=text_color,
        )
        self._title_label.grid(row=0, column=0, sticky="w", padx=16, pady=(12, 0))

        if category:
            self._category_label = ctk.CTkLabel(
                self.container,
                text=category,
                font=category_font,
                anchor="e",
                text_color=subtext_color,
            )
            self._category_label.grid(row=0, column=1, sticky="e", padx=(0, 16), pady=(12, 0))
        else:
            self._category_label = None

        self._subtitle_label = ctk.CTkLabel(
            self.container,
            text=subtitle,
            font=subtitle_font,
            anchor="w",
            text_color=subtext_color,
            wraplength=520,
        )
        self._subtitle_label.grid(row=1, column=0, columnspan=2, sticky="we", padx=16, pady=(4, 12))

        self._indicator_label = ctk.CTkLabel(
            self.container,
            text="▼",
            font=("Segoe UI", 18),
            text_color=subtext_color,
        )
        self._indicator_label.place(relx=0.98, rely=0.5, anchor="e")

        for widget in (self.container, self._title_label, self._subtitle_label, self._indicator_label):
            widget.bind("<Button-1>", self._toggle)

    def _toggle(self, _event=None):
        if self._body_visible:
            self.hide()
        else:
            self.show()
        if self._body_visible and callable(self._on_open):
            try:
                self._on_open()
            except Exception:
                pass

    def show(self):
        if self._body_frame is None:
            self._ensure_body()
        if self._body_frame is None:
            return
        if not self._body_visible:
            self._body_frame.pack(
                fill="x",
                padx=4,
                pady=(0, MERCHANT_SECTION_GAP),
                after=self.container,
            )
            if self._indicator_label:
                self._indicator_label.configure(text="▲")
            self._body_visible = True

    def hide(self):
        if self._body_frame and self._body_visible:
            self._body_frame.pack_forget()
            if self._indicator_label:
                self._indicator_label.configure(text="▼")
            self._body_visible = False

    def assign_body(self, frame: ctk.CTkFrame):
        self._body_frame = frame
        frame.configure(corner_radius=0)
        self._body_factory = None

    def set_body_factory(self, factory: Callable[[], Optional[ctk.CTkFrame]]) -> None:
        self._body_factory = factory

    def _ensure_body(self) -> None:
        if self._body_frame is not None or not callable(self._body_factory):
            return
        try:
            frame = self._body_factory()
        except Exception:
            frame = None
        if isinstance(frame, ctk.CTkFrame):
            self.assign_body(frame)


class MerchantCatalogEntry(_CollapsibleSection):
    """Visual representation of a single object in the merchant-style catalog."""

    def __init__(
        self,
        master,
        *,
        name: str,
        stats_preview: str,
        category: str,
        stats_provider: Optional[Callable[[], str]] = None,
        description_provider: Optional[Callable[[], str]] = None,
        secrets_provider: Optional[Callable[[], str]] = None,
        portrait_provider: Optional[Callable[[], Optional[str]]] = None,
        resolve_media_path: Optional[Callable[[str], Optional[str]]],
        on_edit: Optional[Callable[[], None]] = None,
    ) -> None:
        super().__init__(
            master,
            title=name or "Unnamed Object",
            subtitle=stats_preview,
            category=category,
            on_open=None,
        )
        self._resolve_media_path = resolve_media_path
        self._portrait_image: Optional[ctk.CTkImage] = None
        self._on_edit = on_edit
        self._stats_provider = stats_provider
        self._description_provider = description_provider
        self._secrets_provider = secrets_provider
        self._portrait_provider = portrait_provider

        self.set_body_factory(self._build_body)

    def _assign_portrait(self, label: ctk.CTkLabel, portrait_path: str) -> None:
        if not self._resolve_media_path or not portrait_path:
            return
        resolved = self._resolve_media_path(portrait_path)
        if not resolved:
            return
        try:
            with Image.open(resolved) as img:
                preview = img.copy()
        except Exception:
            return
        if hasattr(Image, "Resampling"):
            preview.thumbnail((180, 180), Image.Resampling.LANCZOS)
        else:
            preview.thumbnail((180, 180), Image.LANCZOS)
        self._portrait_image = ctk.CTkImage(light_image=preview, dark_image=preview, size=preview.size)
        label.configure(image=self._portrait_image)

    def _resolve_text(self, provider: Optional[Callable[[], str]]) -> str:
        if provider is None:
            return ""
        try:
            value = provider()
        except Exception:
            return ""
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        return str(value)

    def _resolve_portrait(self) -> Optional[str]:
        if self._portrait_provider is None:
            return None
        try:
            value = self._portrait_provider()
        except Exception:
            return None
        if not value:
            return None
        if isinstance(value, str):
            portrait = value.strip()
        else:
            portrait = str(value).strip()
        return portrait or None

    def _build_body(self) -> Optional[ctk.CTkFrame]:
        body = ctk.CTkFrame(
            self,
            fg_color=MERCHANT_BODY_COLOR,
            border_width=1,
            border_color=MERCHANT_HEADER_BORDER,
        )
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=0)

        text_color = MERCHANT_TEXT_COLOR
        header_font = ("Segoe UI", 12, "bold")
        body_font = ("Segoe UI", 12)

        row = 0
        stats_full = self._resolve_text(self._stats_provider)
        if stats_full:
            stats_section = ctk.CTkFrame(body, fg_color="transparent")
            stats_section.grid(row=row, column=0, sticky="we", padx=18, pady=(16, 8))
            ctk.CTkLabel(
                stats_section,
                text="Stats",
                font=header_font,
                text_color=text_color,
                anchor="w",
            ).pack(anchor="w")
            ctk.CTkLabel(
                stats_section,
                text=stats_full,
                font=body_font,
                text_color=text_color,
                wraplength=620,
                justify="left",
                anchor="w",
            ).pack(anchor="w", pady=(4, 0))
            row += 1

        description = self._resolve_text(self._description_provider)
        if description:
            desc_section = ctk.CTkFrame(body, fg_color="transparent")
            desc_section.grid(row=row, column=0, sticky="we", padx=18, pady=(8, 8))
            ctk.CTkLabel(
                desc_section,
                text="Description",
                font=header_font,
                text_color=text_color,
                anchor="w",
            ).pack(anchor="w")
            ctk.CTkLabel(
                desc_section,
                text=description,
                font=body_font,
                text_color=text_color,
                wraplength=620,
                justify="left",
                anchor="w",
            ).pack(anchor="w", pady=(4, 0))
            row += 1

        secrets = self._resolve_text(self._secrets_provider)
        if secrets:
            secret_section = ctk.CTkFrame(body, fg_color="transparent")
            secret_section.grid(row=row, column=0, sticky="we", padx=18, pady=(8, 12))
            ctk.CTkLabel(
                secret_section,
                text="Secrets",
                font=header_font,
                text_color=text_color,
                anchor="w",
            ).pack(anchor="w")
            ctk.CTkLabel(
                secret_section,
                text=secrets,
                font=body_font,
                text_color=text_color,
                wraplength=620,
                justify="left",
                anchor="w",
            ).pack(anchor="w", pady=(4, 0))
            row += 1

        edit_container = ctk.CTkFrame(body, fg_color="transparent")
        edit_container.grid(row=row, column=0, sticky="we", padx=18, pady=(4, 16))
        edit_container.grid_columnconfigure(0, weight=1)
        if callable(self._on_edit):
            edit_button = ctk.CTkButton(
                edit_container,
                text="Open in Editor",
                command=self._on_edit,
            )
            edit_button.grid(row=0, column=0, sticky="e")
        row += 1

        portrait_path = self._resolve_portrait()
        if portrait_path:
            image_label = ctk.CTkLabel(body, text="", anchor="center")
            image_label.grid(row=0, column=1, rowspan=max(row, 1), sticky="ne", padx=(0, 18), pady=18)
            self.after(25, lambda p=portrait_path, lbl=image_label: self._assign_portrait(lbl, p))

        return body


class ObjectAccordionCatalog(ctk.CTkFrame):
    """Scrollable merchant-style accordion catalog for objects."""

    def __init__(
        self,
        master,
        *,
        resolve_media_path: Optional[Callable[[str], Optional[str]]] = None,
        on_edit_item: Optional[Callable[[dict], None]] = None,
    ) -> None:
        super().__init__(master, fg_color="transparent")
        self._resolve_media_path = resolve_media_path
        self._on_edit_item = on_edit_item
        self._items: Iterable[dict] = []
        self._sections: list[MerchantCatalogEntry] = []
        self._populate_job: Optional[str] = None
        self._loading_label: Optional[ctk.CTkLabel] = None

        self._scroll = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            corner_radius=0,
        )
        self._scroll.pack(fill="both", expand=True)

        self._empty_label = ctk.CTkLabel(
            self._scroll,
            text="No objects to display",
            font=("Segoe UI", 14, "italic"),
            text_color=MERCHANT_SUBTEXT_COLOR,
        )
        self._empty_label.pack_forget()

    @staticmethod
    def _normalize_text(value: Optional[object]) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, dict):
            lines: list[str] = []
            for key, sub_value in value.items():
                key_text = str(key).strip()
                sub_text = ObjectAccordionCatalog._normalize_text(sub_value)
                if sub_text:
                    lines.append(f"{key_text}: {sub_text}")
                else:
                    lines.append(key_text)
            return "\n".join(line for line in lines if line)
        if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray, str)):
            items = [ObjectAccordionCatalog._normalize_text(v) for v in value]
            items = [item for item in items if item]
            return "\n".join(
                f"• {item}" if not item.startswith("• ") else item for item in items
            )
        return str(value).strip()

    @staticmethod
    def _inline_text(value: Optional[object]) -> str:
        text = ObjectAccordionCatalog._normalize_text(value)
        return ", ".join(part for part in (segment.strip() for segment in text.splitlines()) if part)

    @staticmethod
    def _stats_preview(stats: str, limit: int = 160) -> str:
        if not stats:
            return "No stats available"
        text = " ".join(stats.split())
        if len(text) > limit:
            return text[:limit].rstrip() + "..."
        return text

    def populate(
        self,
        items: Iterable[dict],
        *,
        unique_field: str = "Name",
        stats_field: str = "Stats",
        description_field: str = "Description",
        secrets_field: str = "Secrets",
        category_field: str = "Category",
        portrait_field: Optional[str] = None,
    ) -> None:
        """Populate the accordion with the provided object entries."""

        if self._populate_job:
            try:
                self.after_cancel(self._populate_job)
            except Exception:
                pass
            self._populate_job = None

        for widget in self._scroll.winfo_children():
            widget.destroy()
        self._sections.clear()

        item_list = list(items)
        self._items = item_list
        if not item_list:
            empty = ctk.CTkLabel(
                self._scroll,
                text="No objects to display",
                font=("Segoe UI", 14, "italic"),
                text_color=MERCHANT_SUBTEXT_COLOR,
            )
            empty.pack(padx=24, pady=24)
            self._empty_label = empty
            self._loading_label = None
            return

        self._empty_label = None
        self._loading_label = ctk.CTkLabel(
            self._scroll,
            text="Loading catalog...",
            font=("Segoe UI", 14, "italic"),
            text_color=MERCHANT_SUBTEXT_COLOR,
        )
        self._loading_label.pack(padx=24, pady=24)

        batch_size = 32 if len(item_list) > 400 else 40
        total = len(item_list)

        def build_batch(start_index: int) -> None:
            if self._loading_label:
                self._loading_label.destroy()
                self._loading_label = None
            end_index = min(start_index + batch_size, total)
            for idx in range(start_index, end_index):
                item = item_list[idx]
                name = self._inline_text(item.get(unique_field) or item.get("Name")) or "Unnamed Object"
                category = self._inline_text(item.get(category_field))

                @lru_cache(maxsize=1)
                def stats_value(_item=item):
                    return self._normalize_text(_item.get(stats_field))

                preview = self._stats_preview(stats_value())

                description_provider: Optional[Callable[[], str]] = None
                if description_field:
                    @lru_cache(maxsize=1)
                    def description_value(_item=item):
                        return self._normalize_text(_item.get(description_field))

                    description_provider = description_value

                secrets_provider: Optional[Callable[[], str]] = None
                if secrets_field:
                    @lru_cache(maxsize=1)
                    def secrets_value(_item=item):
                        return self._normalize_text(_item.get(secrets_field))

                    secrets_provider = secrets_value

                portrait_provider: Optional[Callable[[], Optional[str]]] = None
                if portrait_field:

                    @lru_cache(maxsize=1)
                    def portrait_value(_item=item):
                        value = _item.get(portrait_field)
                        if isinstance(value, str):
                            return value.strip()
                        if value is None:
                            return None
                        return str(value).strip() or None

                    portrait_provider = portrait_value

                def _make_edit_callback(entry=item):
                    if not callable(self._on_edit_item):
                        return None

                    def _callback():
                        try:
                            self._on_edit_item(entry)
                        except Exception:
                            pass

                    return _callback

                section = MerchantCatalogEntry(
                    self._scroll,
                    name=name,
                    stats_preview=preview,
                    category=category,
                    stats_provider=stats_value,
                    description_provider=description_provider,
                    secrets_provider=secrets_provider,
                    portrait_provider=portrait_provider,
                    resolve_media_path=self._resolve_media_path,
                    on_edit=_make_edit_callback(),
                )
                section.pack(fill="x", padx=4, pady=0)
                self._sections.append(section)

            if end_index < total:
                self._populate_job = self.after(1, lambda: build_batch(end_index))
            else:
                self._populate_job = None

        self._populate_job = self.after(15, lambda: build_batch(0))


log_module_import(__name__)
