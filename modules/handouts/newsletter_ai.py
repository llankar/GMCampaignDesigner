import json

from modules.ai.local_ai_client import LocalAIClient
from modules.handouts.newsletter_generator import build_newsletter_payload
from modules.handouts.newsletter_plain_renderer import BASE_KEYS, render_plain_newsletter
from modules.helpers.logging_helper import log_info, log_module_import, log_warning

log_module_import(__name__)


def _coerce_payload(payload, language, style):
    if isinstance(payload, dict):
        scenario_title = payload.get("scenario_title")
        if scenario_title:
            sections = payload.get("sections")
            base_text = payload.get("base_text")
            return build_newsletter_payload(scenario_title, sections, language, style, base_text)
        return payload
    if isinstance(payload, (list, tuple)):
        if not payload:
            return {}
        scenario_title = payload[0]
        sections = payload[1] if len(payload) > 1 else None
        if scenario_title:
            return build_newsletter_payload(scenario_title, sections, language, style)
        return {}
    if isinstance(payload, str) and payload.strip():
        return build_newsletter_payload(payload.strip(), None, language, style)
    return {}


def _render_plain_newsletter(payload, language, style):
    return render_plain_newsletter(payload)


def _extract_base_text(payload):
    if not isinstance(payload, dict):
        return ""
    for key, items in payload.items():
        if str(key).strip().lower() not in BASE_KEYS:
            continue
        if isinstance(items, dict):
            text = items.get("Text") or items.get("Description") or items.get("Summary")
            return str(text).strip() if text else ""
        if isinstance(items, (list, tuple)):
            parts = []
            for item in items:
                if isinstance(item, dict):
                    text = item.get("Text") or item.get("Description") or item.get("Summary")
                    if text:
                        parts.append(str(text).strip())
                elif item:
                    parts.append(str(item).strip())
            return "\n".join([part for part in parts if part]).strip()
        if items:
            return str(items).strip()
    return ""


def generate_newsletter_ai(payload, language, style):
    resolved_payload = _coerce_payload(payload, language, style)
    fallback_render = _render_plain_newsletter(resolved_payload, language, style)

    if not resolved_payload:
        return fallback_render

    section_names = [str(name).strip() for name in resolved_payload.keys() if str(name).strip()]
    section_list = ", ".join(section_names) if section_names else "Aucune"
    base_text = _extract_base_text(resolved_payload)

    prompt = (
        "Tu es un assistant qui rédige une newsletter de campagne RPG pour les joueurs.\n"
        "Langue obligatoire: français.\n"
        "Ton: news in-universe (journal local, bulletin, chronique de ville).\n"
        "Longueur: 3 à 4 paragraphes.\n"
        "Interdit: titres, sections, listes, annexes.\n"
        "Intègre naturellement les PNJ et scènes dans le récit, sans énumération finale.\n"
        f"Sections activées: {section_list}\n"
        "Rappel: no spoilers. Ne révèle pas de secrets, surprises ou twists.\n\n"
        "Utilise uniquement les informations fournies ci-dessous. "
        "Ne réécris pas de contenu inventé. Le texte doit être au passé simple.\n"
        "Le texte du MJ doit servir de trame principale; le reste sert d'appoint.\n\n"
        f"Texte du MJ (trame principale):\n{base_text or 'Aucun'}\n\n"
        "Rédige un article de journal in-universe en français, 3 à 4 paragraphes, "
        "sans titres ni listes. Intègre naturellement les PNJ et scènes dans le récit, sans annexes.\n\n"
        "Contenu structuré (JSON):\n"
        f"{json.dumps(resolved_payload, ensure_ascii=False, indent=2)}"
    )

    log_info("Generating AI newsletter", func_name="generate_newsletter_ai")
    try:
        client = LocalAIClient()
        response = client.chat([
            {"role": "system", "content": "Rédige des newsletters RPG claires et sans spoilers."},
            {"role": "user", "content": prompt},
        ])
        if response and response.strip():
            return response.strip()
    except Exception as exc:
        log_warning(f"AI newsletter generation failed: {exc}", func_name="generate_newsletter_ai")

    return fallback_render
