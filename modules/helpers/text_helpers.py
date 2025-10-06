import html
import re
from modules.helpers.logging_helper import log_module_import

log_module_import(__name__)

def format_longtext(data, max_length=30000):
    """ Formate un champ longtext pour l'afficher dans une liste (abrégé + multi-lignes). """
    if isinstance(data, dict):
        text = data.get("text", "")
    else:
        text = str(data)

    text = text.replace("\n", " ").strip()

    if len(text) > max_length:
        return text[:max_length] + "..."
    return text

def format_multiline_text(data, max_length=30000):
    """Like format_longtext but *preserves* newlines for HTML <pre‑wrap> output."""
    if isinstance(data, dict):
        text = data.get("text", "")
    else:
        text = str(data)

    # keep your paragraph breaks
    text = text.replace("\r\n", "\n").strip()

    # truncate if too long
    if len(text) > max_length:
        return text[:max_length] + "…"
    return text

def rtf_to_html(rtf):
    """
    Convert RTF-JSON {"text":…, "formatting":…} into HTML, handling:
    - numeric offsets (e.g. "0", "26")
    - Tk indices (e.g. "1.26" for line 1, column 26)
    """
    text = rtf.get("text", "") if isinstance(rtf, dict) else str(rtf)
    fm   = rtf.get("formatting", {}) if isinstance(rtf, dict) else {}

    # Helper: convert "line.char" → absolute offset in text
    def tk_index_to_offset(idx):
        try:
            line_str, char_str = idx.split('.', 1)
            line = int(line_str)
            col  = int(char_str)
        except Exception:
            return None
        # splitlines(True) keeps the trailing '\n'
        lines = text.splitlines(True)
        if line <= 0 or line > len(lines):
            return None
        # sum lengths of preceding lines
        offset = sum(len(lines[i]) for i in range(line - 1)) + col
        return offset

    opens, closes = {}, {}
    # Build maps of opens/closes keyed by integer positions
    for fmt, runs in fm.items():
        for start, end in runs:
            # determine integer offsets s, e
            s = None; e = None
            # try numeric
            try:
                s = int(start)
            except Exception:
                s = tk_index_to_offset(str(start))
            try:
                e = int(end)
            except Exception:
                e = tk_index_to_offset(str(end))
            # fallback
            if s is None or s < 0: s = 0
            if e is None or e < s: e = s
            if s > len(text): s = len(text)
            if e > len(text): e = len(text)
            opens.setdefault(s, []).append(fmt)
            closes.setdefault(e, []).append(fmt)

    out = []
    # Iterate through each character position, inserting tags
    for i, ch in enumerate(text):
        # close tags at this position
        for fmt in closes.get(i, []):
            if fmt in ("bold","italic","underline"):
                tag = {"bold":"strong","italic":"em","underline":"u"}[fmt]
                out.append(f"</{tag}>")
            elif fmt.startswith("size_") or fmt.startswith("color_"):
                out.append("</span>")
            elif fmt in ("left","center","right"):
                out.append("</div>")
            elif fmt in ("bullet","numbered"):
                # lists are handled as text prefixes; no HTML tag here
                pass

        # open tags at this position
        for fmt in opens.get(i, []):
            if fmt in ("bold","italic","underline"):
                tag = {"bold":"strong","italic":"em","underline":"u"}[fmt]
                out.append(f"<{tag}>")
            elif fmt.startswith("size_"):
                size = fmt.split("_",1)[1]
                out.append(f"<span style=\"font-size:{size}px\">")
            elif fmt.startswith("color_"):
                color = fmt.split("_",1)[1]
                out.append(f"<span style=\"color:{color}\">")
            elif fmt in ("left","center","right"):
                out.append(f"<div style=\"text-align:{fmt}\">")
            elif fmt in ("bullet","numbered"):
                # replicate the list prefix in HTML
                prefix = "• " if fmt=="bullet" else "1. "
                out.append(html.escape(prefix))

        # now the character itself
        out.append("<br>" if ch == "\n" else html.escape(ch))

    # close any tags hanging at end-of-text
    for fmt in closes.get(len(text), []):
        if fmt in ("bold","italic","underline"):
            tag = {"bold":"strong","italic":"em","underline":"u"}[fmt]
            out.append(f"</{tag}>")
        elif fmt.startswith("size_") or fmt.startswith("color_"):
            out.append("</span>")
        elif fmt in ("left","center","right"):
            out.append("</div>")
        # bullet/numbered have no closing tag

    return "".join(out)
    
