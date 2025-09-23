import json
import os
import threading
import customtkinter as ctk
from tkinter import messagebox, filedialog

from modules.helpers.text_helpers import ai_text_to_rtf_json
from modules.generic.generic_model_wrapper import GenericModelWrapper
from modules.ai.local_ai_client import LocalAIClient
from modules.helpers.logging_helper import (
    log_function,
    log_info,
    log_methods,
    log_module_import,
    log_warning,
)

log_module_import(__name__)


@log_function
def parse_json_relaxed(payload: str):
    """Parse JSON from a possibly noisy AI response."""
    if not payload:
        raise RuntimeError("Empty AI response")
    text = payload.strip()
    if text.startswith("```"):
        # Strip optional markdown fences
        import re as _re

        text = _re.sub(r"^```(json)?", "", text, flags=_re.IGNORECASE).strip()
        text = text.rstrip("`").strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    start = None
    for idx, ch in enumerate(text):
        if ch in "[{":
            start = idx
            break
    if start is None:
        raise RuntimeError("Failed to locate JSON in response")
    snippet = text[start:]
    for end in range(len(snippet), max(len(snippet) - 2000, 0), -1):
        try:
            return json.loads(snippet[:end])
        except Exception:
            continue
    raise RuntimeError("Failed to parse JSON from AI response")


