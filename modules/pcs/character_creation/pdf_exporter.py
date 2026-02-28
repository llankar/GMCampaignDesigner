"""PDF export utilities for Savage Fate character sheets."""

from __future__ import annotations

from pathlib import Path

import fitz  # PyMuPDF


def _write(page: fitz.Page, x: float, y: float, text: str, size: float = 10, bold: bool = False) -> None:
    font = "helv" if not bold else "helv-bold"
    page.insert_text((x, y), text, fontsize=size, fontname=font)


def export_character_pdf(character: dict, rules_result, output_path: str) -> str:
    if not output_path:
        raise ValueError("Chemin de sortie PDF invalide.")

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    doc = fitz.open()
    if doc is None or not hasattr(doc, "new_page"):
        raise RuntimeError("Impossible d'initialiser le document PDF via PyMuPDF.")

    page1 = doc.new_page(width=595, height=842)
    page2 = doc.new_page(width=595, height=842)

    _write(page1, 40, 40, "Savage Fate - Character Creation", 16, bold=True)
    _write(page1, 40, 70, f"Nom: {character.get('name', '')}", 12)
    _write(page1, 40, 90, f"Joueur: {character.get('player', '')}", 12)
    _write(page1, 40, 110, f"Concept: {character.get('concept', '')}", 11)
    _write(page1, 40, 130, f"Défaut: {character.get('flaw', '')}", 11)
    _write(page1, 40, 150, f"{character.get('group_asset', '')}", 11)
    _write(page1, 40, 170, f"Rang: {rules_result.rank_name} (index {rules_result.rank_index})", 11)
    _write(page1, 40, 190, f"Blessures superficielles: {rules_result.superficial_health}", 11)

    _write(page1, 40, 220, "Compétences", 13, bold=True)
    y = 240
    for skill, die in rules_result.skill_dice.items():
        favorite = "★" if skill in set(character.get("favorites") or []) else " "
        _write(page1, 40, y, f"{favorite} {skill}", 10)
        _write(page1, 260, y, die, 10)
        y += 18
        if y > 800:
            break

    _write(page2, 40, 40, "Prouesses", 13, bold=True)
    y = 65
    for idx, feat in enumerate(character.get("feats") or [], start=1):
        _write(page2, 40, y, f"{idx}. {feat.get('name', f'Prouesse {idx}')}", 11, bold=True)
        y += 16
        for option in feat.get("options") or []:
            _write(page2, 55, y, f"- {option}", 10)
            y += 14
        _write(page2, 55, y, f"Limitation: {feat.get('limitation', '')}", 10)
        y += 24

    _write(page2, 40, y, "Équipement", 13, bold=True)
    y += 20
    equipment = character.get("equipment") or {}
    pe_alloc = character.get("equipment_pe") or {}
    _write(page2, 40, y, f"Arme ({pe_alloc.get('weapon', 0)} PE): {equipment.get('weapon', '')}", 10)
    y += 16
    _write(page2, 40, y, f"Armure ({pe_alloc.get('armor', 0)} PE): {equipment.get('armor', '')}", 10)
    y += 16
    _write(page2, 40, y, f"Utilitaire ({pe_alloc.get('utility', 0)} PE): {equipment.get('utility', '')}", 10)

    y += 28
    _write(page2, 40, y, "Avancements", 13, bold=True)
    y += 20
    for i in range(1, 41):
        marker = "X" if i <= int(character.get("advancements", 0)) else " "
        _write(page2, 40, y, f"{i:02d}: [{marker}]", 9)
        y += 14
        if y > 810:
            break

    try:
        doc.save(str(output))
    finally:
        doc.close()
    return str(output)
