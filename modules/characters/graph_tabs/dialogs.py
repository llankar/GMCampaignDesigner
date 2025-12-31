import tkinter as tk
from tkinter import messagebox, simpledialog
import customtkinter as ctk

from .model import build_default_tab, ensure_graph_tabs, get_active_tab, set_active_tab


class ManageGraphTabsDialog(ctk.CTkToplevel):
    def __init__(self, master, graph, on_update):
        super().__init__(master)
        self.title("Manage Tabs")
        self.graph = graph
        self.on_update = on_update
        ensure_graph_tabs(self.graph)

        self.geometry("520x420")
        self.minsize(520, 420)

        container = ctk.CTkFrame(self)
        container.pack(fill="both", expand=True, padx=12, pady=12)

        self.tab_list = tk.Listbox(container, height=12)
        self.tab_list.pack(fill="both", expand=True, padx=8, pady=8)
        self.tab_list.bind("<<ListboxSelect>>", self._on_tab_selected)

        button_row = ctk.CTkFrame(container)
        button_row.pack(fill="x", padx=8, pady=(0, 8))

        ctk.CTkButton(button_row, text="Add", command=self._add_tab).pack(side="left", padx=4)
        ctk.CTkButton(button_row, text="Rename", command=self._rename_tab).pack(side="left", padx=4)
        ctk.CTkButton(button_row, text="Delete", command=self._delete_tab).pack(side="left", padx=4)
        ctk.CTkButton(button_row, text="Move Up", command=self._move_up).pack(side="left", padx=4)
        ctk.CTkButton(button_row, text="Move Down", command=self._move_down).pack(side="left", padx=4)

        action_row = ctk.CTkFrame(container)
        action_row.pack(fill="x", padx=8, pady=(0, 8))
        ctk.CTkButton(action_row, text="Set Active", command=self._set_active).pack(side="left", padx=4)
        ctk.CTkButton(action_row, text="Edit Subset", command=self._edit_subset).pack(side="left", padx=4)
        ctk.CTkButton(action_row, text="Close", command=self._close).pack(side="right", padx=4)

        self._refresh_list()

    def _refresh_list(self):
        self.tab_list.delete(0, tk.END)
        active_id = self.graph.get("active_tab_id")
        for idx, tab in enumerate(self.graph.get("tabs", [])):
            name = tab.get("name", "Tab")
            marker = "* " if tab.get("id") == active_id else ""
            self.tab_list.insert(idx, f"{marker}{name}")

    def _selected_index(self):
        selection = self.tab_list.curselection()
        return selection[0] if selection else None

    def _on_tab_selected(self, _event=None):
        tab = self._selected_tab()
        if not tab:
            return
        if self.graph.get("active_tab_id") == tab.get("id"):
            return
        set_active_tab(self.graph, tab.get("id"))
        self._refresh_list()
        self.on_update()

    def _selected_tab(self):
        idx = self._selected_index()
        if idx is None:
            return None
        return self.graph.get("tabs", [])[idx]

    def _unique_name(self, base_name, current_tab=None):
        existing = {tab.get("name") for tab in self.graph.get("tabs", []) if tab is not current_tab}
        name = base_name
        suffix = 2
        while name in existing:
            name = f"{base_name} ({suffix})"
            suffix += 1
        return name

    def _add_tab(self):
        name = simpledialog.askstring("Add Tab", "Tab name:", parent=self)
        if not name:
            return
        tab = build_default_tab()
        tab["name"] = self._unique_name(name.strip() or "Tab")
        tab["subsetDefinition"] = {"mode": "subset", "node_tags": []}
        self.graph.setdefault("tabs", []).append(tab)
        self.graph["active_tab_id"] = tab["id"]
        self._refresh_list()
        self.on_update()

    def _rename_tab(self):
        tab = self._selected_tab()
        if not tab:
            messagebox.showinfo("Rename Tab", "Select a tab to rename.")
            return
        name = simpledialog.askstring("Rename Tab", "New name:", initialvalue=tab.get("name", "Tab"), parent=self)
        if not name:
            return
        tab["name"] = self._unique_name(name.strip() or "Tab", current_tab=tab)
        self._refresh_list()
        self.on_update()

    def _delete_tab(self):
        tabs = self.graph.get("tabs", [])
        if len(tabs) <= 1:
            messagebox.showwarning("Delete Tab", "At least one tab must remain.")
            return
        tab = self._selected_tab()
        if not tab:
            messagebox.showinfo("Delete Tab", "Select a tab to delete.")
            return
        if not messagebox.askyesno("Delete Tab", f"Delete '{tab.get('name')}'?"):
            return
        tabs.remove(tab)
        if self.graph.get("active_tab_id") == tab.get("id"):
            self.graph["active_tab_id"] = tabs[0]["id"]
        self._refresh_list()
        self.on_update()

    def _move_up(self):
        idx = self._selected_index()
        if idx is None or idx == 0:
            return
        tabs = self.graph.get("tabs", [])
        tabs[idx - 1], tabs[idx] = tabs[idx], tabs[idx - 1]
        self._refresh_list()
        self.tab_list.selection_set(idx - 1)
        self.on_update()

    def _move_down(self):
        idx = self._selected_index()
        tabs = self.graph.get("tabs", [])
        if idx is None or idx >= len(tabs) - 1:
            return
        tabs[idx + 1], tabs[idx] = tabs[idx], tabs[idx + 1]
        self._refresh_list()
        self.tab_list.selection_set(idx + 1)
        self.on_update()

    def _set_active(self):
        tab = self._selected_tab()
        if not tab:
            messagebox.showinfo("Set Active", "Select a tab to activate.")
            return
        set_active_tab(self.graph, tab.get("id"))
        self._refresh_list()
        self.on_update()

    def _edit_subset(self):
        tab = self._selected_tab()
        if not tab:
            messagebox.showinfo("Edit Subset", "Select a tab to edit.")
            return
        GraphTabSubsetDialog(self, self.graph, tab, on_save=self._on_subset_save)

    def _on_subset_save(self):
        self.on_update()

    def _close(self):
        self.on_update()
        self.destroy()


