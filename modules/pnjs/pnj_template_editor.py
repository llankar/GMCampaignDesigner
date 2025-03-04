import customtkinter as ctk
from tkinter import messagebox
import json
import os

TEMPLATE_PATH = os.path.join("data", "campaign1", "pnj_template.json")

class TemplateEditorWindow(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("Edit NPC Template")
        
        self.minsize(1280,720)
        self.transient(master)
        self.lift()
        self.focus_force()

        self.champ_frames = []
        self.load_template()

        ctk.CTkButton(self, text="Add Field", command=self.add_field).pack(pady=5)
        ctk.CTkButton(self, text="Save Template", command=self.save_template).pack(pady=5)

    def load_template(self):
        if not os.path.exists(TEMPLATE_PATH):
            self.template = {"fields": [{"name": "Name", "type": "text", "default": ""}]}
        else:
            try:
                with open(TEMPLATE_PATH, 'r', encoding='utf-8') as file:
                    content = file.read().strip()
                    if not content:
                        raise ValueError("Empty file")
                    self.template = json.loads(content)
            except (json.JSONDecodeError, ValueError):
                messagebox.showwarning("Corrupted template", "The template file is empty or corrupted. A default template will be created.")
                self.template = {"fields": [{"name": "Name", "type": "text", "default": ""}]}
                self.save_template()

        for field in self.template["fields"]:
            self.add_field(field)

    def add_field(self, field=None):
        frame = ctk.CTkFrame(self)
        frame.pack(fill="x", pady=2, padx=5)

        ctk.CTkLabel(frame, text="Name:").pack(side="left", padx=2)
        name_entry = ctk.CTkEntry(frame, width=120)
        name_entry.pack(side="left", padx=2)

        ctk.CTkLabel(frame, text="Type:").pack(side="left", padx=2)
        type_combobox = ctk.CTkComboBox(frame, values=["text", "longtext", "choice", "boolean"])
        type_combobox.pack(side="left", padx=2)
        type_combobox.bind("<<ComboboxSelected>>", lambda e, f=frame: self.manage_options(f))

        default_entry = ctk.CTkEntry(frame, width=100)
        default_entry.pack(side="left", padx=2)

        options_label = ctk.CTkLabel(frame, text="Options:")
        options_entry = ctk.CTkEntry(frame, width=200)

        if field:
            name_entry.insert(0, field["name"])
            type_combobox.set(field["type"])
            default_entry.insert(0, str(field.get("default", "")))
            if field["type"] == "choice":
                options_label.pack(side="left", padx=2)
                options_entry.pack(side="left", padx=2)
                options_entry.insert(0, ",".join(field.get("options", [])))

        if field and field["name"] == "Name":
            name_entry.configure(state="disabled")  # Name must always exist and be the first field

        remove_button = ctk.CTkButton(frame, text="X", width=30, command=lambda: self.remove_field(frame))
        remove_button.pack(side="right", padx=2)

        self.champ_frames.append((frame, name_entry, type_combobox, default_entry, options_label, options_entry))

    def manage_options(self, frame):
        _, _, type_combobox, _, options_label, options_entry = next(item for item in self.champ_frames if item[0] == frame)
        if type_combobox.get() == "choice":
            options_label.pack(side="left", padx=2)
            options_entry.pack(side="left", padx=2)
        else:
            options_label.pack_forget()
            options_entry.pack_forget()

    def remove_field(self, frame):
        for item in self.champ_frames:
            if item[0] == frame:
                if item[1].get() == "Name":
                    messagebox.showerror("Forbidden", "'Name' field cannot be removed.")
                    return
                self.champ_frames.remove(item)
                frame.destroy()
                break

    def save_template(self):
        fields = []
        for _, name_entry, type_combobox, default_entry, options_label, options_entry in self.champ_frames:
            field = {
                "name": name_entry.get(),
                "type": type_combobox.get(),
                "default": self.convert_default(default_entry.get(), type_combobox.get())
            }
            if field["type"] == "choice":
                field["options"] = [opt.strip() for opt in options_entry.get().split(",") if opt.strip()]
            fields.append(field)

        if fields[0]["name"] != "Name":
            messagebox.showerror("Invalid template", "The first field must always be 'Name'.")
            return

        template = {"fields": fields}
        os.makedirs(os.path.dirname(TEMPLATE_PATH), exist_ok=True)
        with open(TEMPLATE_PATH, 'w', encoding='utf-8') as file:
            json.dump(template, file, indent=4, ensure_ascii=False)

        messagebox.showinfo("Success", "Template saved successfully.")
        self.destroy()

    def convert_default(self, value, field_type):
        if field_type == "boolean":
            return value.lower() in ["true", "yes", "1"]
        return value

def open_template_editor(master):
    TemplateEditorWindow(master)
