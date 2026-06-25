"""Display helpers for GM Table switch labels."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable

from modules.scenarios.gm_table.table_registry import GM_TABLES


def build_table_switch_labels(
    get_name: Callable[[str], str],
) -> tuple[list[str], dict[str, str], dict[str, str]]:
    """Return unique option labels while keeping stable table ids separate.

    The GM may give multiple table slots the same display name. Option menu labels
    must still be unique so selecting a label can resolve back to one stable table
    id without using the name as a persistence key.
    """
    names_by_id = {table.table_id: get_name(table.table_id) for table in GM_TABLES}
    counts = Counter(names_by_id.values())
    labels_by_id: dict[str, str] = {}
    id_by_label: dict[str, str] = {}
    labels: list[str] = []
    for table in GM_TABLES:
        name = names_by_id[table.table_id]
        label = name if counts[name] == 1 else f"{name} ({table.name})"
        labels_by_id[table.table_id] = label
        id_by_label[label] = table.table_id
        labels.append(label)
    return labels, id_by_label, labels_by_id
