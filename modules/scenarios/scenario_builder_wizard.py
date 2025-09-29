import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

from modules.generic.generic_list_selection_view import GenericListSelectionView
from modules.generic.generic_model_wrapper import GenericModelWrapper
from modules.helpers.logging_helper import log_module_import, log_info
from modules.helpers.template_loader import load_template
from modules.scenarios.scenario_graph_editor import ScenarioGraphEditor


log_module_import(__name__)


class WizardStep(ctk.CTkFrame):
    """Base class for wizard steps with state synchronization hooks."""

    def load_state(self, state):  # pragma: no cover - UI synchronization
        """Populate widgets using the shared wizard ``state``."""

    def save_state(self, state):  # pragma: no cover - UI synchronization
        """Persist widget values into the shared wizard ``state``."""
        return True


class WizardScenarioGraphEditor(ScenarioGraphEditor):
    """Scenario graph editor variant that keeps changes in-memory for the wizard."""

    def __init__(
        self,
        master,
        state_ref,
        on_state_change,
        scenario_wrapper,
        npc_wrapper,
        creature_wrapper,
        place_wrapper,
        *args,
        **kwargs,
    ):
        self._state_ref = state_ref
        self._state_callback = on_state_change
        super().__init__(
            master,
            scenario_wrapper=scenario_wrapper,
            npc_wrapper=npc_wrapper,
            creature_wrapper=creature_wrapper,
            place_wrapper=place_wrapper,
            *args,
            **kwargs,
        )

    def init_toolbar(self):  # pragma: no cover - UI layout
        toolbar = ctk.CTkFrame(self)
        toolbar.pack(fill="x", padx=5, pady=5)
        ctk.CTkLabel(toolbar, text="Scene Planning", font=ctk.CTkFont(size=15, weight="bold")).pack(
            side="left", padx=5
        )
        ctk.CTkButton(toolbar, text="Reset Zoom", command=self.reset_zoom).pack(side="left", padx=5)

    def _save_scenario_changes(self):  # pragma: no cover - simple callback
        if not self.scenario:
            return
        if isinstance(self._state_ref, dict):
            self._state_ref.clear()
            self._state_ref.update(self.scenario)
        if callable(self._state_callback):
            self._state_callback(self._state_ref)


class BasicInfoStep(WizardStep):
    def __init__(self, master):
        super().__init__(master)
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        form = ctk.CTkFrame(self)
        form.grid(row=0, column=0, sticky="nsew", padx=20, pady=(20, 10))

        ctk.CTkLabel(form, text="Scenario Title", anchor="w").pack(fill="x", pady=(0, 4))
        self.title_var = ctk.StringVar()
        self.title_entry = ctk.CTkEntry(form, textvariable=self.title_var)
        self.title_entry.pack(fill="x", pady=(0, 12))

        ctk.CTkLabel(form, text="Summary", anchor="w").pack(fill="x", pady=(0, 4))
        self.summary_text = ctk.CTkTextbox(form, height=160)
        self.summary_text.pack(fill="both", expand=True, pady=(0, 12))

        ctk.CTkLabel(form, text="Secrets", anchor="w").pack(fill="x", pady=(0, 4))
        self.secret_text = ctk.CTkTextbox(form, height=120)
        self.secret_text.pack(fill="both", expand=True, pady=(0, 12))

    def load_state(self, state):  # pragma: no cover - UI synchronization
        self.title_var.set(state.get("Title", ""))
        self.summary_text.delete("1.0", "end")
        self.summary_text.insert("1.0", state.get("Summary", ""))
        secret_val = state.get("Secrets") or state.get("Secret") or ""
        self.secret_text.delete("1.0", "end")
        self.secret_text.insert("1.0", secret_val)

    def save_state(self, state):  # pragma: no cover - UI synchronization
        state["Title"] = self.title_var.get().strip()
        state["Summary"] = self.summary_text.get("1.0", "end").strip()
        secrets = self.secret_text.get("1.0", "end").strip()
        state["Secrets"] = secrets
        state["Secret"] = secrets  # ScenarioGraphEditor expects the singular key
        if "Scenes" not in state or state["Scenes"] is None:
            state["Scenes"] = []
        return True


