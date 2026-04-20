"""Tests for entities group card chip reflow behavior."""

from modules.scenarios.widgets.scene_body import entities_group_card as subject


class _FakeWidget:
    def __init__(self, parent=None, width=80, **_kwargs):
        self.parent = parent
        self.width = width
        self.exists = True
        self.children = []
        self.bound = {}
        self.grid_info = None
        self.config = {}
        if parent is not None and hasattr(parent, "children"):
            parent.children.append(self)

    def pack(self, *args, **kwargs):
        return None

    def pack_forget(self, *args, **kwargs):
        return None

    def grid(self, *args, **kwargs):
        self.grid_info = kwargs

    def grid_forget(self, *args, **kwargs):
        self.grid_info = None

    def bind(self, sequence, callback, add=None):
        self.bound[sequence] = callback

    def after_idle(self, callback):
        callback()

    def winfo_width(self):
        return self.width

    def winfo_reqwidth(self):
        return self.width

    def winfo_exists(self):
        return self.exists

    def grid_columnconfigure(self, *args, **kwargs):
        return None

    def configure(self, **kwargs):
        self.config.update(kwargs)


class _FakeFrame(_FakeWidget):
    pass


class _FakeLabel(_FakeWidget):
    pass


class _FakeButton(_FakeWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config.update(kwargs)


class _FakeFont:
    def __init__(self, *args, **kwargs):
        pass


def _install_fake_ctk(monkeypatch):
    fake_ctk = type(
        "_FakeCTk",
        (),
        {
            "CTkFrame": _FakeFrame,
            "CTkLabel": _FakeLabel,
            "CTkButton": _FakeButton,
            "CTkFont": _FakeFont,
        },
    )
    monkeypatch.setattr(subject, "ctk", fake_ctk)


def test_estimate_columns_uses_container_width():
    chips = [_FakeWidget(width=90), _FakeWidget(width=100), _FakeWidget(width=110)]

    assert subject._estimate_columns(280, chips) == 2


def test_group_card_reflow_keeps_hidden_entities_accessible_in_narrow_viewport(monkeypatch):
    _install_fake_ctk(monkeypatch)

    def _fake_create_entity_chip(parent, **_kwargs):
        return _FakeWidget(parent=parent, width=90)

    monkeypatch.setattr(subject, "create_entity_chip", _fake_create_entity_chip)

    palette = {
        "surface_overlay": "#111",
        "pill_border": "#222",
        "text": "#fff",
        "muted_text": "#888",
        "pill_bg": "#333",
        "surface_card": "#444",
    }

    root = _FakeFrame(width=300)
    card = subject.create_entities_group_card(
        root,
        group_label="NPCs",
        entities=[{"name": f"E{i}"} for i in range(5)],
        palette=palette,
        visible_limit=3,
    )

    chips_container = card.children[1]
    toggle = next(widget for widget in chips_container.children if isinstance(widget, _FakeButton))

    collapsed_visible = [child for child in chips_container.children if child.grid_info is not None]
    assert len(collapsed_visible) == 4  # 3 chips + toggle

    toggle.config["command"]()

    expanded_visible = [child for child in chips_container.children if child.grid_info is not None]
    assert len(expanded_visible) == 6  # 5 chips + toggle
    assert toggle.config["text"] == "Show less"
