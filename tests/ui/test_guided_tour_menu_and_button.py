from modules.ui.menu.menu_sections import build_menu_specs


class AppStub:
    entity_definitions = {}

    def __init__(self):
        self.called = 0

    def launch_guided_tour(self):
        self.called += 1

    def __getattr__(self, _name):
        return lambda *args, **kwargs: None


def test_help_menu_guided_tour_calls_launcher():
    app = AppStub()
    specs = build_menu_specs(app)
    help_menu = next(menu for menu in specs if menu.label == "Help")
    guided = next(item for group in help_menu.groups for item in group.items if item.label == "Guided Tour")

    guided.command()
    assert app.called == 1
