from __future__ import annotations

from datetime import datetime


def _clean_text(value: object) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split())


def build_scene_snapshot_entry(
    *,
    timestamp: datetime,
    scene_key: str | None,
    scene_metadata: dict[str, object] | None,
    active_tab: str | None,
) -> str:
    """Return a compact structured line to append to GM notes."""
    metadata = scene_metadata or {}
    scene_label = _clean_text(
        metadata.get("note_title")
        or metadata.get("display_label")
        or scene_key
        or "Scene inconnue"
    )
    scene_summary = _clean_text(metadata.get("description"))
    tab_label = _clean_text(active_tab or "Aucun onglet")

    lines = [f"[{timestamp.strftime('%Y-%m-%d %H:%M')}] SCENE: {scene_label}"]
    if scene_summary:
        lines.append(f"RÉSUMÉ: {scene_summary}")
    lines.append(f"FOCUS: {tab_label}")
    lines.append("ACTION PJ: ")
    lines.append("IMPACT: ")
    lines.append("INDICE: obtenu|raté")
    lines.append("SUITE: ")
    return "\n".join(lines).strip()


def build_session_debrief_entry(
    *,
    scenario_name: str,
    started_at: datetime | None,
    ended_at: datetime,
    completed_scenes: list[str],
    pending_scenes: list[str],
) -> str:
    """Build a lightweight end-of-session summary template."""
    start_text = started_at.strftime("%H:%M") if started_at else "?"
    end_text = ended_at.strftime("%H:%M")
    completed_text = ", ".join(completed_scenes) if completed_scenes else "Aucune"
    pending_text = ", ".join(pending_scenes) if pending_scenes else "Aucune"

    return "\n".join(
        [
            f"=== DÉBRIEF SESSION · {scenario_name} ===",
            f"Plage horaire: {start_text} → {end_text}",
            f"Scènes terminées: {completed_text}",
            f"Scènes en attente: {pending_text}",
            "",
            "Résumé de session:",
            "- ",
            "",
            "Conséquences majeures:",
            "- ",
            "",
            "TODO prochaine session:",
            "- ",
        ]
    ).strip()