def normalize_rtf_json(rtf, text_widget=None):
    """
    Convert any { text:str, formatting:{ tag:[[s,e],…], … } }
    where s/e might be "line.char" (e.g. "1.26")
    into integer offsets.
    """
    text = rtf.get("text","") if isinstance(rtf, dict) else str(rtf)
    fm   = rtf.get("formatting",{}) if isinstance(rtf, dict) else {}
    new_fm = {}
    # helper to convert "L.C" → offset
    def to_offset(pos):
        if isinstance(pos, str) and "." in pos:
            line, col = map(int, pos.split(".",1))
            # sum lines’ lengths +1 for newline:
            lines = text.split("\n")
            return sum(len(l)+1 for l in lines[:line-1]) + col
        return int(pos)
    for tag, ranges in fm.items():
        new_ranges = []
        for start,end in ranges:
            new_ranges.append([ to_offset(start), to_offset(end) ])
        new_fm[tag] = new_ranges
    return {"text": text, "formatting": new_fm}


def ai_text_to_rtf_json(raw_text):
    """
    Convert an AI answer (plain text with light Markdown/HTML) to our RTF-JSON:
    {"text": str, "formatting": { tag: [(start,end), ...], ... }}

    Supported inline markers:
    - Bold: **text**, __text__, <b>text</b>, <strong>text</strong>
    - Italic: *text*, _text_, <i>text</i>, <em>text</em>
    - Underline: ++text++, <u>text</u>

    Block helpers:
    - Headings: #, ##, ### → size_22/18/16 on the full line text
    - Bullets: lines starting with "- " or "* " are turned into "• " prefix
    - Numbered: lines starting with "1. ", "2) ", etc. are kept as-is

    Returns formatting with numeric offsets suitable for RichTextEditor.load_text_data.
    """
    if raw_text is None:
        raw_text = ""

    # Normalize newlines
    text = str(raw_text).replace("\r\n", "\n").replace("\r", "\n")

    formatting = {}

    def add_run(tag, start, end):
        if start is None or end is None or end <= start:
            return
        formatting.setdefault(tag, []).append((start, end))

    # Regexes for numbered list and headings
    numbered_re = re.compile(r"^(\s*)(\d+)[\.)]\s+")
    heading_map = [
        (re.compile(r"^\s*#\s+"), "size_22"),
        (re.compile(r"^\s*##\s+"), "size_18"),
        (re.compile(r"^\s*###\s+"), "size_16"),
    ]

    out_chars = []
    out_pos = 0

    def process_inline(line):
        """Return (rendered_line, inline_runs) where inline_runs is [(tag,start,end), ...] relative to start of this rendered line."""
        i = 0
        rendered = []
        runs = []
        # stacks store starting offset in rendered text for an open tag
        stack = {
            "bold": [],
            "italic": [],
            "underline": [],
        }

        def open_tag(tag):
            stack[tag].append(len(rendered))

        def close_tag(tag):
            if stack[tag]:
                start = stack[tag].pop()
                end = len(rendered)
                if end > start:
                    runs.append((tag, start, end))

        L = len(line)
        while i < L:
            ch = line[i]

            # HTML-like tags
            if line.startswith("<strong>", i):
                open_tag("bold"); i += 8; continue
            if line.startswith("</strong>", i):
                close_tag("bold"); i += 9; continue
            if line.startswith("<b>", i):
                open_tag("bold"); i += 3; continue
            if line.startswith("</b>", i):
                close_tag("bold"); i += 4; continue
            if line.startswith("<em>", i):
                open_tag("italic"); i += 4; continue
            if line.startswith("</em>", i):
                close_tag("italic"); i += 5; continue
            if line.startswith("<i>", i):
                open_tag("italic"); i += 3; continue
            if line.startswith("</i>", i):
                close_tag("italic"); i += 4; continue
            if line.startswith("<u>", i):
                open_tag("underline"); i += 3; continue
            if line.startswith("</u>", i):
                close_tag("underline"); i += 4; continue

            # Markdown-like markers (order matters for multi-char)
            if line.startswith("**", i):
                # toggle bold
                if stack["bold"]:
                    close_tag("bold")
                else:
                    open_tag("bold")
                i += 2; continue
            if line.startswith("__", i):
                # treat as bold (common in MD)
                if stack["bold"]:
                    close_tag("bold")
                else:
                    open_tag("bold")
                i += 2; continue
            if line.startswith("++", i):
                if stack["underline"]:
                    close_tag("underline")
                else:
                    open_tag("underline")
                i += 2; continue
            if ch == "*":
                if stack["italic"]:
                    close_tag("italic")
                else:
                    open_tag("italic")
                i += 1; continue
            if ch == "_":
                if stack["italic"]:
                    close_tag("italic")
                else:
                    open_tag("italic")
                i += 1; continue

            # default: copy character
            rendered.append(ch)
            i += 1

        # Close any unclosed tags at end-of-line (best-effort)
        for tag, arr in stack.items():
            while arr:
                start = arr.pop()
                end = len(rendered)
                if end > start:
                    runs.append((tag, start, end))

        return ("".join(rendered), runs)

    lines = text.split("\n")
    for li, raw_line in enumerate(lines):
        line = raw_line
        size_tag = None
        bullet_prefix = ""

        # Headings (check from largest to smallest? we mapped in order #, ##, ### above)
        # Use most specific first: ###, then ##, then #
        if re.match(r"^\s*###\s+", line):
            line = re.sub(r"^\s*###\s+", "", line)
            size_tag = "size_16"
        elif re.match(r"^\s*##\s+", line):
            line = re.sub(r"^\s*##\s+", "", line)
            size_tag = "size_18"
        elif re.match(r"^\s*#\s+", line):
            line = re.sub(r"^\s*#\s+", "", line)
            size_tag = "size_22"

        # Bulleted list markers: - or * followed by space (honor leading whitespace)
        m_bullet = re.match(r"^(\s*)([-*])\s+", line)
        if m_bullet:
            indent = m_bullet.group(1)
            # remove marker
            line = line[m_bullet.end():]
            bullet_prefix = indent + "• "

        # Numbered list: keep numeric prefix, just normalize spacing
        # (we don't add formatting tags; the textual prefix is enough)
        # Already matched bullet? skip numbered check in that case
        if not m_bullet:
            m_num = numbered_re.match(line)
            if m_num:
                # normalize to "<indent><n>. "
                indent, n = m_num.group(1), m_num.group(2)
                line = indent + f"{n}. " + line[m_num.end():]

        rendered, inline_runs = process_inline(line)

        # Write into global buffer and collect runs with absolute offsets
        prefix_len = len(bullet_prefix)
        line_start = out_pos
        if bullet_prefix:
            out_chars.append(bullet_prefix)
            out_pos += prefix_len
        if rendered:
            out_chars.append(rendered)
        # Apply inline runs adjusted by prefix_len and current line start
        for tag, s, e in inline_runs:
            add_run(tag, line_start + s + prefix_len, line_start + e + prefix_len)

        # Apply heading size across the whole line (including bullet prefix)
        if size_tag:
            line_len = prefix_len + len(rendered)
            if line_len > 0:
                add_run(size_tag, line_start, line_start + line_len)

        # Advance position; add newline between lines, but not after last line
        out_pos = line_start + prefix_len + len(rendered)
        if li < len(lines) - 1:
            out_chars.append("\n")
            out_pos += 1

    final_text = "".join(out_chars)
    return {"text": final_text, "formatting": formatting}

