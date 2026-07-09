"""View for random and AI-assisted scenario generation."""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk

from campaign_generator import GENERATOR_FUNCTIONS, export_to_docx
from modules.campaigns.shared.arc_status import DEFAULT_SCENARIO_STATUS
from modules.generic.generic_model_wrapper import GenericModelWrapper
from modules.helpers.logging_helper import log_exception, log_module_import
from modules.scenarios.ai_prompt_library import (
    PromptLibrary,
    PromptQuestion,
    ScenarioPrompt,
)
from modules.scenarios.ai_scenario_generator import (
    AIGenerationError,
    AIScenarioGenerator,
    build_final_prompt,
    parse_generated_scenario,
    validate_required_answers,
)
from modules.scenarios.prompt_library_dialog import PromptLibraryDialog
from modules.scenarios.services.generated_entity_persistence import (
    GeneratedScenarioEntityPersistence,
    scenario_entity_names,
)

log_module_import(__name__)


class ScenarioGeneratorView(ctk.CTkFrame):
    """Frame embedding random and AI prompt-based scenario generation."""

    def __init__(self, parent):
        """Initialize the ScenarioGeneratorView instance."""
        super().__init__(parent)
        self.mode_var = ctk.StringVar(value="Random generator")
        self.setting_var = ctk.StringVar(value=list(GENERATOR_FUNCTIONS.keys())[0])
        self.title_var = ctk.StringVar(value="")
        self.prompt_library = PromptLibrary()
        self.prompts: list[ScenarioPrompt] = []
        self.prompt_var = ctk.StringVar(value="")
        self.question_mode_var = ctk.StringVar(value="Guided")
        self.answer_vars: dict[str, tk.StringVar] = {}
        self.guided_index = 0
        self.guided_answers: dict[str, str] = {}
        self.current_campaign: dict[str, str] | None = None
        self.current_ai_text = ""
        self._load_prompts()
        self._build_widgets()
        self._on_mode_changed(self.mode_var.get())

    def _load_prompts(self) -> None:
        """Load prompt names for the selector."""
        try:
            self.prompts = self.prompt_library.load()
        except Exception as exc:
            log_exception("Failed to load prompt library")
            messagebox.showerror("Prompt Library", str(exc))
            self.prompts = []
        if self.prompts and not self.prompt_var.get():
            self.prompt_var.set(self.prompts[0].name)

    def _build_widgets(self) -> None:
        """Build widgets."""
        top = ctk.CTkFrame(self)
        top.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(top, text="Mode:").pack(side="left")
        ctk.CTkOptionMenu(
            top,
            values=["Random generator", "AI prompt generator"],
            variable=self.mode_var,
            command=self._on_mode_changed,
        ).pack(side="left", padx=5)

        self.random_frame = ctk.CTkFrame(self)
        ctk.CTkLabel(self.random_frame, text="Setting:").pack(side="left")
        ctk.CTkOptionMenu(
            self.random_frame,
            values=list(GENERATOR_FUNCTIONS.keys()),
            variable=self.setting_var,
        ).pack(side="left", padx=5)
        ctk.CTkButton(
            self.random_frame, text="Generate", command=self.generate_campaign
        ).pack(side="left", padx=5)

        self.ai_frame = ctk.CTkFrame(self)
        ctk.CTkLabel(self.ai_frame, text="Prompt:").grid(
            row=0, column=0, sticky="w", padx=8, pady=(8, 4)
        )
        self.prompt_menu = ctk.CTkOptionMenu(
            self.ai_frame,
            values=self._prompt_names(),
            variable=self.prompt_var,
            command=lambda _v: self._render_questions(),
        )
        self.prompt_menu.grid(row=0, column=1, sticky="ew", padx=8, pady=(8, 4))
        ctk.CTkButton(
            self.ai_frame, text="Manage Prompts", command=self._open_prompt_manager
        ).grid(row=0, column=2, padx=8, pady=(8, 4))
        ctk.CTkLabel(self.ai_frame, text="Question mode:").grid(
            row=0, column=3, sticky="w", padx=8, pady=(8, 4)
        )
        ctk.CTkOptionMenu(
            self.ai_frame,
            values=["Guided", "Advanced/manual"],
            variable=self.question_mode_var,
            command=lambda _v: self._render_questions(),
        ).grid(row=0, column=4, padx=8, pady=(8, 4))
        self.ai_frame.grid_columnconfigure(1, weight=1)
        self.questions_frame = ctk.CTkFrame(
            self.ai_frame, fg_color="#243447", corner_radius=12
        )
        self.questions_frame.grid(
            row=1, column=0, columnspan=5, sticky="ew", padx=8, pady=(8, 10)
        )
        self.questions_frame.grid_columnconfigure(0, weight=1)
        self.questions_frame.grid_columnconfigure(1, weight=1)
        actions = ctk.CTkFrame(self.ai_frame)
        actions.grid(row=2, column=0, columnspan=5, sticky="ew", padx=8, pady=(0, 8))
        self.guided_back_btn = ctk.CTkButton(
            actions, text="Back", width=72, command=self._guided_back
        )
        self.guided_back_btn.pack(side="left", padx=4)
        self.guided_primary_btn = ctk.CTkButton(
            actions,
            text="Continue",
            width=180,
            height=36,
            font=("Helvetica", 14, "bold"),
            command=self._guided_primary_action,
        )
        self.guided_primary_btn.pack(side="left", padx=4)
        self.generate_ai_btn = ctk.CTkButton(
            actions, text="Generate with AI", command=self.generate_with_ai
        )
        self.generate_ai_btn.pack(side="left", padx=4)
        self.progress_label = ctk.CTkLabel(actions, text="")
        self.progress_label.pack(side="left", padx=10)

        self.results_frame = ctk.CTkScrollableFrame(self, fg_color="#2c3e50")
        self.results_frame.pack(fill="both", expand=True, padx=10, pady=10)
        self.results_frame.bind("<Configure>", self._resize_ai_result_textbox)
        self.ai_result_text = ctk.CTkTextbox(
            self.results_frame,
            wrap="word",
            height=self._result_textbox_height(),
        )

        bottom = ctk.CTkFrame(self)
        bottom.pack(fill="x", padx=10, pady=(0, 10))
        ctk.CTkLabel(bottom, text="Title:").pack(side="left")
        ctk.CTkEntry(bottom, textvariable=self.title_var).pack(
            side="left", padx=5, fill="x", expand=True
        )
        self.export_btn = ctk.CTkButton(
            bottom, text="Export to DOCX", command=self.export_docx, state="disabled"
        )
        self.export_btn.pack(side="left", padx=5)
        self.add_btn = ctk.CTkButton(
            bottom, text="Save to DB", command=self.add_to_db, state="disabled"
        )
        self.add_btn.pack(side="left", padx=5)
        self._render_questions()

    def _prompt_names(self) -> list[str]:
        return [prompt.name for prompt in self.prompts] or [""]

    def _result_textbox_height(self) -> int:
        """Return a large result textbox height that follows the available panel."""
        fallback_height = 520
        available_height = self.results_frame.winfo_height()
        if available_height <= 1:
            return fallback_height
        return max(fallback_height, available_height - 16)

    def _resize_ai_result_textbox(self, _event: tk.Event | None = None) -> None:
        """Keep generated AI text readable instead of capped at the widget default."""
        if not self.current_ai_text or not self.ai_result_text.winfo_exists():
            return
        self.ai_result_text.configure(height=self._result_textbox_height())

    def _current_prompt(self) -> ScenarioPrompt | None:
        return next(
            (prompt for prompt in self.prompts if prompt.name == self.prompt_var.get()),
            None,
        )

    def _on_mode_changed(self, _value: str) -> None:
        self.random_frame.pack_forget()
        self.ai_frame.pack_forget()
        if self.mode_var.get() == "AI prompt generator":
            self.ai_frame.pack(fill="x", padx=10, pady=(0, 10))
        else:
            self.random_frame.pack(fill="x", padx=10, pady=(0, 10))

    def _open_prompt_manager(self) -> None:
        PromptLibraryDialog(
            self, self.prompt_library, on_change=self._reload_prompts_from_dialog
        )

    def _reload_prompts_from_dialog(self) -> None:
        self._load_prompts()
        self.prompt_menu.configure(values=self._prompt_names())
        if self.prompts:
            self.prompt_var.set(self.prompts[0].name)
        self._render_questions()

    def _render_questions(self) -> None:
        for child in self.questions_frame.winfo_children():
            child.destroy()
        prompt = self._current_prompt()
        self.answer_vars = {}
        if not prompt:
            ctk.CTkLabel(
                self.questions_frame,
                text="No prompt available. Use Manage Prompts to create one.",
                font=("Helvetica", 14, "bold"),
            ).grid(row=0, column=0, sticky="w", padx=16, pady=16)
            self._show_manual_actions()
            return
        questions = prompt.questions
        if self.question_mode_var.get() == "Guided":
            self.guided_index = min(self.guided_index, max(len(questions) - 1, 0))
            if not questions:
                ctk.CTkLabel(
                    self.questions_frame,
                    text="This prompt has no questions.",
                    font=("Helvetica", 14, "bold"),
                ).grid(row=0, column=0, sticky="w", padx=16, pady=16)
                self._show_manual_actions()
                return
            question = questions[self.guided_index]
            self._render_guided_question_card(question, len(questions))
            self._update_guided_actions(prompt)
        else:
            ctk.CTkLabel(
                self.questions_frame,
                text="Advanced answers",
                font=("Helvetica", 16, "bold"),
                anchor="w",
            ).grid(row=0, column=0, columnspan=2, sticky="ew", padx=16, pady=(14, 8))
            for row, question in enumerate(questions, start=1):
                ctk.CTkLabel(self.questions_frame, text=question.label).grid(
                    row=row, column=0, sticky="w", padx=16, pady=4
                )
                var = tk.StringVar(
                    value=self.guided_answers.get(question.key, question.default)
                )
                self.answer_vars[question.key] = var
                ctk.CTkEntry(
                    self.questions_frame,
                    textvariable=var,
                    placeholder_text=self._entry_placeholder(question),
                ).grid(row=row, column=1, sticky="ew", padx=(8, 16), pady=4)
            self._show_manual_actions()

    def _render_guided_question_card(
        self, question: PromptQuestion, question_count: int
    ) -> None:
        """Render the active guided prompt question as a prominent card."""
        ctk.CTkLabel(
            self.questions_frame,
            text=f"Step {self.guided_index + 1} of {question_count}",
            text_color="#9fb3c8",
            font=("Helvetica", 13, "bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=18, pady=(16, 4))
        ctk.CTkLabel(
            self.questions_frame,
            text=question.label,
            font=("Helvetica", 20, "bold"),
            anchor="w",
            justify="left",
            wraplength=1100,
        ).grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 8))
        helper_text = self._question_helper_text()
        if helper_text:
            ctk.CTkLabel(
                self.questions_frame,
                text=helper_text,
                text_color="#b8c7d9",
                font=("Helvetica", 13),
                anchor="w",
                justify="left",
                wraplength=1100,
            ).grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 12))
        var = tk.StringVar(
            value=self.guided_answers.get(question.key, question.default)
        )
        self.answer_vars[question.key] = var
        entry = ctk.CTkEntry(
            self.questions_frame,
            textvariable=var,
            height=42,
            font=("Helvetica", 15),
            placeholder_text=self._entry_placeholder(question),
        )
        entry.grid(row=3, column=0, sticky="ew", padx=18, pady=(0, 18))
        entry.bind("<Return>", lambda _event: self._guided_primary_action())
        entry.focus_set()

    def _question_helper_text(self) -> str:
        """Return contextual helper text for the active guided question."""
        if self.guided_index == 0:
            return "Examples: medfan, sci-fi, modern, Star Wars, Dresden Files, Dragonlance"
        return ""

    def _entry_placeholder(self, question: PromptQuestion) -> str:
        """Build a concise placeholder for scenario prompt answers."""
        if question.default:
            return question.default
        if self.guided_index == 0 or question.key == "scenario_type":
            return "e.g. medfan, sci-fi, modern, Star Wars..."
        return "Type your answer here..."

    def _show_manual_actions(self) -> None:
        """Display the standalone AI generation action outside guided mode."""
        self.guided_back_btn.pack_forget()
        self.guided_primary_btn.pack_forget()
        if not self.generate_ai_btn.winfo_ismapped():
            self.generate_ai_btn.pack(side="left", padx=4, before=self.progress_label)

    def _update_guided_actions(self, prompt: ScenarioPrompt) -> None:
        """Refresh guided navigation buttons for the active prompt/question."""
        primary_text = (
            "Write the scenario"
            if self.guided_index == len(prompt.questions) - 1
            else "Continue"
        )
        self.guided_primary_btn.configure(text=primary_text, state="normal")
        self.generate_ai_btn.pack_forget()
        if not self.guided_back_btn.winfo_ismapped():
            self.guided_back_btn.pack(side="left", padx=4, before=self.progress_label)
        if not self.guided_primary_btn.winfo_ismapped():
            self.guided_primary_btn.pack(
                side="left", padx=4, before=self.progress_label
            )
        self.guided_back_btn.configure(
            state="normal" if self.guided_index > 0 else "disabled"
        )

    def _collect_answers(self) -> dict[str, str]:
        answers = dict(self.guided_answers)
        for key, var in self.answer_vars.items():
            answers[key] = var.get().strip()
        return answers

    def _guided_primary_action(self) -> None:
        prompt = self._current_prompt()
        if not prompt:
            return
        self.guided_answers.update(self._collect_answers())
        if self.guided_index < len(prompt.questions) - 1:
            self.guided_index += 1
            self._render_questions()
            return
        self.generate_with_ai()

    def _guided_back(self) -> None:
        self.guided_answers.update(self._collect_answers())
        if self.guided_index > 0:
            self.guided_index -= 1
            self._render_questions()

    def _clear_results(self) -> None:
        for child in self.results_frame.winfo_children():
            child.destroy()

    def generate_campaign(self) -> None:
        """Generate a legacy random scenario."""
        setting = self.setting_var.get()
        try:
            campaign = GENERATOR_FUNCTIONS[setting]()
        except Exception as exc:
            log_exception("Random scenario generation failed")
            messagebox.showerror("Error", f"Failed to generate scenario: {exc}")
            return
        self.current_campaign = campaign
        self.current_ai_text = ""
        self._clear_results()
        for key, value in campaign.items():
            card = ctk.CTkFrame(self.results_frame, fg_color="#34495e", corner_radius=4)
            title_lbl = ctk.CTkLabel(
                card,
                text=key,
                text_color="#ecf0f1",
                font=("Helvetica", 16, "bold"),
                anchor="w",
            )
            desc_lbl = ctk.CTkLabel(
                card,
                text=value,
                text_color="#bdc3c7",
                justify="left",
                wraplength=1580,
                font=("Helvetica", 14),
            )
            title_lbl.pack(anchor="w", padx=8, pady=(4, 0))
            desc_lbl.pack(anchor="w", fill="x", padx=8, pady=(0, 6))
            card.pack(fill="x", expand=True, padx=5, pady=5)
        self.export_btn.configure(state="normal")
        self.add_btn.configure(state="normal")

    def generate_with_ai(self) -> None:
        """Generate a scenario from the selected AI prompt without freezing the UI."""
        prompt = self._current_prompt()
        if not prompt:
            messagebox.showwarning("No Prompt", "Select or create a prompt first.")
            return
        answers = self._collect_answers()
        missing = validate_required_answers(prompt, answers)
        if missing:
            messagebox.showwarning(
                "Missing Answers", "Please answer: " + ", ".join(missing)
            )
            return
        _final, unresolved = build_final_prompt(prompt, answers)
        if unresolved:
            messagebox.showwarning(
                "Placeholder Warning",
                "Unanswered placeholders: " + ", ".join(unresolved),
            )
        self.generate_ai_btn.configure(state="disabled")
        self.guided_primary_btn.configure(state="disabled")
        self.progress_label.configure(text="Generating with AI...")

        def worker() -> None:
            try:
                result = AIScenarioGenerator().generate(prompt, answers)
            except Exception as exc:
                self.after(0, lambda exc=exc: self._on_ai_error(exc))
                return
            self.after(0, lambda: self._on_ai_success(result))

        threading.Thread(target=worker, daemon=True).start()

    def _on_ai_success(self, text: str) -> None:
        self.generate_ai_btn.configure(state="normal")
        self.guided_primary_btn.configure(state="normal")
        self.progress_label.configure(text="")
        if not text.strip():
            messagebox.showerror("AI Error", "AI provider returned an empty scenario.")
            return
        self.current_ai_text = text.strip()
        parsed = parse_generated_scenario(self.current_ai_text)
        self.current_campaign = self._ai_export_payload(self.current_ai_text)
        if parsed.get("Title") and not self.title_var.get().strip():
            self.title_var.set(str(parsed["Title"]))
        self._clear_results()
        self.ai_result_text = ctk.CTkTextbox(
            self.results_frame,
            wrap="word",
            height=self._result_textbox_height(),
        )
        self.ai_result_text.insert("1.0", self.current_ai_text)
        self.ai_result_text.pack(fill="both", expand=True, padx=5, pady=5)
        self.export_btn.configure(state="normal")
        self.add_btn.configure(state="normal")

    def _on_ai_error(self, exc: Exception) -> None:
        self.generate_ai_btn.configure(state="normal")
        self.guided_primary_btn.configure(state="normal")
        self.progress_label.configure(text="")
        log_exception("AI scenario generation failed")
        if isinstance(exc, AIGenerationError):
            messagebox.showerror("AI Provider Unavailable", str(exc))
        else:
            messagebox.showerror("AI Error", f"Failed to generate scenario: {exc}")

    def _current_result_text(self) -> str:
        if self.current_ai_text and self.ai_result_text.winfo_exists():
            return self.ai_result_text.get("1.0", "end").strip()
        if self.current_campaign:
            return "\n".join(f"{k}: {v}" for k, v in self.current_campaign.items())
        return ""

    def _ai_export_payload(self, text: str) -> dict[str, str]:
        parsed = parse_generated_scenario(text)
        return {"Generated Scenario": text, "Secrets": str(parsed.get("Secrets", ""))}

    def export_docx(self) -> None:
        """Export the current scenario to DOCX."""
        if not self.current_campaign and not self.current_ai_text:
            messagebox.showwarning("No Scenario", "Generate a scenario first.")
            return
        filename = filedialog.asksaveasfilename(
            defaultextension=".docx",
            filetypes=[("Word Document", "*.docx")],
            title="Save Scenario",
        )
        if not filename:
            return
        try:
            payload = (
                self._ai_export_payload(self._current_result_text())
                if self.current_ai_text
                else self.current_campaign
            )
            export_to_docx(payload, filename)
        except Exception as exc:
            log_exception("Scenario DOCX export failed")
            messagebox.showerror("Export Error", str(exc))
            return
        messagebox.showinfo("Exported", "Scenario exported to DOCX.")

    def add_to_db(self) -> None:
        """Save the current scenario to the database."""
        if not self.current_campaign and not self.current_ai_text:
            messagebox.showwarning("No Scenario", "Generate a scenario first.")
            return
        title = self.title_var.get().strip()
        if not title:
            messagebox.showwarning(
                "Missing Title", "Please provide a title for the scenario."
            )
            return
        if self.current_ai_text:
            text = self._current_result_text()
            parsed = parse_generated_scenario(text)
            scenario_entity = {
                "Title": title,
                "Status": DEFAULT_SCENARIO_STATUS,
                "Summary": str(parsed.get("Summary") or text),
                "Secrets": str(parsed.get("Secrets") or ""),
                "Places": scenario_entity_names(parsed.get("Places")),
                "NPCs": scenario_entity_names(parsed.get("NPCs")),
                "Objects": (
                    parsed.get("Objects")
                    if isinstance(parsed.get("Objects"), list)
                    else []
                ),
                "Scenes": (
                    parsed.get("Scenes")
                    if isinstance(parsed.get("Scenes"), list)
                    else []
                ),
            }
        else:
            summary = "\n".join(f"{k}: {v}" for k, v in self.current_campaign.items())
            scenario_entity = {
                "Title": title,
                "Status": DEFAULT_SCENARIO_STATUS,
                "Summary": summary,
                "Secrets": "",
                "Places": [],
                "NPCs": [],
                "Objects": [],
            }
        try:
            wrapper = GenericModelWrapper("scenarios")
            existing = wrapper.load_items()
            if any(
                str(s.get("Title", "")).strip().lower() == title.lower()
                for s in existing
            ):
                messagebox.showwarning(
                    "Duplicate Title",
                    f"A scenario titled '{title}' already exists. Please rename it before saving.",
                )
                return
            existing.append(scenario_entity)
            wrapper.save_items(existing)
            entity_result = GeneratedScenarioEntityPersistence().save_missing_entities(
                scenario_entity,
                parsed if self.current_ai_text else None,
            )
        except Exception as exc:
            log_exception("Scenario database save failed")
            messagebox.showerror("Save Error", str(exc))
            return
        created_bits = []
        if entity_result.npcs_created:
            created_bits.append(f"{len(entity_result.npcs_created)} NPC(s)")
        if entity_result.places_created:
            created_bits.append(f"{len(entity_result.places_created)} place(s)")
        entity_summary = (
            "\nCreated missing entities: " + ", ".join(created_bits)
            if created_bits
            else ""
        )
        messagebox.showinfo(
            "Saved",
            f"Scenario '{title}' added to database.{entity_summary}",
        )
