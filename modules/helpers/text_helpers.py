import html

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