import re

_SECTION_DEFINITIONS = (
    ("key beats", "Key beats", "🎯"),
    ("conflicts/obstacles", "Conflicts/obstacles", "⚔️"),
    ("clues/hooks", "Clues/hooks", "🧩"),
    ("transitions", "Transitions", "🔀"),
    ("important locations", "Important locations", "📍"),
    ("involved npcs", "Involved NPCs", "🧑‍🤝‍🧑"),
)

_HEADER_PATTERN = re.compile(
    r"^\s*[-*>#•·●▪]*\s*\**\s*(key beats|conflicts/obstacles|clues/hooks|transitions|important locations|involved npcs)\s*\**\s*:?\s*$",
    re.IGNORECASE,
)

_HEADER_BULLET_PREFIX = re.compile(r"^[•·●▪\-\*]\s*")


def _normalize_line(line):
    return str(line or "").strip()


def _extract_items(section_text):
    lines = [_normalize_line(line) for line in str(section_text or "").splitlines()]
    lines = [line for line in lines if line]
    if not lines:
        return []

    bullet_items = []
    plain_chunks = []
    for line in lines:
        bullet_match = re.match(r"^[-*•–—]\s*(.+)$", line)
        numbered_match = re.match(r"^\d+[\.)]\s*(.+)$", line)
        if bullet_match:
            bullet_items.append(bullet_match.group(1).strip())
        elif numbered_match:
            bullet_items.append(numbered_match.group(1).strip())
        else:
            plain_chunks.append(line)

    if bullet_items:
        return [item for item in bullet_items if item]

    merged = " ".join(plain_chunks)
    candidates = [part.strip(" -•\t") for part in re.split(r"(?:\s*;\s+|\s{2,}|\n+)", merged) if part.strip()]
    if len(candidates) == 1:
        sentence_candidates = [part.strip() for part in re.split(r"(?<=[.!?])\s+", candidates[0]) if part.strip()]
        if len(sentence_candidates) > 1:
            candidates = sentence_candidates
    return candidates


def parse_scene_body_sections(body_text):
    """Parse scene body text into intro + known thematic sections."""
    lines = str(body_text or "").splitlines()
    intro_lines = []
    sections_buffer = {}
    current_key = None

    for raw_line in lines:
        line = raw_line.rstrip()
        line_without_bullet = _HEADER_BULLET_PREFIX.sub("", line, count=1)
        header_match = _HEADER_PATTERN.match(line_without_bullet)
        if header_match:
            current_key = header_match.group(1).strip().lower()
            sections_buffer.setdefault(current_key, [])
            continue

        if current_key is None:
            intro_lines.append(line)
        else:
            sections_buffer[current_key].append(line)

    sections = []
    for key, title, emoji in _SECTION_DEFINITIONS:
        raw_text = "\n".join(sections_buffer.get(key, [])).strip()
        if not raw_text:
            continue
        sections.append(
            {
                "key": key,
                "title": title,
                "emoji": emoji,
                "raw_text": raw_text,
                "items": _extract_items(raw_text),
            }
        )

    intro_text = "\n".join(intro_lines).strip()
    return {
        "intro_text": intro_text,
        "sections": sections,
        "has_sections": bool(sections),
    }