class GraphPlanningStep(WizardStep):
    def __init__(
        self,
        master,
        state,
        scenario_wrapper,
        npc_wrapper,
        creature_wrapper,
        place_wrapper,
    ):
        super().__init__(master)
        self._state = state
        self._scenario_wrapper = scenario_wrapper
        self.editor = WizardScenarioGraphEditor(
            self,
            state,
            self._handle_state_change,
            scenario_wrapper,
            npc_wrapper,
            creature_wrapper,
            place_wrapper,
        )
        self.editor.pack(fill="both", expand=True, padx=10, pady=10)
        self._loaded_state = None

    def _handle_state_change(self, state):  # pragma: no cover - UI callback
        if isinstance(state, dict):
            self._state.clear()
            self._state.update(state)

    def load_state(self, state):  # pragma: no cover - UI synchronization
        state.setdefault("Secret", state.get("Secrets", ""))
        state.setdefault("Scenes", state.get("Scenes", []) or [])
        state.setdefault("NPCs", state.get("NPCs", []) or [])
        state.setdefault("Places", state.get("Places", []) or [])
        state.setdefault("Creatures", state.get("Creatures", []) or [])
        if state is not self._loaded_state:
            self.editor.load_scenario(state)
            self._loaded_state = state

    def save_state(self, state):  # pragma: no cover - UI synchronization
        scenario = self.editor.scenario or {}
        for key in ("Title", "Summary", "Secret", "Secrets", "Scenes", "NPCs", "Places", "Creatures", "Factions", "Objects"):
            if key in scenario and scenario[key] is not None:
                state[key] = scenario[key]
        return True


class EntityLinkingStep(WizardStep):
    ENTITY_FIELDS = {
        "npcs": ("NPCs", "NPC"),
        "places": ("Places", "Place"),
        "factions": ("Factions", "Faction"),
        "creatures": ("Creatures", "Creature"),
        "objects": ("Objects", "Item"),
    }

    def __init__(self, master, wrappers):
        super().__init__(master)
        self.wrappers = wrappers
        self.selected = {field: [] for field, _ in self.ENTITY_FIELDS.values()}
        self.listboxes = {}

        container = ctk.CTkFrame(self)
        container.pack(fill="both", expand=True, padx=10, pady=10)
        container.grid_columnconfigure((0, 1), weight=1, uniform="entities")

        for idx, (entity_type, (field, label)) in enumerate(self.ENTITY_FIELDS.items()):
            frame = ctk.CTkFrame(container)
            row, col = divmod(idx, 2)
            frame.grid(row=row, column=col, sticky="nsew", padx=8, pady=8)
            frame.grid_rowconfigure(1, weight=1)
            frame.grid_columnconfigure(0, weight=1)

            ctk.CTkLabel(frame, text=f"Linked {label}s", anchor="w", font=ctk.CTkFont(size=14, weight="bold")).grid(
                row=0, column=0, sticky="w", padx=6, pady=(6, 4)
            )

            listbox = tk.Listbox(frame, activestyle="none")
            listbox.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 6))
            self.listboxes[field] = listbox

            btn_row = ctk.CTkFrame(frame)
            btn_row.grid(row=2, column=0, sticky="ew", padx=6, pady=(0, 8))
            btn_row.grid_columnconfigure((0, 1), weight=1)

            ctk.CTkButton(
                btn_row,
                text="Add",
                command=lambda et=entity_type, f=field: self.open_selector(et, f),
            ).grid(row=0, column=0, padx=4, pady=2, sticky="ew")

            ctk.CTkButton(
                btn_row,
                text="Remove",
                command=lambda f=field: self.remove_selected(f),
            ).grid(row=0, column=1, padx=4, pady=2, sticky="ew")

    def open_selector(self, entity_type, field):  # pragma: no cover - UI interaction
        wrapper = self.wrappers[entity_type]
        template = load_template(entity_type)
        top = ctk.CTkToplevel(self)
        top.title(f"Select {field}")
        top.geometry("900x600")
        selection = GenericListSelectionView(
            top,
            entity_type,
            wrapper,
            template,
            on_select_callback=lambda et, name, f=field, win=top: self._on_entity_selected(f, name, win),
        )
        selection.pack(fill="both", expand=True)
        top.transient(self.winfo_toplevel())
        top.grab_set()

    def _on_entity_selected(self, field, name, window):  # pragma: no cover - UI callback
        if not name:
            return
        items = self.selected.setdefault(field, [])
        if name not in items:
            items.append(name)
            self.refresh_list(field)
        try:
            window.destroy()
        except Exception:
            pass

    def remove_selected(self, field):  # pragma: no cover - UI interaction
        listbox = self.listboxes.get(field)
        if not listbox:
            return
        selection = listbox.curselection()
        if not selection:
            return
        selected_items = self.selected.get(field, [])
        for index in reversed(selection):
            try:
                del selected_items[index]
            except IndexError:
                continue
        self.refresh_list(field)

    def refresh_list(self, field):  # pragma: no cover - UI helper
        listbox = self.listboxes.get(field)
        if not listbox:
            return
        listbox.delete(0, tk.END)
        for name in self.selected.get(field, []):
            listbox.insert(tk.END, name)

    def load_state(self, state):  # pragma: no cover - UI synchronization
        for entity_type, (field, _) in self.ENTITY_FIELDS.items():
            values = state.get(field) or []
            if isinstance(values, str):
                values = [values]
            self.selected[field] = list(dict.fromkeys(values))
            self.refresh_list(field)

    def save_state(self, state):  # pragma: no cover - UI synchronization
        for _, (field, _) in self.ENTITY_FIELDS.items():
            state[field] = list(dict.fromkeys(self.selected.get(field, [])))
        return True


