import sqlite3
import sys
import types


class _CTkWidget:
    def __init__(self, *args, **kwargs):
        pass

    def pack(self, *args, **kwargs):
        pass

    def grid(self, *args, **kwargs):
        pass

    def configure(self, *args, **kwargs):
        pass


class _CTkTextbox(_CTkWidget):
    def delete(self, *args, **kwargs):
        pass

    def insert(self, *args, **kwargs):
        pass


class _CTkToplevel(_CTkWidget):
    def destroy(self):
        pass


class _StringVar:
    def __init__(self, value=""):
        self._value = value

    def get(self):
        return self._value

    def set(self, value):
        self._value = value


ctk_stub = types.ModuleType("customtkinter")
ctk_stub.CTkToplevel = type("CTkToplevel", (_CTkToplevel,), {})
ctk_stub.CTkFrame = type("CTkFrame", (_CTkWidget,), {})
ctk_stub.CTkLabel = type("CTkLabel", (_CTkWidget,), {})
ctk_stub.CTkEntry = type("CTkEntry", (_CTkWidget,), {})
ctk_stub.CTkTextbox = type("CTkTextbox", (_CTkTextbox,), {})
ctk_stub.CTkButton = type("CTkButton", (_CTkWidget,), {})
ctk_stub.CTkScrollableFrame = type("CTkScrollableFrame", (_CTkWidget,), {})
ctk_stub.CTkOptionMenu = type("CTkOptionMenu", (_CTkWidget,), {})
ctk_stub.CTkFont = lambda *args, **kwargs: None
ctk_stub.StringVar = _StringVar
sys.modules.setdefault("customtkinter", ctk_stub)


from modules.generic import generic_model_wrapper as gmw
from modules.scenarios import scenario_builder_wizard as sbw


class _DummyStep:
    def save_state(self, state):
        return True


def test_finish_persists_secret_aliases(tmp_path, monkeypatch):
    db_path = tmp_path / "campaign.db"

    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE scenarios (Title TEXT PRIMARY KEY)")
    conn.commit()
    conn.close()

    monkeypatch.setattr(gmw, "get_connection", lambda: sqlite3.connect(db_path))
    monkeypatch.setattr(sbw.messagebox, "showwarning", lambda *a, **k: None)
    monkeypatch.setattr(sbw.messagebox, "showinfo", lambda *a, **k: None)
    monkeypatch.setattr(sbw.messagebox, "askyesno", lambda *a, **k: True)

    wizard = sbw.ScenarioBuilderWizard.__new__(sbw.ScenarioBuilderWizard)
    wizard.steps = [("dummy", _DummyStep())]
    wizard.current_step_index = 0
    wizard.state = {
        "Title": "Test Scenario",
        "Summary": "Summary",
        "Secrets": "Hidden truth",
        "Scenes": [],
        "Places": [],
        "NPCs": [],
        "Creatures": [],
        "Factions": [],
        "Objects": [],
    }
    wizard.scenario_wrapper = gmw.GenericModelWrapper("scenarios")
    wizard.on_saved = None
    wizard.destroy = lambda: None

    wizard.finish()

    saved = wizard.scenario_wrapper.load_items()
    assert saved, "Scenario record should be created"
    assert saved[0]["Secrets"] == "Hidden truth"
    assert saved[0]["Secret"] == "Hidden truth"

    conn = sqlite3.connect(db_path)
    try:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(scenarios)")}
    finally:
        conn.close()
    assert {"Secrets", "Secret"}.issubset(columns)
