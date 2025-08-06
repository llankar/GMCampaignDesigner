import tkinter as tk

class ToolTip:
    def __init__(self, widget, text, delay=500):
        self.widget = widget
        self.text = text
        self.delay = delay
        self.tiplabel = None
        self.after_id = None

        widget.bind("<Enter>", self.schedule_wrapper, add="+")
        widget.bind("<Leave>", self.cancel, add="+")
        widget.bind("<ButtonPress>", self.cancel, add="+")

    def schedule_wrapper(self, event=None):
        self.schedule()

    def schedule(self):
        self.cancel()
        self.after_id = self.widget.after(self.delay, self.showtip)

    def cancel(self, event=None):
        if self.after_id:
            self.widget.after_cancel(self.after_id)
            self.after_id = None
        self.hidetip()

    def showtip(self):
        if self.tiplabel or not self.text:
            return

        x = self.widget.winfo_rootx() + 10
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5

        self.tiplabel = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tw.attributes("-topmost", True)

        label = tk.Label(
            tw,
            text=self.text,
            justify="left",
            background="#ffffe0",
            relief="solid",
            borderwidth=1,
            font=("tahoma", "8", "normal"),
            padx=4,
            pady=2
        )
        label.pack()

    def hidetip(self):
        if self.tiplabel:
            self.tiplabel.destroy()
            self.tiplabel = None