class GraphTabSubsetDialog(ctk.CTkToplevel):
    def __init__(self, master, graph, tab, on_save):
        super().__init__(master)
        self.title("Edit Tab Subset")
        self.graph = graph
        self.tab = tab
        self.on_save = on_save

        self.geometry("520x520")
        self.minsize(520, 520)

        container = ctk.CTkFrame(self)
        container.pack(fill="both", expand=True, padx=12, pady=12)

        ctk.CTkLabel(container, text="Saved Search (optional):").pack(anchor="w", padx=8, pady=(4, 0))
        self.search_var = tk.StringVar(value=(self.tab.get("subsetDefinition") or {}).get("search", ""))
        search_entry = ctk.CTkEntry(container, textvariable=self.search_var)
        search_entry.pack(fill="x", padx=8, pady=(0, 8))

        ctk.CTkLabel(container, text="Selected Characters:").pack(anchor="w", padx=8, pady=(4, 0))
        self.node_list = tk.Listbox(container, selectmode="extended", height=18)
        self.node_list.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self.node_tags = []
        for node in self.graph.get("nodes", []):
            name = node.get("entity_name") or node.get("name") or node.get("tag")
            label = f"{name} ({node.get('entity_type', 'entity')})"
            self.node_list.insert(tk.END, label)
            self.node_tags.append(node.get("tag"))

        subset = self.tab.get("subsetDefinition") or {}
        selected_tags = set(subset.get("node_tags") or [])
        for idx, tag in enumerate(self.node_tags):
            if tag in selected_tags:
                self.node_list.selection_set(idx)

        button_row = ctk.CTkFrame(container)
        button_row.pack(fill="x", padx=8, pady=(0, 8))
        ctk.CTkButton(button_row, text="Use All Nodes", command=self._use_all_nodes).pack(side="left", padx=4)
        ctk.CTkButton(button_row, text="Save", command=self._save).pack(side="right", padx=4)
        ctk.CTkButton(button_row, text="Cancel", command=self.destroy).pack(side="right", padx=4)

    def _use_all_nodes(self):
        self.node_list.selection_clear(0, tk.END)
        self.search_var.set("")

    def _save(self):
        selected_indices = self.node_list.curselection()
        selected_tags = [self.node_tags[idx] for idx in selected_indices if idx < len(self.node_tags)]
        search = self.search_var.get().strip()
        if not selected_tags and not search:
            self.tab["subsetDefinition"] = {"mode": "all"}
        else:
            subset = {"mode": "subset", "node_tags": selected_tags}
            if search:
                subset["search"] = search
            self.tab["subsetDefinition"] = subset
        self.on_save()
        self.destroy()
