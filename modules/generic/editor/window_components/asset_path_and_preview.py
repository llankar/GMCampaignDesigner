"""Utilities for window components asset path and preview."""

from modules.generic.editor.window_context import *


class GenericEditorWindowAssetPathAndPreview:
    def _validate_asset_source(self, src_path: str, *, asset_label: str) -> bool:
        """Ensure selected source path exists before copying."""
        if not src_path:
            return False
        source = Path(src_path)
        if source.is_file():
            return True
        messagebox.showerror(
            f"{asset_label} introuvable",
            f"Le fichier source est introuvable:\n{src_path}",
        )
        return False

    def _set_image_preview_from_path(self, image_path: str) -> None:
        """Refresh image preview label for the provided stored image path."""
        if image_path:
            candidate = Path(image_path)
            abs_path = candidate if candidate.is_absolute() else Path(ConfigHelper.get_campaign_dir()) / candidate
        else:
            abs_path = None
        try:
            # Keep image resilient if this step fails.
            if abs_path and abs_path.exists():
                image = Image.open(abs_path).resize((256, 256))
                self.image_image = ctk.CTkImage(light_image=image, size=(256, 256))
                self.image_label.configure(image=self.image_image, text="")
            else:
                raise FileNotFoundError
        except Exception:
            display_name = os.path.basename(image_path) if image_path else "[No Image]"
            self.image_label.configure(image=None, text=display_name)
            self.image_image = None

    def _persist_image_path(self, path: str) -> str:
        """Store image path in campaign-relative format."""
        normalized = self._campaign_relative_path(path)
        self.image_path = normalized
        self.field_widgets["Image"] = normalized
        return normalized

    def _attach_image_from_source(self, src_path: str) -> bool:
        """Copy image from source path and persist normalized campaign-relative value."""
        if not self._validate_asset_source(src_path, asset_label="Image"):
            return False
        copied_path = self.copy_and_resize_image(src_path)
        normalized = self._persist_image_path(copied_path)
        self._set_image_preview_from_path(normalized)
        return True

    def select_image(self):
        """Select image."""
        file_path = filedialog.askopenfilename(
            title="Select Image or Video",
            filetypes=[
                ("Images & Videos", "*.png;*.jpg;*.jpeg;*.gif;*.bmp;*.webp;*.mp4;*.webm;*.mov;*.mkv;*.avi;*.m4v"),
                ("Image Files", "*.png;*.jpg;*.jpeg;*.gif;*.bmp;*.webp"),
                ("Video Files", "*.mp4;*.webm;*.mov;*.mkv;*.avi;*.m4v"),
                ("PNG Files", "*.png"),
                ("JPEG Files", "*.jpg;*.jpeg"),
                ("GIF Files", "*.gif"),
                ("Bitmap Files", "*.bmp"),
                ("WebP Files", "*.webp"),
                ("All Files", "*.*")
            ]
        )

        if file_path:
            self._attach_image_from_source(file_path)

    def attach_image_from_library(self, image_result):
        """Attach image selected from image library."""
        source_path = getattr(image_result, "path", image_result)
        self._attach_image_from_source(str(source_path))
    def _campaign_relative_path(self, path):
        """Internal helper for campaign relative path."""
        if not path or str(path).strip() in ("[No Image]", "[No Portrait]", "[No Attachment]", ""):
            return ""
        try:
            candidate = Path(path)
        except TypeError:
            return str(path)
        if candidate.is_absolute():
            try:
                campaign_dir = Path(ConfigHelper.get_campaign_dir()).resolve()
                return candidate.resolve().relative_to(campaign_dir).as_posix()
            except Exception:
                return candidate.resolve().as_posix()
        return candidate.as_posix()
    def _format_audio_label(self, value: str) -> str:
        """Format audio label."""
        if not value:
            return "[No Audio]"
        resolved = Path(resolve_audio_path(value))
        name = os.path.basename(str(value)) or "Audio"
        if resolved.exists():
            return name
        return f"{name} (missing)"
    def _refresh_portrait_listbox(self, *, select_primary: bool = False, selected_index: int | None = None):
        """Refresh portrait listbox."""
        if not getattr(self, "portrait_listbox", None):
            return
        self.portrait_listbox.delete(0, "end")
        for path in self.portrait_paths:
            self.portrait_listbox.insert("end", path)
        if not self.portrait_paths:
            return
        if select_primary or selected_index is None:
            index = 0
        else:
            index = max(0, min(selected_index, len(self.portrait_paths) - 1))
        self.portrait_listbox.selection_clear(0, "end")
        self.portrait_listbox.selection_set(index)
        self.portrait_listbox.activate(index)
    def _on_portrait_select(self, _event=None):
        """Handle portrait select."""
        if not getattr(self, "portrait_listbox", None):
            return
        selection = self.portrait_listbox.curselection()
        if not selection:
            return
        index = selection[0]
        try:
            path = self.portrait_paths[index]
        except IndexError:
            return
        self._update_portrait_preview(path=path)
    def _add_portrait_path(self, path: str, *, make_primary: bool = False):
        """Internal helper for add portrait path."""
        if not path:
            return
        normalized = self._campaign_relative_path(path)
        if not normalized:
            return
        if normalized in self.portrait_paths:
            if make_primary and self.portrait_paths[0] != normalized:
                self.portrait_paths.remove(normalized)
                self.portrait_paths.insert(0, normalized)
        else:
            if make_primary:
                self.portrait_paths.insert(0, normalized)
            else:
                self.portrait_paths.append(normalized)
        self._refresh_portrait_listbox(select_primary=make_primary)
        self._update_portrait_preview()
    def set_primary_portrait(self):
        """Set primary portrait."""
        if not getattr(self, "portrait_listbox", None):
            return
        selection = self.portrait_listbox.curselection()
        if not selection:
            return
        index = selection[0]
        if index == 0:
            return
        try:
            path = self.portrait_paths.pop(index)
        except IndexError:
            return
        self.portrait_paths.insert(0, path)
        self._refresh_portrait_listbox(select_primary=True)
        self._update_portrait_preview()
    def remove_selected_portrait(self):
        """Remove selected portrait."""
        if not getattr(self, "portrait_listbox", None):
            return
        selection = list(self.portrait_listbox.curselection())
        if not selection:
            return
        for index in sorted(selection, reverse=True):
            if 0 <= index < len(self.portrait_paths):
                self.portrait_paths.pop(index)
        self._refresh_portrait_listbox(select_primary=True)
        self._update_portrait_preview()
    def _update_portrait_preview(self, *, path: str | None = None, primary_only: bool = False):
        """Update portrait preview."""
        campaign_dir = Path(ConfigHelper.get_campaign_dir())
        if path is None:
            if primary_only:
                path = primary_portrait(self.portrait_paths)
            else:
                path = primary_portrait(self.portrait_paths)
        self.portrait_path = primary_portrait(self.portrait_paths)
        if path:
            candidate = Path(path)
            abs_path = candidate if candidate.is_absolute() else campaign_dir / candidate
        else:
            abs_path = None
        try:
            # Keep portrait preview resilient if this step fails.
            if abs_path and abs_path.exists():
                image = Image.open(abs_path).resize((256, 256))
                self.portrait_image = ctk.CTkImage(light_image=image, size=(256, 256))
                self.portrait_label.configure(image=self.portrait_image, text="")
            else:
                raise FileNotFoundError
        except Exception:
            display_name = os.path.basename(path) if path else "[No Portrait]"
            self.portrait_label.configure(image=None, text=display_name)
            self.portrait_image = None
        self.field_widgets["Portrait"] = serialize_portrait_value(self.portrait_paths)
    def copy_and_resize_image(self, src_path):
        """Copy and resize image."""
        campaign_dir = Path(ConfigHelper.get_campaign_dir())
        image_folder = campaign_dir / 'assets' / 'images' / 'map_images'
        MAX_IMAGE_SIZE = (1920, 1080)

        image_folder.mkdir(parents=True, exist_ok=True)

        image_name = self.item.get('Name', 'Unnamed').replace(' ', '_')
        ext = os.path.splitext(src_path)[-1].lower()
        dest_filename = f"{image_name}_{id(self)}{ext}"
        dest_path = image_folder / dest_filename
        shutil.copy(src_path, dest_path)

        try:
            relative = dest_path.relative_to(campaign_dir).as_posix()
        except ValueError:
            relative = dest_path.as_posix()
        return relative
    def copy_and_resize_portrait(self, src_path):
        """Copy and resize portrait."""
        campaign_dir = Path(ConfigHelper.get_campaign_dir())
        portrait_folder = campaign_dir / 'assets' / 'portraits'
        MAX_PORTRAIT_SIZE = (1024, 1024)

        portrait_folder.mkdir(parents=True, exist_ok=True)

        npc_name = self.item.get('Name', 'Unnamed').replace(' ', '_')
        source_stem = os.path.splitext(os.path.basename(src_path))[0]
        sanitized_stem = ''.join(
            char if char.isalnum() or char in {'_', '-'} else '_'
            for char in source_stem
        )
        if not sanitized_stem:
            sanitized_stem = 'portrait'
        ext = os.path.splitext(src_path)[-1].lower()
        unique_stamp = time.time_ns()
        dest_filename = f"{npc_name}_{sanitized_stem}_{unique_stamp}{ext}"
        dest_path = portrait_folder / dest_filename
        shutil.copy(src_path, dest_path)

        try:
            relative = dest_path.relative_to(campaign_dir).as_posix()
        except ValueError:
            relative = dest_path.as_posix()
        return relative
    def copy_audio_asset(self, src_path: str) -> str:
        """Copy audio asset."""
        campaign_dir = Path(ConfigHelper.get_campaign_dir())
        audio_folder = campaign_dir / 'assets' / 'audio'
        audio_folder.mkdir(parents=True, exist_ok=True)

        base_name = (
            self.item.get('Name')
            or self.item.get('Title')
            or os.path.splitext(os.path.basename(src_path))[0]
            or 'audio'
        )
        sanitized = ''.join(ch if ch.isalnum() or ch in {'_', '-'} else '_' for ch in str(base_name))
        if not sanitized:
            sanitized = 'audio'
        ext = os.path.splitext(src_path)[-1]
        timestamp = int(time.time())
        dest_filename = f"{sanitized}_{timestamp}{ext}"
        dest_path = audio_folder / dest_filename
        shutil.copy(src_path, dest_path)

        try:
            relative = dest_path.relative_to(campaign_dir).as_posix()
        except ValueError:
            relative = dest_path.as_posix()
        return relative
