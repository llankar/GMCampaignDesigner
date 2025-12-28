import json

from modules.ai.local_ai_client import LocalAIClient
from modules.handouts.newsletter_generator import build_newsletter_payload
from modules.helpers.logging_helper import log_info, log_module_import, log_warning

log_module_import(__name__)


def _coerce_payload(payload, language, style):
    if isinstance(payload, dict):
        scenario_title = payload.get("scenario_title")
        if scenario_title:
            sections = payload.get("sections")
            return build_newsletter_payload(scenario_title, sections, language, style)
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


def _format_item_line(item):
    if isinstance(item, dict):
        title = str(item.get("Title") or item.get("Name") or "").strip()
        text = str(item.get("Text") or item.get("Description") or "").strip()
        if title and text:
            return f"- {title}: {text}"
        if title:
            return f"- {title}"
        if text:
            return f"- {text}"
        related = item.get("Related")
        if isinstance(related, dict) and related:
            related_parts = []
            for key, entries in related.items():
                names = []
                for entry in entries or []:
                    if isinstance(entry, dict) and entry.get("Name"):
                        names.append(str(entry.get("Name")).strip())
                    elif entry:
                        names.append(str(entry).strip())
                if names:
                    related_parts.append(f"{key}: {', '.join(names)}")
            if related_parts:
                return f"- Related: {'; '.join(related_parts)}"
        return None
    if item is None:
        return None
    text = str(item).strip()
    return f"- {text}" if text else None


def _render_plain_newsletter(payload, language, style):
    title_parts = ["Newsletter"]
    if language:
        title_parts.append(f"Langue: {language}")
    if style:
        title_parts.append(f"Style: {style}")
    lines = [" - ".join(title_parts)]
    for section_name, items in (payload or {}).items():
        if not items:
            continue
        lines.append("")
        lines.append(str(section_name))
        for item in items:
            line = _format_item_line(item)
            if line:
                lines.append(line)
    return "\n".join(lines).strip()


def generate_newsletter_ai(payload, language, style):
    resolved_payload = _coerce_payload(payload, language, style)
    fallback_render = _render_plain_newsletter(resolved_payload, language, style)

    if not resolved_payload:
        return fallback_render

    section_names = [str(name).strip() for name in resolved_payload.keys() if str(name).strip()]
    section_list = ", ".join(section_names) if section_names else "Aucune"

    prompt = (
        "Tu es un assistant qui rédige une newsletter de campagne RPG pour les joueurs.\n"
        f"Langue: {language or 'français'}\n"
        f"Ton / style: {style or 'neutre'}\n"
        f"Sections activées: {section_list}\n"
        "Rappel: no spoilers. Ne révèle pas de secrets, surprises ou twists.\n\n"
        "Utilise uniquement les informations fournies ci-dessous. "
        "Ne réécris pas de contenu inventé. "
        "Retourne un texte clair, agréable à lire, avec des titres de section.\n\n"
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
