def format_longtext(text, max_lines=3, max_length=60):
    lines = []
    current_line = ""

    for word in text.split():
        if len(current_line) + len(word) + 1 > max_length:
            lines.append(current_line)
            current_line = word
            if len(lines) >= max_lines:
                lines[-1] += "…"
                break
        else:
            current_line += (" " if current_line else "") + word

    if len(lines) < max_lines:
        lines.append(current_line)

    return "\n".join(lines)
