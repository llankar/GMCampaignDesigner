
import customtkinter as ctk
import tkinter as tk
from .places_model import load_template

class EditPlaceWindow(ctk.CTkToplevel):
    def __init__(self, master, data, creation_mode=False):
        super().__init__(master)
        self.data = data
        self.saved = False
        self.template = load_template()

        self.title(f'{"Create" if creation_mode else "Edit"} Place')
        
        self.minsize(1280, 720)
        self.transient(master)
        self.lift()
        self.focus_force()

        self.fields = {}

        for field in self.template["fields"]:
            ctk.CTkLabel(self, text=field["name"]).pack()
            widget = self.create_field_widget(field, data.get(field["name"], field.get("default", "")))
            widget.pack(pady=2)
            self.fields[field["name"]] = widget

        save_button = ctk.CTkButton(self, text="Save", command=self.save_data)
        save_button.pack(pady=5)

    def create_field_widget(self, field, value):
        if field["type"] == "text":
            widget = ctk.CTkEntry(self)
            widget.insert(0, value)

        elif field["type"] == "longtext":
            frame = ctk.CTkFrame(self)
            text_widget = tk.Text(frame, height=6, wrap="word")
            text_widget.insert("1.0", value)
            text_widget.pack(fill="both", expand=True)
            widget = frame
            widget.text_widget = text_widget

        elif field["type"] == "choice":
            widget = ctk.CTkComboBox(self, values=field.get("options", []))
            widget.set(value)

        elif field["type"] == "boolean":
            widget = ctk.CTkCheckBox(self, text="Yes")
            if value:
                widget.select()
            else:
                widget.deselect()

        else:
            widget = ctk.CTkEntry(self)
            widget.insert(0, value)

        return widget

    def save_data(self):
        for field in self.template["fields"]:
            widget = self.fields[field["name"]]
            if field["type"] in ["text", "choice"]:
                self.data[field["name"]] = widget.get()
            elif field["type"] == "longtext":
                self.data[field["name"]] = widget.text_widget.get("1.0", "end").strip()
            elif field["type"] == "boolean":
                self.data[field["name"]] = widget.get() == "1"

        self.saved = True
        self.destroy()
