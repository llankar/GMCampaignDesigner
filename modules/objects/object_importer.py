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


def _normalize_object_payload(payload):
    """Return the equipment list from various payload shapes."""

    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("objects", "equipment", "items", "Equipment", "Items"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
    log_warning(
        f"Unrecognized payload structure for AI import: type={type(payload).__name__}",
        func_name="_normalize_object_payload",
    )
    raise ValueError(
        "Payload must be a list of objects or contain an 'objects' array. Enable application "
        "logging in config/config.ini to inspect the AI response."
    )


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
def import_object_records(payload) -> int:
    """Persist a list (or wrapped dict) of equipment entries into the database."""

    objects = _normalize_object_payload(payload)
    if not objects:
        preview = ""
        try:
            preview = json.dumps(payload, ensure_ascii=False)
        except Exception:
            try:
                preview = str(payload)
            except Exception:
                preview = "<unavailable>"

        if len(preview) > 500:
            preview = preview[:500] + "…"

        log_warning(
            f"AI payload did not contain any object entries. Preview: {preview}",
            func_name="import_object_records",
        )
        raise ValueError(
            "No objects found in payload. Enable application logging in config/config.ini "
            "([Logging] section) to capture the AI response for troubleshooting."
        )

    wrapper = GenericModelWrapper("objects")
    existing = wrapper.load_items()

    new_items = []
    for raw in objects:
        if not isinstance(raw, dict):
            continue
        item = {
            "Name": raw.get("Name", "Unnamed Object"),
            "Description": _to_longtext(raw.get("Description", "")),
            "Stats": _to_longtext(raw.get("Stats", "")),
            "Secrets": _to_longtext(raw.get("Secrets", "")),
            "Portrait": raw.get("Portrait", ""),
        }
        new_items.append(item)

    if not new_items:
        raise ValueError("No valid object entries were provided")

    wrapper.save_items(existing + new_items)
    return len(new_items)


@log_function
def import_objects_from_json(raw_text: str) -> int:
    """Parse JSON text containing object definitions and import them into the DB."""

    data = parse_json_relaxed(raw_text)
    return import_object_records(data)


@log_methods
class ObjectImportWindow(ctk.CTkToplevel):
    """Window allowing AI-assisted import of equipment objects from PDFs or pasted text."""

    def __init__(self, master=None):
        super().__init__(master)
        self.title("Import Equipment from PDF")
        self.geometry("600x600")
        self.transient(master)
        self.grab_set()
        self.focus_force()

        instruction = ctk.CTkLabel(
            self,
            text="Paste equipment JSON/text or import a PDF to extract objects via AI.",
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
            messagebox.showwarning("No Data", "Please paste JSON describing objects first.")
            return
        try:
            self._set_status("Importing objects from JSON...")
            self._busy(True)
            count = import_objects_from_json(text)
            messagebox.showinfo("Success", f"Imported {count} object(s) from pasted JSON.")
        except Exception as exc:
            messagebox.showerror("Import Error", str(exc))
        finally:
            self._busy(False)
            self._set_status("Idle")

    def import_pdf_via_ai(self):
        try:
            path = filedialog.askopenfilename(
                title="Select Equipment PDF",
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
                pages = self._extract_pdf_text(path)
                if not pages or not any(page.strip() for page in pages):
                    self._warn("Empty PDF", "Could not extract meaningful text from the PDF.")
                    return
                combined_objects = []
                total_imported = 0
                basename = os.path.basename(path)
                for index in range(0, len(pages), 2):
                    chunk_text = "\n".join(pages[index : index + 2]).strip()
                    if not chunk_text:
                        continue
                    start_page = index + 1
                    end_page = min(index + 2, len(pages))
                    label = f"{basename} p{start_page}-{end_page}"
                    self._set_status(f"Processing {label}...")
                    objects, count = self._ai_extract_and_import(
                        chunk_text,
                        source_label=label,
                        update_text=False,
                    )
                    if objects:
                        combined_objects.extend(objects)
                    total_imported += count

                if not combined_objects:
                    self._warn("No Objects Imported", "AI did not return any objects for the PDF.")
                    return

                pretty = json.dumps({"objects": combined_objects}, ensure_ascii=False, indent=2)
                self._set_text(pretty)
                self._info(
                    "Import Complete",
                    f"Imported {total_imported} object(s) from {basename}.",
                )
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
            messagebox.showwarning("No Text", "Please paste equipment source text first.")
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
    def _extract_pdf_text(self, path: str) -> list[str]:
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
            return chunks
        except Exception as exc:
            log_warning(f"PDF extraction failed: {exc}", func_name="ObjectImportWindow._extract_pdf_text")
            raise

    def _ai_extract_and_import(self, raw_text: str, source_label: str = "", *, update_text: bool = True):
        log_info(
            f"Running object AI import for {source_label or 'input'}",
            func_name="ObjectImportWindow._ai_extract_and_import",
        )
        self._set_status("Contacting AI...")
        client = LocalAIClient()

        wrapper = GenericModelWrapper("objects")
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
            "objects": [
                {
                    "Name": "text",
                    "Description": "longtext (narrative details from the PDF)",
                    "Stats": "stat block or table values copied verbatim",
                    "Secrets": "longtext(optional)",
                    "Portrait": "url or filename(optional)",
                }
            ]
        }

        hints = "\n".join(
            f"- {sample['Name']}: {sample['Stats'][:120]}" for sample in stats_examples
        )

        prompt = (
            "You are an assistant that extracts tabletop RPG equipment entries from PDFs.\n"
            "Return STRICT JSON only using the schema below.\n"
            "For every object, capture both its descriptive text AND any numeric/stat blocks from tables.\n"
            "If description and stats appear separately, merge them into 'Description' and 'Stats' respectively without losing detail.\n"
            "Do not invent values—leave fields blank if the PDF omits them. Preserve line breaks inside the 'Stats' text so tables stay readable.\n\n"
            "Schema:\n" + json.dumps(schema, ensure_ascii=False, indent=2) + "\n\n"
        )
        if hints:
            prompt += "Existing stats examples for context:\n" + hints + "\n\n"
        prompt += (
            f"Source: {source_label or 'Unknown'}\n"
            "PDF text (may be truncated):\n" + raw_text[:5_000_000]
        )

        response = client.chat([
            {"role": "system", "content": "Extract structured equipment information as strict JSON."},
            {"role": "user", "content": prompt},
        ])

        parsed = parse_json_relaxed(response)
        objects = _normalize_object_payload(parsed)
        count = import_object_records(objects)

        if update_text:
            pretty = json.dumps({"objects": objects}, ensure_ascii=False, indent=2)
            self._set_text(pretty)
            self._info(
                "Import Complete",
                f"Imported {count} object(s) from {source_label or 'AI input'}.",
            )

        return objects, count

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