class ReviewStep(WizardStep):
    def __init__(self, master):
        super().__init__(master)
        self.text = ctk.CTkTextbox(self, state="disabled")
        self.text.pack(fill="both", expand=True, padx=20, pady=20)

    def load_state(self, state):  # pragma: no cover - UI synchronization
        summary_lines = [
            f"Title: {state.get('Title', 'Untitled Scenario')}",
            "",
            "Summary:",
            state.get("Summary", "(No summary provided.)"),
            "",
            "Secrets:",
            state.get("Secrets", "(No secrets provided.)"),
            "",
            "Scenes:",
        ]

        scenes = state.get("Scenes") or []
        if isinstance(scenes, (list, tuple)) and scenes:
            for idx, scene in enumerate(scenes, start=1):
                if isinstance(scene, dict):
                    title = scene.get("Title") or scene.get("title") or f"Scene {idx}"
                    summary_lines.append(f"  - {title}")
                else:
                    summary_lines.append(f"  - {scene}")
        else:
            summary_lines.append("  (No scenes planned.)")

        for field in ("NPCs", "Creatures", "Places", "Factions", "Objects"):
            entries = state.get(field) or []
            summary_lines.append("")
            summary_lines.append(f"{field}:")
            if entries:
                for name in entries:
                    summary_lines.append(f"  - {name}")
            else:
                summary_lines.append("  (None)")

        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", "\n".join(summary_lines))
        self.text.configure(state="disabled")


