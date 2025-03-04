import customtkinter as ctk
import tkinter as tk
from tkinter import simpledialog, colorchooser
from modules.helpers.custom_buttons import MinimalCTkButton  # Import de notre bouton personnalisé

class RichTextEditor(ctk.CTkFrame):
    def __init__(self, master, initial_text=""):
        super().__init__(master)
        # Global toolbar at the top
        toolbar = ctk.CTkFrame(self)
        toolbar.pack(fill="x", padx=5, pady=5)

        # Bouton Bold avec notre surcharge pour réduire le padding interne
        bold_button = MinimalCTkButton(toolbar, text="Bold", command=self.toggle_bold)
        bold_button.pack(side="left", padx=5)

        # Vous pouvez faire de même pour les autres boutons...
        italic_button = MinimalCTkButton(toolbar, text="Italic", command=self.toggle_italic)
        italic_button.pack(side="left", padx=5)
        
        underline_button = MinimalCTkButton(toolbar, text="Underline", command=self.toggle_underline)
        underline_button.pack(side="left", padx=5)

        # (le reste de l'initialisation reste inchangé)
        size_button = MinimalCTkButton(toolbar, text="Font Size", command=self.change_font_size)
        size_button.pack(side="left", padx=5)
        color_button = MinimalCTkButton(toolbar, text="Text Color", command=self.change_text_color)
        color_button.pack(side="left", padx=5)
        left_button = MinimalCTkButton(toolbar, text="Left", command=self.align_left)
        left_button.pack(side="left", padx=5)
        center_button = MinimalCTkButton(toolbar, text="Center", command=self.align_center)
        center_button.pack(side="left", padx=5)
        right_button = MinimalCTkButton(toolbar, text="Right", command=self.align_right)
        right_button.pack(side="left", padx=5)
        bullet_button = MinimalCTkButton(toolbar, text="Bullet List", command=self.toggle_bullet_list)
        bullet_button.pack(side="left", padx=5)
        numbered_button = MinimalCTkButton(toolbar, text="Numbered List", command=self.toggle_numbered_list)
        numbered_button.pack(side="left", padx=5)

        self.text_widget = tk.Text(self, wrap="word", font=("Helvetica", 12))
        self.text_widget.pack(expand=True, fill="both", padx=5, pady=5)
        self.text_widget.insert("1.0", initial_text)

        self.text_widget.tag_configure("bold", font=("Helvetica", 12, "bold"))
        self.text_widget.tag_configure("italic", font=("Helvetica", 12, "italic"))
        self.text_widget.tag_configure("underline", font=("Helvetica", 12, "underline"))
        self.text_widget.tag_configure("left", justify="left")
        self.text_widget.tag_configure("center", justify="center")
        self.text_widget.tag_configure("right", justify="right")

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
        """Returns a dictionary with the plain text and formatting ranges."""
        text = self.text_widget.get("1.0", "end-1c")
        tags = ["bold", "italic", "underline", "left", "center", "right"]
        formatting = {}
        for tag in tags:
            ranges = self.text_widget.tag_ranges(tag)
            formatting[tag] = []
            for i in range(0, len(ranges), 2):
                start = str(ranges[i])
                end = str(ranges[i+1])
                formatting[tag].append((start, end))
        return {"text": text, "formatting": formatting}

    def load_text_data(self, data):
        """Loads text and applies formatting from a dictionary."""
        self.text_widget.delete("1.0", "end")
        self.text_widget.insert("1.0", data.get("text", ""))
        formatting = data.get("formatting", {})
        for tag, ranges in formatting.items():
            for start, end in ranges:
                self.text_widget.tag_add(tag, start, end)

    def get_text(self):
        """For backward compatibility, return plain text."""
        return self.text_widget.get("1.0", "end-1c")
