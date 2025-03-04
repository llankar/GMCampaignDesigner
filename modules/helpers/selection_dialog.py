import customtkinter as ctk

class SelectionDialog(ctk.CTkToplevel):
    def __init__(self, master, title, label, options):
        super().__init__(master)
        self.result = None

        self.title(title)
        self.geometry("400x150")
        self.transient(master)
        self.lift()
        self.focus_force()

        ctk.CTkLabel(self, text=label).pack(pady=10)

        self.combo = ctk.CTkComboBox(self, values=options)
        self.combo.pack(pady=5)
        self.combo.set(options[0] if options else "")

        button_frame = ctk.CTkFrame(self)
        button_frame.pack(pady=10)

        ctk.CTkButton(button_frame, text="OK", command=self.on_ok).pack(side="left", padx=5)
        ctk.CTkButton(button_frame, text="Cancel", command=self.on_cancel).pack(side="right", padx=5)

    def on_ok(self):
        self.result = self.combo.get()
        self.destroy()

    def on_cancel(self):
        self.result = None
        self.destroy()