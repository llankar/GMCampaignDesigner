from pathlib import Path

from modules.scenarios.gm_table.scenario_board import map_cards
from modules.scenarios.gm_table.scenario_board.map_cards import build_map_cards


class _Wrapper:
    def __init__(self, records):
        self._records = records

    def load_items(self):
        return self._records


def test_build_map_cards_resolves_record_metadata_and_image_size(
    tmp_path: Path, monkeypatch
) -> None:
    image_path = tmp_path / "warehouse.png"
    image_path.write_bytes(b"fake image")

    class _FakeImage:
        width = 320
        height = 180

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(map_cards.Image, "open", lambda _path: _FakeImage())
    wrapper = _Wrapper(
        [
            {
                "Name": "Old Warehouse",
                "Image": str(image_path),
                "Type": "Battlemap",
                "Category": "Urban",
                "Description": "A dockside warehouse with loading bays and upper offices.",
            }
        ]
    )

    cards = build_map_cards(["old warehouse"], wrapper)

    assert len(cards) == 1
    assert cards[0].name == "Old Warehouse"
    assert cards[0].subtitle == "Battlemap • Urban"
    assert cards[0].size_label == "320 × 180"
    assert "dockside warehouse" in cards[0].details


def test_build_map_cards_keeps_unresolved_map_names() -> None:
    cards = build_map_cards(["Hidden Shrine"], _Wrapper([]))

    assert len(cards) == 1
    assert cards[0].name == "Hidden Shrine"
    assert cards[0].size_label == "No image"