def _normalize_creature_payload(payload):
    """Return the creature list from various payload shapes."""
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("creatures", "Creatures"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
    raise ValueError("Payload must be a list of creatures or contain a 'creatures' array")


def _to_longtext(value):
    """Convert plain strings into the rich-text JSON structure used by the DB."""
    if isinstance(value, dict) and "text" in value:
        return value
    if isinstance(value, (list, dict)):
        try:
            value = json.dumps(value, ensure_ascii=False, indent=2)
        except Exception:
            value = str(value)
    return ai_text_to_rtf_json(str(value) if value is not None else "")


@log_function
def import_creature_records(payload) -> int:
    """Persist a list (or wrapped dict) of creature entries into the database."""
    creatures = _normalize_creature_payload(payload)
    if not creatures:
        raise ValueError("No creatures found in payload")

    wrapper = GenericModelWrapper("creatures")
    existing = wrapper.load_items()
    new_items = []
    for raw in creatures:
        if not isinstance(raw, dict):
            continue
        item = {
            "Name": raw.get("Name", "Unnamed"),
            "Type": raw.get("Type", ""),
            "Description": _to_longtext(raw.get("Description", "")),
            "Weakness": _to_longtext(raw.get("Weakness", "")),
            "Powers": _to_longtext(raw.get("Powers", "")),
            "Stats": _to_longtext(raw.get("Stats", "")),
            "Background": _to_longtext(raw.get("Background", "")),
            "Genre": raw.get("Genre", ""),
            "Portrait": raw.get("Portrait", ""),
        }
        new_items.append(item)
    if not new_items:
        raise ValueError("No valid creature entries were provided")

    wrapper.save_items(existing + new_items)
    return len(new_items)


@log_function
def import_creatures_from_json(raw_text: str) -> int:
    """Parse JSON text containing creature definitions and import them into the DB."""
    data = parse_json_relaxed(raw_text)
    return import_creature_records(data)


@log_methods
class CreatureImportWindow(ctk.CTkToplevel):
    """Window allowing AI-assisted import of creature data from PDFs or pasted text."""

    def __init__(self, master=None):
        super().__init__(master)
        self.title("Import Creatures from PDF")
        self.geometry("600x600")
        self.transient(master)
        self.grab_set()
        self.focus_force()

        instruction = ctk.CTkLabel(
            self,
            text="Paste creature text/JSON or import a PDF to extract creatures via AI.",
        )
        instruction.pack(pady=(10, 0), padx=10)

        self.textbox = ctk.CTkTextbox(self, wrap="word", height=400, fg_color="#2B2B2B", text_color="white")
        self.textbox.pack(fill="both", expand=True, padx=10, pady=10)

        btn_row = ctk.CTkFrame(self)
        btn_row.pack(fill="x", padx=10, pady=(0, 10))
        self.btn_import_pdf = ctk.CTkButton(btn_row, text="Import PDF via AI", command=self.import_pdf_via_ai)
        self.btn_import_pdf.pack(side="left", padx=5)
        self.btn_ai_parse = ctk.CTkButton(btn_row, text="AI Parse Text", command=self.ai_parse_textarea)
        self.btn_ai_parse.pack(side="left", padx=5)
        self.btn_import_text = ctk.CTkButton(btn_row, text="Save Pasted JSON", command=self.import_pasted_json)
        self.btn_import_text.pack(side="right", padx=5)

        status_row = ctk.CTkFrame(self)
        status_row.pack(fill="x", padx=10, pady=(0, 10))
        self.progress = ctk.CTkProgressBar(status_row, mode="indeterminate")
        self.progress.pack(fill="x", side="left", expand=True)
        self.status_label = ctk.CTkLabel(status_row, text="Idle")
        self.status_label.pack(side="right", padx=(8, 0))

    def import_pasted_json(self):
        text = self.textbox.get("1.0", "end-1c").strip()
        if not text:
            messagebox.showwarning("No Data", "Please paste JSON describing creatures first.")
            return
        try:
            self._set_status("Importing creatures from JSON...")
            self._busy(True)
            count = import_creatures_from_json(text)
            messagebox.showinfo("Success", f"Imported {count} creature(s) from pasted JSON.")
        except Exception as exc:
            messagebox.showerror("Import Error", str(exc))
        finally:
            self._busy(False)
            self._set_status("Idle")

    def import_pdf_via_ai(self):
        try:
            path = filedialog.askopenfilename(
                title="Select Creature PDF",
                filetypes=[("PDF Files", "*.pdf"), ("All Files", "*.*")],
            )
        except Exception as exc:
            messagebox.showerror("PDF Selection Error", str(exc))
            return
        if not path:
            return

        def worker():
            try:
                self._set_status("Extracting PDF text...")
                text = self._extract_pdf_text(path)
                if not text or len(text.strip()) < 50:
                    self._warn("Empty PDF", "Could not extract meaningful text from the PDF.")
                    return
                self._ai_extract_and_import(text, source_label=os.path.basename(path))
            except Exception as exc:
                self._error("AI Import Error", str(exc))
            finally:
                self._busy(False)
                self._set_status("Idle")

        self._busy(True)
        threading.Thread(target=worker, daemon=True).start()

    def ai_parse_textarea(self):
        raw = self.textbox.get("1.0", "end-1c").strip()
        if not raw:
            messagebox.showwarning("No Text", "Please paste creature source text first.")
            return

        def worker():
            try:
                self._ai_extract_and_import(raw, source_label="Pasted Text")
            except Exception as exc:
                self._error("AI Parse Error", str(exc))
            finally:
                self._busy(False)
                self._set_status("Idle")

        self._set_status("Parsing text with AI...")
        self._busy(True)
        threading.Thread(target=worker, daemon=True).start()

    # --- Internal helpers -------------------------------------------------
    def _extract_pdf_text(self, path: str) -> str:
        try:
            try:
                import PyPDF2 as pypdf  # type: ignore
            except Exception:
                import pypdf as pypdf  # type: ignore
            chunks = []
            with open(path, "rb") as handle:
                reader = pypdf.PdfReader(handle)
                for page in reader.pages:
                    try:
                        chunks.append(page.extract_text() or "")
                    except Exception:
                        continue
            return "\n".join(chunks)
        except Exception as exc:
            log_warning(f"PDF extraction failed: {exc}", func_name="CreatureImportWindow._extract_pdf_text")
            raise

    def _ai_extract_and_import(self, raw_text: str, source_label: str = ""):
        log_info(f"Running creature AI import for {source_label or 'input'}", func_name="CreatureImportWindow._ai_extract_and_import")
        self._set_status("Contacting AI...")
        client = LocalAIClient()

        wrapper = GenericModelWrapper("creatures")
        existing = wrapper.load_items()
        stats_examples = []
        for entry in existing:
            stats_val = entry.get("Stats")
            if isinstance(stats_val, dict):
                stats_val = stats_val.get("text", "")
            if isinstance(stats_val, str) and stats_val.strip():
                stats_examples.append({
                    "Name": entry.get("Name", ""),
                    "Stats": stats_val.strip(),
                })
            if len(stats_examples) >= 3:
                break

        schema = {
            "creatures": [
                {
                    "Name": "text",
                    "Type": "text(optional)",
                    "Description": "longtext(optional)",
                    "Weakness": "longtext(optional)",
                    "Powers": "longtext(optional)",
                    "Stats": "stat block text",
                    "Background": "longtext(optional)",
                    "Genre": "text(optional)",
                    "Portrait": "url or file(optional)",
                }
            ]
        }

        prompt = (
            "You are an assistant that extracts creature stat blocks from tabletop RPG PDFs.\n"
            "Return STRICT JSON only using the schema below.\n"
            "Important: For every creature, copy the statistics directly from the PDF into the 'Stats' field.\n"
            "Do not invent numbers or abilities—leave the field empty if the PDF omits them.\n"
            "Preserve line breaks so the stat block stays readable.\n\n"
            "Schema:\n" + json.dumps(schema, ensure_ascii=False, indent=2) + "\n\n"
            "Examples of Stats formatting from the current database:\n" + json.dumps(stats_examples, ensure_ascii=False, indent=2) + "\n\n"
            f"Source: {source_label or 'Unknown'}\n"
            "PDF text (may be truncated):\n" + raw_text[:50000]
        )

        response = client.chat([
            {"role": "system", "content": "Extract structured creature information as strict JSON."},
            {"role": "user", "content": prompt},
        ])

        parsed = parse_json_relaxed(response)
        creatures = _normalize_creature_payload(parsed)
        count = import_creature_records(creatures)

        pretty = json.dumps({"creatures": creatures}, ensure_ascii=False, indent=2)
        self._set_text(pretty)
        self._info("Import Complete", f"Imported {count} creature(s) from {source_label or 'AI input'}.")

    def _set_text(self, value: str):
        def _do():
            try:
                self.textbox.delete("1.0", "end")
                self.textbox.insert("1.0", value)
            except Exception:
                pass
        self.after(0, _do)

    def _set_status(self, text: str):
        def _do():
            try:
                self.status_label.configure(text=text)
            except Exception:
                pass
        self.after(0, _do)

    def _busy(self, active: bool):
        def _do():
            try:
                if active:
                    self.progress.start()
                else:
                    self.progress.stop()
                state = "disabled" if active else "normal"
                for btn in (self.btn_import_pdf, self.btn_ai_parse, self.btn_import_text):
                    try:
                        btn.configure(state=state)
                    except Exception:
                        pass
            except Exception:
                pass
        self.after(0, _do)

    def _info(self, title: str, message: str):
        self.after(0, lambda: messagebox.showinfo(title, message))

    def _warn(self, title: str, message: str):
        self.after(0, lambda: messagebox.showwarning(title, message))

    def _error(self, title: str, message: str):
        self.after(0, lambda: messagebox.showerror(title, message))
