"""Utilities for window components portrait and image workflows."""

from modules.generic.editor.window_context import *
from modules.generic.editor.styles import EDITOR_PALETTE, primary_button_style, tk_listbox_theme


class GenericEditorWindowPortraitAndImageWorkflows:
    def create_portrait_field(self, field):
        """Create portrait field."""
        frame = ctk.CTkFrame(self._field_parent(), fg_color="transparent")
        frame.pack(fill="x", pady=5)

        campaign_dir = Path(ConfigHelper.get_campaign_dir())
        raw_value = self.item.get("Portrait", "") or ""
        normalized_paths = [
            self._campaign_relative_path(path)
            for path in parse_portrait_value(raw_value)
            if path
        ]
        self.portrait_paths = normalized_paths
        self.portrait_path = primary_portrait(self.portrait_paths)

        image_frame = ctk.CTkFrame(frame, fg_color=EDITOR_PALETTE["surface_soft"], corner_radius=10)
        image_frame.pack(fill="x", pady=5)

        self.portrait_label = ctk.CTkLabel(image_frame, text="[No Portrait]", text_color=EDITOR_PALETTE["muted_text"])
        self.portrait_label.pack(pady=5)

        list_frame = ctk.CTkFrame(frame, fg_color=EDITOR_PALETTE["surface_soft"], corner_radius=10)
        list_frame.pack(fill="x", pady=(0, 5))

        ctk.CTkLabel(list_frame, text="Portraits", text_color=EDITOR_PALETTE["muted_text"]).pack(anchor="w", padx=8, pady=(8, 0))
        self.portrait_listbox = tk.Listbox(list_frame, height=4, exportselection=False, **tk_listbox_theme())
        self.portrait_listbox.pack(fill="x", padx=5, pady=5)
        self._refresh_portrait_listbox(select_primary=True)
        self.portrait_listbox.bind("<<ListboxSelect>>", self._on_portrait_select)

        button_frame = ctk.CTkFrame(frame, fg_color="transparent")
        button_frame.pack(pady=5)

        ctk.CTkButton(button_frame, text="Add Portrait(s)", **primary_button_style(), command=self.select_portrait).pack(side="left", padx=5)
        ctk.CTkButton(button_frame, text="Search Images", **primary_button_style(), command=self.open_portrait_image_browser).pack(side="left", padx=5)
        ctk.CTkButton(button_frame, text="Paste Portrait", **primary_button_style(), command=self.paste_portrait_from_clipboard).pack(side="left", padx=5)
        ctk.CTkButton(button_frame, text="Create Portrait with description", **primary_button_style(), command=self.create_portrait_with_swarmui).pack(side="left", padx=5)
        ctk.CTkButton(button_frame, text="Set Primary", **primary_button_style(), command=self.set_primary_portrait).pack(side="left", padx=5)
        ctk.CTkButton(button_frame, text="Remove Selected", **primary_button_style(), command=self.remove_selected_portrait).pack(side="left", padx=5)

        helper_label = ctk.CTkLabel(
            frame,
            text="Copiez l’image puis utilisez ‘Paste Portrait’.",
            font=ctk.CTkFont(size=12, slant="italic"),
            text_color=EDITOR_PALETTE["muted_text"],
            anchor="w",
        )
        helper_label.pack(fill="x", padx=5, pady=(0, 5))

        self._update_portrait_preview(primary_only=True)
    def open_portrait_image_browser(self):
        """Open portrait image browser."""
        query = self._resolve_portrait_search_query()
        query = quote_plus(query) 
        url = ImageBrowserDialog.build_search_url(query)
        try:
            # Keep portrait image browser resilient if this step fails.
            PyWebviewClient(title="Image Browser").open(url)
        except Exception as exc:
            log_exception(
                f"Unable to open image browser for {url}: {exc}",
                func_name="GenericEditorWindow.open_portrait_image_browser",
            )
            messagebox.showerror(
                "Image Browser",
                "Impossible d’ouvrir la page d’images. Vérifiez la connexion puis réessayez.",
            )
    def _resolve_portrait_search_query(self):
        """Resolve portrait search query."""
        key_field = self.model_wrapper._infer_key_field()
        widget = self.field_widgets.get(key_field)
        name = ""
        if hasattr(widget, "get"):
            name = str(widget.get()).strip()
        if not name:
            name = str(self.item.get(key_field) or self.item.get("Name") or "").strip()
        return name or "fantasy portrait"
    def paste_portrait_from_clipboard(self):
        """Paste image from clipboard and set as entity portrait.
        Supports images directly or image file paths in clipboard (Windows).
        """
        try:
            data = ImageGrab.grabclipboard()
        except Exception as e:
            messagebox.showerror("Clipboard Error", f"Unable to access clipboard: {e}")
            return

        if data is None:
            messagebox.showinfo("Paste Portrait", "No image found in clipboard.")
            return

        if isinstance(data, list):
            # Handle the branch where isinstance(data, list).
            added = False
            for path in data:
                try:
                    # Keep paste portrait from clipboard resilient if this step fails.
                    if os.path.isfile(path):
                        copied = self.copy_and_resize_portrait(path)
                        self._add_portrait_path(copied, make_primary=not self.portrait_paths)
                        added = True
                except Exception:
                    continue
            if not added:
                messagebox.showinfo("Paste Portrait", "Clipboard has file paths but none are valid images.")
            return

        if isinstance(data, Image.Image):
            try:
                # Keep paste portrait from clipboard resilient if this step fails.
                campaign_dir = Path(ConfigHelper.get_campaign_dir())
                portrait_folder = campaign_dir / 'assets' / 'portraits'
                portrait_folder.mkdir(parents=True, exist_ok=True)

                base_name = (self.item.get('Name') or 'Unnamed').replace(' ', '_')
                dest_filename = f"{base_name}_{id(self)}.png"
                dest_path = portrait_folder / dest_filename

                img = data
                if img.mode == 'P':
                    # Convert palette images to RGBA to preserve transparency information
                    img = img.convert('RGBA')
                elif img.mode not in ('RGB', 'RGBA'):
                    # Fallback for other color modes that are not directly supported
                    img = img.convert('RGB')

                img.save(dest_path, format='PNG')

                try:
                    relative = dest_path.relative_to(campaign_dir).as_posix()
                except ValueError:
                    relative = dest_path.as_posix()
                self._add_portrait_path(relative, make_primary=not self.portrait_paths)
                return
            except Exception as e:
                messagebox.showerror("Paste Portrait", f"Failed to paste image: {e}")
                return

        messagebox.showinfo("Paste Portrait", "Clipboard content is not an image.")
    def create_image_field(self, field):
        """Create image field."""
        frame = ctk.CTkFrame(self._field_parent())
        frame.pack(fill="x", pady=5)

        campaign_dir = Path(ConfigHelper.get_campaign_dir())
        raw_image_path = self.item.get("Image", "") or ""
        normalized_path = self._campaign_relative_path(raw_image_path)
        self.image_path = normalized_path

        abs_path = None
        if normalized_path:
            # Continue with this path when normalized path is set.
            candidate = Path(normalized_path)
            abs_path = candidate if candidate.is_absolute() else campaign_dir / candidate
        elif raw_image_path:
            candidate = Path(raw_image_path)
            abs_path = candidate if candidate.is_absolute() else campaign_dir / candidate

        image_frame = ctk.CTkFrame(frame, fg_color=EDITOR_PALETTE["surface_soft"], corner_radius=10)
        image_frame.pack(fill="x", pady=5)

        if abs_path and abs_path.exists():
            # Handle the branch where abs path is set and abs_path.exists().
            try:
                image = Image.open(abs_path).resize((256, 256))
                self.image_image = ctk.CTkImage(light_image=image, size=(256, 256))
                self.image_label = ctk.CTkLabel(image_frame, image=self.image_image, text="")
            except Exception:
                self.image_label = ctk.CTkLabel(image_frame, text="[No Image]")
                self.image_image = None
        else:
            self.image_label = ctk.CTkLabel(image_frame, text="[No Image]")
            self.image_image = None
            if not normalized_path:
                self.image_path = ""

        self.image_label.pack(pady=5)

        button_frame = ctk.CTkFrame(frame, fg_color="transparent")
        button_frame.pack(pady=5)

        ctk.CTkButton(button_frame, text="Select Image", command=self.select_image, **primary_button_style()).pack(side="left", padx=5)
        ctk.CTkButton(button_frame, text="Paste Image", command=self.paste_image_from_clipboard, **primary_button_style()).pack(side="left", padx=5)
        self.field_widgets[field["name"]] = self.image_path
    def paste_image_from_clipboard(self):
        """Paste image from clipboard and set as entity image (map image).
        Supports images directly or image file paths in clipboard (Windows/macOS).
        """
        try:
            data = ImageGrab.grabclipboard()
        except Exception as e:
            messagebox.showerror("Clipboard Error", f"Unable to access clipboard: {e}")
            return

        if data is None:
            messagebox.showinfo("Paste Image", "No image found in clipboard.")
            return

        # If clipboard contains a list of file paths, try first valid image path
        if isinstance(data, list):
            # Handle the branch where isinstance(data, list).
            for path in data:
                try:
                    # Keep paste image from clipboard resilient if this step fails.
                    if os.path.isfile(path):
                        # Handle the branch where os.path.isfile(path).
                        self.image_path = self.copy_and_resize_image(path)
                        if self.image_path:
                            candidate = Path(self.image_path)
                            abs_path = candidate if candidate.is_absolute() else Path(ConfigHelper.get_campaign_dir()) / candidate
                        else:
                            abs_path = None
                        try:
                            # Keep paste image from clipboard resilient if this step fails.
                            if abs_path and abs_path.exists():
                                image = Image.open(abs_path).resize((256, 256))
                                self.image_image = ctk.CTkImage(light_image=image, size=(256, 256))
                                self.image_label.configure(image=self.image_image, text="")
                            else:
                                raise FileNotFoundError
                        except Exception:
                            display_name = os.path.basename(self.image_path) if self.image_path else "[No Image]"
                            self.image_label.configure(image=None, text=display_name)
                            self.image_image = None
                        self.field_widgets["Image"] = self._campaign_relative_path(self.image_path)
                        return
                except Exception:
                    continue
            messagebox.showinfo("Paste Image", "Clipboard has file paths but none are valid images.")
            return

        # If clipboard contains a PIL Image
        if isinstance(data, Image.Image):
            try:
                # Keep paste image from clipboard resilient if this step fails.
                campaign_dir = Path(ConfigHelper.get_campaign_dir())
                image_folder = campaign_dir / 'assets' / 'images' / 'map_images'
                image_folder.mkdir(parents=True, exist_ok=True)

                base_name = (self.item.get('Name') or 'Unnamed').replace(' ', '_')
                dest_filename = f"{base_name}_{id(self)}.png"
                dest_path = image_folder / dest_filename

                # Convert to RGB to ensure PNG save works for all modes
                img = data
                if img.mode in ("P", "RGBA"):
                    img = img.convert("RGB")

                # Save directly to destination
                img.save(dest_path, format="PNG")

                # Store relative path used by the app
                try:
                    relative = Path(dest_path).relative_to(campaign_dir).as_posix()
                except ValueError:
                    relative = Path(dest_path).as_posix()
                self.image_path = relative
                abs_path = Path(dest_path)
                try:
                    # Keep paste image from clipboard resilient if this step fails.
                    if abs_path.exists():
                        image = Image.open(abs_path).resize((256, 256))
                        self.image_image = ctk.CTkImage(light_image=image, size=(256, 256))
                        self.image_label.configure(image=self.image_image, text="")
                    else:
                        raise FileNotFoundError
                except Exception:
                    display_name = os.path.basename(self.image_path) if self.image_path else "[No Image]"
                    self.image_label.configure(image=None, text=display_name)
                    self.image_image = None
                self.field_widgets["Image"] = self._campaign_relative_path(self.image_path)
                return
            except Exception as e:
                messagebox.showerror("Paste Image", f"Failed to paste image: {e}")
                return

        messagebox.showinfo("Paste Image", "Clipboard content is not an image.")
    def launch_swarmui(self):
        """Launch swarmui."""
        global SWARMUI_PROCESS
        # Retrieve the SwarmUI path from config.ini
        swarmui_path = ConfigHelper.get("Paths", "swarmui_path", fallback=r"E:\SwarmUI\SwarmUI")
        # Build the command by joining the path with the batch file name
        SWARMUI_CMD = os.path.join(swarmui_path, "launch-windows.bat")
        env = os.environ.copy()
        env.pop('VIRTUAL_ENV', None)
        if SWARMUI_PROCESS is None or SWARMUI_PROCESS.poll() is not None:
            try:
                # Keep swarmui resilient if this step fails.
                SWARMUI_PROCESS = subprocess.Popen(
                    SWARMUI_CMD,
                    shell=True,
                    cwd=swarmui_path,
                    env=env
                )
                # Wait a little for the process to initialize.
                time.sleep(120.0)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to launch SwarmUI: {e}")
    def cleanup_swarmui(self):
        """
        Terminate the SwarmUI process if it is running.
        """
        global SWARMUI_PROCESS
        if SWARMUI_PROCESS is not None and SWARMUI_PROCESS.poll() is None:
            SWARMUI_PROCESS.terminate()
    def create_portrait_with_swarmui(self):
        """Create a portrait by delegating image generation to SwarmUI."""

        self.launch_swarmui()
        # Ask for model
        model_options = get_available_models()
        if not model_options:
            messagebox.showerror("Error", "No models available in SwarmUI models folder.")
            return

        # Pop-up to select model
        top = ctk.CTkToplevel(self)
        top.title("Select AI Model")
        top.geometry("400x200")
        top.transient(self)
        top.grab_set()

        model_var = ctk.StringVar(value=model_options[0])
        last_model = ConfigHelper.get("LastUsed", "model", fallback=None)
        
        if last_model in model_options:
            selected_model = ctk.StringVar(value=last_model)
        else:
            selected_model = ctk.StringVar(value=model_options[0])
        ctk.CTkLabel(top, text="Select AI Model for this NPC:").pack(pady=20)
        ctk.CTkOptionMenu(top, values=model_options, variable=selected_model).pack(pady=10)

        def on_confirm():
            """Handle confirm."""
            top.destroy()
            ConfigHelper.set("LastUsed", "model", selected_model.get())
            self.generate_portrait(selected_model.get())
        ctk.CTkButton(top, text="Generate", command=on_confirm).pack(pady=10)
    def generate_portrait(self, selected_model):
        """
        Generates a portrait image using the SwarmUI API and associates the resulting
        image with the current NPC by updating its 'Portrait' field.
        """
        SWARM_API_URL = "http://127.0.0.1:7801"  # Change if needed
        try:
            # Step 1: Obtain a new session from SwarmUI
            session_url = f"{SWARM_API_URL}/API/GetNewSession"
            session_response = requests.post(session_url, json={}, headers={"Content-Type": "application/json"})
            session_data = session_response.json()
            session_id = session_data.get("session_id")
            if not session_id:
                messagebox.showerror("Error", "Failed to obtain session ID from Swarm API.")
                return

            # Build a prompt based on the current NPC's data (you can enhance this as needed)
            npc_name = self.item.get("Name", "Unknown")
            npc_role = self.item.get("Role", "Unknown")
            npc_faction = self.item.get("Factions", "Unknown")
            npc_object = self.item.get("Objects", "Unknown")
            npc_desc = self.item.get("Description", "Unknown") 
            npc_desc =  text_helpers.format_longtext(npc_desc)
            npc_desc = f"{npc_desc} {npc_role} {npc_faction} {npc_object}"
            prompt = f"{npc_desc}"

            # Step 2: Define image generation parameters
            prompt_data = {
                "session_id": session_id,
                "images": 6,  # Generate multiple candidates
                "prompt": prompt,
                "negativeprompt": "blurry, low quality, comics style, mangastyle, paint style, watermark, ugly, monstrous, too many fingers, too many legs, too many arms, bad hands, unrealistic weapons, bad grip on equipment, nude",
                "model": selected_model,
                "width": 1024,
                "height": 1024,
                "cfgscale": 9,
                "steps": 20,
                "seed": -1
            }
            generate_url = f"{SWARM_API_URL}/API/GenerateText2Image"
            image_response = requests.post(generate_url, json=prompt_data, headers={"Content-Type": "application/json"})
            image_data = image_response.json()

            images = image_data.get("images")
            if not images or len(images) == 0:
                messagebox.showerror("Error", "Image generation failed. Check API response.")
                return

            # Step 3: Download all generated images into memory
            thumbs = []
            images_bytes = []
            for rel_path in images:
                try:
                    # Keep generate portrait resilient if this step fails.
                    url = f"{SWARM_API_URL}/{rel_path}"
                    resp = requests.get(url)
                    if resp.status_code == 200:
                        images_bytes.append(resp.content)
                        img = Image.open(BytesIO(resp.content)).convert("RGB")
                        thumb = img.copy()
                        thumb.thumbnail((256, 256))
                        thumbs.append(thumb)
                except Exception:
                    continue

            if not thumbs:
                messagebox.showerror("Error", "Failed to download generated images.")
                return

            # Step 4: Let user choose one of the 6 images
            chosen_index = self._show_image_selection_window(thumbs)
            if chosen_index is None or chosen_index < 0 or chosen_index >= len(images_bytes):
                return  # User cancelled

            chosen_bytes = images_bytes[chosen_index]

            # Step 5: Save the chosen image locally and update the NPC's Portrait field
            output_filename = f"{npc_name.replace(' ', '_')}_portrait.png"
            with open(output_filename, "wb") as f:
                f.write(chosen_bytes)

            # Associate the selected portrait with the NPC data.
            generated_path = self.copy_and_resize_portrait(output_filename)
            self._add_portrait_path(generated_path, make_primary=not self.portrait_paths)

            # Copy the original generated file to assets/generated and delete local temp
            GENERATED_FOLDER = os.path.join(ConfigHelper.get_campaign_dir(), "assets", "generated")
            os.makedirs(GENERATED_FOLDER, exist_ok=True)
            shutil.copy(output_filename, os.path.join(GENERATED_FOLDER, output_filename))
            os.remove(output_filename)

        except Exception as e:
            messagebox.showerror("Error", f"An error occurred: {e}")
    def _show_image_selection_window(self, pil_images):
        """
        Display a modal window with thumbnails side by side for the user to choose.
        Returns the selected index, or None if cancelled.
        """
        if not pil_images:
            return None

        top = ctk.CTkToplevel(self)
        top.title("Choose a Portrait")
        top.transient(self)
        top.grab_set()

        # Container frame
        container = ctk.CTkFrame(top)
        container.pack(padx=10, pady=10, fill="both", expand=True)

        # Keep CTkImage references to avoid GC
        ctk_images = []
        selected = {"idx": None}

        def on_choose(i):
            """Handle choose."""
            selected["idx"] = i
            top.destroy()

        # Layout: 3 columns x 2 rows (up to 6 images)
        cols = 6 if len(pil_images) <= 6 else 6
        # Place horizontally side by side if <= 6
        for i, img in enumerate(pil_images[:6]):
            cimg = ctk.CTkImage(light_image=img, size=(256, 256))
            ctk_images.append(cimg)
            btn = ctk.CTkButton(container, image=cimg, text="", width=260, height=260,
                                command=lambda idx=i: on_choose(idx))
            btn.grid(row=0, column=i, padx=5, pady=5)

        # Cancel button
        cancel_btn = ctk.CTkButton(top, text="Cancel", command=lambda: (setattr(selected, "idx", None), top.destroy()))
        # Workaround: setattr on dict won't work; override with lambda capturing selected
        def _cancel():
            """Internal helper for cancel."""
            selected["idx"] = None
            top.destroy()
        cancel_btn.configure(command=_cancel)
        cancel_btn.pack(pady=5)

        # Size window to fit thumbnails in a row
        top.update_idletasks()
        total_w = min(6, len(pil_images)) * (260 + 10) + 20
        total_h = 320
        try:
            top.geometry(f"{total_w}x{total_h}")
        except Exception:
            pass

        top.wait_window()
        return selected["idx"]
    def select_portrait(self):
        """Select portrait."""
        file_paths = filedialog.askopenfilenames(
            title="Select Portrait Image(s)",
            filetypes=[
                ("Image Files", "*.png;*.jpg;*.jpeg;*.gif;*.bmp;*.webp"),
                ("PNG Files", "*.png"),
                ("JPEG Files", "*.jpg;*.jpeg"),
                ("GIF Files", "*.gif"),
                ("Bitmap Files", "*.bmp"),
                ("WebP Files", "*.webp"),
                ("All Files", "*.*")
            ]
        )

        if file_paths:
            for file_path in file_paths:
                if not self._validate_asset_source(file_path, asset_label="Portrait"):
                    continue
                copied = self.copy_and_resize_portrait(file_path)
                normalized = self._campaign_relative_path(copied)
                self._add_portrait_path(normalized, make_primary=not self.portrait_paths)

    def attach_portrait_from_library(self, image_result):
        """Attach portrait selected from image library."""
        source_path = str(getattr(image_result, "path", image_result))
        if not self._validate_asset_source(source_path, asset_label="Portrait"):
            return
        copied = self.copy_and_resize_portrait(source_path)
        normalized = self._campaign_relative_path(copied)
        self._add_portrait_path(normalized, make_primary=not self.portrait_paths)
