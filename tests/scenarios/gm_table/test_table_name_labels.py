"""Tests for GM Table display-name labels."""

from modules.scenarios.gm_table.table_name_labels import build_table_switch_labels


def test_table_switch_labels_keep_duplicate_names_selectable_by_stable_id() -> None:
    """Duplicate display names should become unique labels backed by table ids."""
    names = {
        "table_1": "Main",
        "table_2": "Main",
        "table_3": "Table3",
        "table_4": "Table4",
        "table_5": "Table5",
        "table_6": "Table6",
    }

    labels, id_by_label, labels_by_id = build_table_switch_labels(names.__getitem__)

    assert labels[:2] == ["Main (Main)", "Main (Table2)"]
    assert id_by_label["Main (Main)"] == "table_1"
    assert id_by_label["Main (Table2)"] == "table_2"
    assert labels_by_id["table_2"] == "Main (Table2)"
