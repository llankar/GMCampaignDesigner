import customtkinter as ctk
import tkinter as tk
from tkinter import simpledialog, colorchooser
from modules.helpers.custom_buttons import MinimalCTkButton  # Import de notre bouton personnalisé

class RichTextEditor(ctk.CTkFrame):
    def __init__(self, master, initial_text=""):
        super().__init__(master)
        # Global toolbar at the top (exposed as self.toolbar)
        self.toolbar = ctk.CTkFrame(self)
        self.toolbar.pack(fill="x", padx=5, pady=5)

        # Bouton Bold
        bold_button = MinimalCTkButton(self.toolbar, text="Bold", command=self.toggle_bold)
        bold_button.pack(side="left", padx=5)

        italic_button = MinimalCTkButton(self.toolbar, text="Italic", command=self.toggle_italic)
        italic_button.pack(side="left", padx=5)

        underline_button = MinimalCTkButton(self.toolbar, text="Underline", command=self.toggle_underline)
        underline_button.pack(side="left", padx=5)

        bullet_button = MinimalCTkButton(self.toolbar, text="Bullet List", command=self.toggle_bullet_list)
        bullet_button.pack(side="left", padx=5)

        numbered_button = MinimalCTkButton(self.toolbar, text="Numbered List", command=self.toggle_numbered_list)
        numbered_button.pack(side="left", padx=5)

        # === Create the text widget ===
        self.text_widget = tk.Text(self, wrap="word", font=("Helvetica", 12), height=4)
        self.text_widget.pack(fill="x", padx=5, pady=5)

        # Insert any initial text (if any)
        self.text_widget.insert("1.0", initial_text)
        self.text_widget.bind("<KeyRelease>", self.update_text_height)
        
        # ▶️ **NEW**: whenever our widget is resized, recalc height
        self.text_widget.bind("<Configure>", lambda e: self.update_text_height())
        # --- Resize dynamically on content ---
        self.update_text_height()  # Initial height
        # Run once on init and bind to typing
        
        self.text_widget.tag_configure("bold", font=("Helvetica", 12, "bold"))
        self.text_widget.tag_configure("italic", font=("Helvetica", 12, "italic"))
        self.text_widget.tag_configure("underline", font=("Helvetica", 12, "underline"))
        self.text_widget.tag_configure("left", justify="left")
        self.text_widget.tag_configure("center", justify="center")
        self.text_widget.tag_configure("right", justify="right")
    
    def update_text_height(self, event=None):
        lines = int(self.text_widget.count("1.0", "end", "displaylines")[0])
        clamped = max(1, min(lines, 100))
        self.text_widget.configure(height=clamped)
    # ----------------------
    # Formatting Functions
    # ----------------------
    def toggle_bold(self):
        try:
            start = self.text_widget.index("sel.first")
            end = self.text_widget.index("sel.last")
            if "bold" in self.text_widget.tag_names(start):
                self.text_widget.tag_remove("bold", start, end)
            else:
                self.text_widget.tag_add("bold", start, end)
        except tk.TclError:
            pass

    def toggle_italic(self):
        try:
            start = self.text_widget.index("sel.first")
            end = self.text_widget.index("sel.last")
            if "italic" in self.text_widget.tag_names(start):
                self.text_widget.tag_remove("italic", start, end)
            else:
                self.text_widget.tag_add("italic", start, end)
        except tk.TclError:
            pass

    def toggle_underline(self):
        try:
            start = self.text_widget.index("sel.first")
            end = self.text_widget.index("sel.last")
            if "underline" in self.text_widget.tag_names(start):
                self.text_widget.tag_remove("underline", start, end)
            else:
                self.text_widget.tag_add("underline", start, end)
        except tk.TclError:
            pass

    def change_font_size(self):
        try:
            new_size = simpledialog.askinteger("Font Size", "Enter new font size:", minvalue=6, maxvalue=72)
            if new_size:
                start = self.text_widget.index("sel.first")
                end = self.text_widget.index("sel.last")
                for tag in self.text_widget.tag_names(start):
                    if tag.startswith("size_"):
                        self.text_widget.tag_remove(tag, start, end)
                new_tag = f"size_{new_size}"
                self.text_widget.tag_configure(new_tag, font=("Helvetica", new_size))
                self.text_widget.tag_add(new_tag, start, end)
        except tk.TclError:
            pass

    def change_text_color(self):
        try:
            color = colorchooser.askcolor()[1]
            if color:
                start = self.text_widget.index("sel.first")
                end = self.text_widget.index("sel.last")
                for tag in self.text_widget.tag_names(start):
                    if tag.startswith("color_"):
                        self.text_widget.tag_remove(tag, start, end)
                new_tag = f"color_{color}"
                self.text_widget.tag_configure(new_tag, foreground=color)
                self.text_widget.tag_add(new_tag, start, end)
        except tk.TclError:
            pass

    def align_left(self):
        try:
            start = self.text_widget.index("sel.first")
            end = self.text_widget.index("sel.last")
            self.text_widget.tag_add("left", start, end)
        except tk.TclError:
            pass

    def align_center(self):
        try:
            start = self.text_widget.index("sel.first")
            end = self.text_widget.index("sel.last")
            self.text_widget.tag_add("center", start, end)
        except tk.TclError:
            pass

    def align_right(self):
        try:
            start = self.text_widget.index("sel.first")
            end = self.text_widget.index("sel.last")
            self.text_widget.tag_add("right", start, end)
        except tk.TclError:
            pass

    def toggle_bullet_list(self):
        try:
            start_index = self.text_widget.index("sel.first linestart")
            end_index = self.text_widget.index("sel.last lineend")
            lines = self.text_widget.get(start_index, end_index).splitlines()

            bullet_mode = all(line.startswith("• ") for line in lines if line.strip() != "")
            new_text = ""
            for line in lines:
                if bullet_mode:
                    # Remove bullet if present
                    if line.startswith("• "):
                        new_text += line[2:] + "\n"
                    else:
                        new_text += line + "\n"
                else:
                    # Add bullet if not present
                    if not line.startswith("• "):
                        new_text += "• " + line + "\n"
                    else:
                        new_text += line + "\n"
            self.text_widget.delete(start_index, end_index)
            self.text_widget.insert(start_index, new_text)
        except tk.TclError:
            pass

    def toggle_numbered_list(self):
        import re
        try:
            start_index = self.text_widget.index("sel.first linestart")
            end_index = self.text_widget.index("sel.last lineend")
            lines = self.text_widget.get(start_index, end_index).splitlines()
            number_pattern = re.compile(r"^\d+\.\s")
            number_mode = all(number_pattern.match(line) for line in lines if line.strip() != "")
            new_text = ""
            if number_mode:
                for line in lines:
                    new_text += number_pattern.sub("", line) + "\n"
            else:
                for i, line in enumerate(lines, start=1):
                    new_text += f"{i}. " + line + "\n"
            self.text_widget.delete(start_index, end_index)
            self.text_widget.insert(start_index, new_text)
        except tk.TclError:
            pass

    # ----------------------
    # Helper Methods to Save/Load Formatting
    # ----------------------
    def get_text_data(self):
        """Returns a dict with plain text and *integer* formatting ranges."""
        text = self.text_widget.get("1.0", "end-1c")
        tags = ["bold", "italic", "underline", "left", "center", "right"]
        formatting = {}

        for tag in tags:
            formatting[tag] = []
            ranges = self.text_widget.tag_ranges(tag)
            # ranges comes back as [start1, end1, start2, end2, ...]
            for i in range(0, len(ranges), 2):
                start_idx = str(ranges[i])
                end_idx   = str(ranges[i+1])
                start_off = self._index_to_offset(start_idx)
                end_off   = self._index_to_offset(end_idx)
                formatting[tag].append((start_off, end_off))

        return {"text": text, "formatting": formatting}

    def load_text_data(self, data):
        """Loads text and applies formatting from RTF-JSON (with numeric offsets)."""
        # 1) Clear existing content and insert all text
        self.text_widget.delete("1.0", "end")
        text = data.get("text", "") if isinstance(data, dict) else str(data)
        self.text_widget.insert("1.0", text)
        
        # 2) Apply each formatting run, converting numeric offsets to Tk indices
        formatting = data.get("formatting", {}) if isinstance(data, dict) else {}
        for tag, runs in formatting.items():
            for start, end in runs:
                # Convert numeric offsets into "1.0 + N chars"
                try:
                    s = int(start)
                    e = int(end)
                    idx1 = f"1.0 + {s} chars"
                    idx2 = f"1.0 + {e} chars"
                except (ValueError, TypeError):
                    # If already in "line.char" form, use directly
                    idx1 = start
                    idx2 = end
                self.text_widget.tag_add(tag, idx1, idx2)
        self.after(100, self.update_text_height)
    def get_text(self):
        """For backward compatibility, return plain text."""
        return self.text_widget.get("1.0", "end-1c")
    
    def _index_to_offset(self, index_str):
        """
        Turn a Tk index like "3.14" (line 3, column 14) into a
        single integer offset in the full self.text_widget content.
        """
        # Split "line.col" into ints
        line, col = map(int, index_str.split('.'))
        # Grab all text up through that line
        full = self.text_widget.get("1.0", "end-1c")
        lines = full.split('\n')
        # Sum lengths (+1 for each newline) of all *previous* lines:
        prev = sum(len(l) + 1 for l in lines[:line-1])
        # Then add the column offset on this line:
        return prev + col