class ScenarioBuilderWizard(ctk.CTkToplevel):
    """Interactive wizard guiding users through building a scenario."""

    def __init__(self, master, on_saved=None):
        super().__init__(master)
        self.title("Scenario Builder Wizard")
        self.geometry("1280x860")
        self.minsize(1100, 700)
        self.transient(master)
        self.on_saved = on_saved

        self.state = {
            "Title": "",
            "Summary": "",
            "Secrets": "",
            "Secret": "",
            "Scenes": [],
            "NPCs": [],
            "Creatures": [],
            "Places": [],
            "Factions": [],
            "Objects": [],
        }

        self.scenario_wrapper = GenericModelWrapper("scenarios")
        self.npc_wrapper = GenericModelWrapper("npcs")
        self.creature_wrapper = GenericModelWrapper("creatures")
        self.place_wrapper = GenericModelWrapper("places")
        self.faction_wrapper = GenericModelWrapper("factions")
        self.object_wrapper = GenericModelWrapper("objects")

        self._build_layout()
        self._create_steps()
        self.current_step_index = 0
        self._show_step(0)

    def _build_layout(self):  # pragma: no cover - UI layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self)
        header.grid(row=0, column=0, sticky="ew")
        self.header_label = ctk.CTkLabel(
            header,
            text="Scenario Builder",
            font=ctk.CTkFont(size=18, weight="bold"),
            anchor="w",
        )
        self.header_label.pack(fill="x", padx=20, pady=12)

        self.step_container = ctk.CTkFrame(self)
        self.step_container.grid(row=1, column=0, sticky="nsew")
        self.step_container.grid_rowconfigure(0, weight=1)
        self.step_container.grid_columnconfigure(0, weight=1)

        nav = ctk.CTkFrame(self)
        nav.grid(row=2, column=0, sticky="ew")
        nav.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self.back_btn = ctk.CTkButton(nav, text="Back", command=self.go_back)
        self.back_btn.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        self.next_btn = ctk.CTkButton(nav, text="Next", command=self.go_next)
        self.next_btn.grid(row=0, column=1, padx=10, pady=10, sticky="ew")
        self.finish_btn = ctk.CTkButton(nav, text="Finish", command=self.finish)
        self.finish_btn.grid(row=0, column=2, padx=10, pady=10, sticky="ew")
        self.cancel_btn = ctk.CTkButton(nav, text="Cancel", command=self.cancel)
        self.cancel_btn.grid(row=0, column=3, padx=10, pady=10, sticky="ew")

    def _create_steps(self):  # pragma: no cover - UI layout
        entity_wrappers = {
            "npcs": self.npc_wrapper,
            "places": self.place_wrapper,
            "factions": self.faction_wrapper,
            "creatures": self.creature_wrapper,
            "objects": self.object_wrapper,
        }

        self.steps = [
            ("Basic Information", BasicInfoStep(self.step_container)),
            (
                "Scene Graph",
                GraphPlanningStep(
                    self.step_container,
                    self.state,
                    self.scenario_wrapper,
                    self.npc_wrapper,
                    self.creature_wrapper,
                    self.place_wrapper,
                ),
            ),
            ("Entity Linking", EntityLinkingStep(self.step_container, entity_wrappers)),
            ("Review", ReviewStep(self.step_container)),
        ]

        for _, frame in self.steps:
            frame.grid(row=0, column=0, sticky="nsew")

    def _show_step(self, index):  # pragma: no cover - UI navigation
        title, frame = self.steps[index]
        self.header_label.configure(text=f"Step {index + 1} of {len(self.steps)}: {title}")
        frame.tkraise()
        frame.load_state(self.state)
        self._update_navigation_buttons()

    def _update_navigation_buttons(self):  # pragma: no cover - UI navigation
        self.back_btn.configure(state="normal" if self.current_step_index > 0 else "disabled")
        is_last = self.current_step_index == len(self.steps) - 1
        self.next_btn.configure(state="disabled" if is_last else "normal")
        self.finish_btn.configure(state="normal" if is_last else "disabled")

    def go_next(self):  # pragma: no cover - UI navigation
        step = self.steps[self.current_step_index][1]
        if not step.save_state(self.state):
            return
        self.current_step_index += 1
        self._show_step(self.current_step_index)

    def go_back(self):  # pragma: no cover - UI navigation
        step = self.steps[self.current_step_index][1]
        if not step.save_state(self.state):
            return
        self.current_step_index -= 1
        self._show_step(self.current_step_index)

    def cancel(self):  # pragma: no cover - UI navigation
        self.destroy()

    def finish(self):  # pragma: no cover - UI navigation
        step = self.steps[self.current_step_index][1]
        if not step.save_state(self.state):
            return

        title = (self.state.get("Title") or "").strip()
        if not title:
            messagebox.showwarning("Missing Title", "Please provide a title before saving the scenario.")
            return

        secrets = self.state.get("Secrets") or ""
        scenes = self.state.get("Scenes") or []
        if isinstance(scenes, str):
            scenes = [scenes]

        payload = {
            "Title": title,
            "Summary": self.state.get("Summary", ""),
            "Secrets": secrets,
            "Scenes": scenes,
            "Places": list(dict.fromkeys(self.state.get("Places", []))),
            "NPCs": list(dict.fromkeys(self.state.get("NPCs", []))),
            "Creatures": list(dict.fromkeys(self.state.get("Creatures", []))),
            "Factions": list(dict.fromkeys(self.state.get("Factions", []))),
            "Objects": list(dict.fromkeys(self.state.get("Objects", []))),
        }

        items = self.scenario_wrapper.load_items()
        replaced = False
        for idx, existing in enumerate(items):
            if existing.get("Title") == title:
                if not messagebox.askyesno(
                    "Overwrite Scenario",
                    f"A scenario titled '{title}' already exists. Overwrite it?",
                ):
                    return
                items[idx] = payload
                replaced = True
                break

        if not replaced:
            items.append(payload)

        log_info(
            f"Saving scenario '{title}' via builder wizard (replaced={replaced})",
            func_name="ScenarioBuilderWizard.finish",
        )

        self.scenario_wrapper.save_items(items)
        messagebox.showinfo("Scenario Saved", f"Scenario '{title}' has been saved.")
        if callable(self.on_saved):
            try:
                self.on_saved()
            except Exception:
                pass
        self.destroy()