# --- Robust fallbacks for longtext coercion ---
def _coerce_text(val):
    if val is None:
        return ""
    if isinstance(val, list):
        # Recursively coerce nested longtext fragments so we never display
        # Python reprs (e.g. dictionaries) in the UI when rich-text blocks
        # are provided as arrays of segments.
        return " ".join(
            _coerce_text(x) for x in val if x is not None
        )
    if isinstance(val, dict):
        v = val.get("text", "")
        if isinstance(v, (list, dict)):
            return _coerce_text(v)
        return str(v)
    return str(val)


def coerce_text(val):
    """Return a plain-text representation for longtext-style values.

    Many parts of the UI accept data that may either be a raw string or the
    richer ``{"text": ..., "formatting": ...}`` structure produced by
    importers.  ``coerce_text`` normalises the value so widgets can safely
    display it without worrying about the underlying shape.
    """

    return _coerce_text(val)

def format_longtext(data, max_length=30000):
    text = _coerce_text(data)
    text = text.replace("\n", " ").strip()
    if len(text) > max_length:
        return text[:max_length] + "..."
    return text

def format_multiline_text(data, max_length=30000):
    text = _coerce_text(data)
    text = text.replace("\r\n", "\n").strip()
    if len(text) > max_length:
        return text[:max_length] + "�?�"
    return text
