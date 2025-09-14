import os
import sys
import ast
import re
import time
from pathlib import Path

from PIL import ImageGrab


ROOT = Path(__file__).resolve().parents[1]
MODULES_DIR = ROOT / "modules"
DOCS_DIR = ROOT / "docs"
IMAGES_DIR = DOCS_DIR / "images"


def discover_python_files():
    files = []
    # Include top-level key files
    for name in ["main_window.py", "campaign_generator.py"]:
        p = ROOT / name
        if p.exists():
            files.append(p)
    # Include all module files (skip venv, dist, etc.)
    for p in MODULES_DIR.rglob("*.py"):
        files.append(p)
    return sorted(set(files))


def discover_html_files():
    files = []
    for p in (MODULES_DIR / "web" / "templates").rglob("*.html"):
        files.append(p)
    return sorted(set(files))


def parse_module_api(py_path: Path):
    api = {"module": str(py_path.relative_to(ROOT)), "doc": None, "functions": [], "classes": []}
    try:
        src = py_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return api
    try:
        tree = ast.parse(src)
    except Exception:
        return api
    api["doc"] = ast.get_docstring(tree)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            api["functions"].append({
                "name": node.name,
                "lineno": node.lineno,
                "doc": ast.get_docstring(node) or "",
            })
        elif isinstance(node, ast.ClassDef):
            klass = {
                "name": node.name,
                "lineno": node.lineno,
                "doc": ast.get_docstring(node) or "",
                "methods": [],
            }
            for sub in node.body:
                if isinstance(sub, ast.FunctionDef):
                    klass["methods"].append({
                        "name": sub.name,
                        "lineno": sub.lineno,
                        "doc": ast.get_docstring(sub) or "",
                    })
            api["classes"].append(klass)
    return api


MENU_PATTERNS = [
    re.compile(r"add_command\(\s*label\s*=\s*([\'\"])(?P<label>.*?)(?<!\\)\1", re.S),
    re.compile(r"add_cascade\(\s*label\s*=\s*([\'\"])(?P<label>.*?)(?<!\\)\1", re.S),
]


def parse_context_menus(py_path: Path):
    try:
        src = py_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return []
    menus = []
    # Heuristic: find right-click handlers and nearby menu definitions
    if "<Button-3>" in src or "Menu(" in src:
        labels = []
        for pat in MENU_PATTERNS:
            for m in pat.finditer(src):
                labels.append(m.group("label"))
        if labels:
            menus.append({
                "module": str(py_path.relative_to(ROOT)),
                "items": sorted(set(labels), key=lambda x: labels.index(x)),
            })
    return menus


def parse_html_context_menus(html_path: Path):
    menus = []
    try:
        src = html_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return menus
    # Extract items inside context-menu and link-menu blocks
    for menu_id in ["context-menu", "link-menu"]:
        # Rough extraction: <div id="context-menu"> ... </div>
        block = re.search(rf"<div[^>]+id=\"{menu_id}\"[^>]*>(.*?)</div>", src, re.S | re.I)
        if not block:
            continue
        inner = block.group(1)
        labels = re.findall(r"<li[^>]*>(.*?)</li>", inner, re.S | re.I)
        clean = [re.sub(r"<[^>]+>", "", lbl).strip() for lbl in labels]
        clean = [c for c in clean if c]
        if clean:
            menus.append({
                "module": str(html_path.relative_to(ROOT)),
                "items": clean,
            })
    return menus


def ensure_dirs():
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)


def grab_widget_screenshot(widget, name: str):
    # Update geometry and bring to front
    widget.update_idletasks()
    widget.update()
    # Compute absolute screen bbox
    try:
        x = widget.winfo_rootx()
        y = widget.winfo_rooty()
        w = widget.winfo_width()
        h = widget.winfo_height()
        screen_w = widget.winfo_screenwidth()
        screen_h = widget.winfo_screenheight()
    except Exception:
        return None
    if w <= 0 or h <= 0:
        # Fallback to full screen
        w = screen_w
        h = screen_h
        x = 0
        y = 0

    # If nearly fullscreen, capture entire screen to avoid cutting edges
    fullscreen_like = (abs(w - screen_w) < 40 and abs(h - screen_h) < 80) or (w >= screen_w - 20)
    if fullscreen_like:
        bbox = (0, 0, screen_w, screen_h)
    else:
        margin = 8
        bbox = (
            max(0, x - margin),
            max(0, y - margin),
            min(screen_w, x + w + margin),
            min(screen_h, y + h + margin),
        )
    img_path = IMAGES_DIR / f"{name}.png"
    # Small sleep to ensure visuals are drawn
    time.sleep(0.2)
    try:
        img = ImageGrab.grab(bbox=bbox)
        img.save(img_path)
        return img_path
    except Exception:
        return None


def screenshot_app_views():
    # Run the Tk app in a subprocess-like flow but inside current process
    os.environ["DOCS_MODE"] = "1"
    sys.path.insert(0, str(ROOT))
    try:
        import tkinter as tk
        import customtkinter as ctk
        from main_window import MainWindow
    except Exception as e:
        return {}

    shots = {}

    app = MainWindow()
    app.update()
    shots["main_window"] = str(grab_widget_screenshot(app, "main_window") or "")

    # Sidebar entity views
    for ent in ["scenarios", "pcs", "npcs", "creatures", "factions", "places", "objects", "informations", "clues", "maps"]:
        try:
            app.open_entity(ent)
            app.update()
            shots[f"entity_{ent}"] = str(grab_widget_screenshot(app, f"entity_{ent}") or "")
        except Exception:
            pass

    # Graph editors
    for key, fn in [
        ("npc_graph", app.open_npc_graph_editor),
        ("pc_graph", app.open_pc_graph_editor),
        ("faction_graph", app.open_faction_graph_editor),
        ("scenario_graph", app.open_scenario_graph_editor),
    ]:
        try:
            fn()
            app.update()
            shots[key] = str(grab_widget_screenshot(app, key) or "")
        except Exception:
            pass

    # Scenario generator/importer
    try:
        app.open_scenario_generator()
        app.update()
        shots["scenario_generator"] = str(grab_widget_screenshot(app, "scenario_generator") or "")
    except Exception:
        pass
    try:
        app.open_scenario_importer()
        app.update()
        shots["scenario_importer"] = str(grab_widget_screenshot(app, "scenario_importer") or "")
    except Exception:
        pass

    # Map tool (separate Toplevel)
    try:
        app.map_tool()
        app.update(); app.update_idletasks()
        # The most recent toplevel should be the map tool window
        tops = [w for w in app.winfo_children() if isinstance(w, ctk.CTkToplevel)]
        map_top = tops[-1] if tops else None
        if map_top:
            shots["map_tool_selector"] = str(grab_widget_screenshot(map_top, "map_tool_selector") or "")
            # Try to switch from selector to editor by selecting first available map
            ctrl = getattr(app, 'map_controller', None)
            if ctrl and getattr(ctrl, '_maps', None):
                try:
                    first_map_name = list(ctrl._maps.keys())[0]
                    ctrl._on_display_map("maps", first_map_name)
                    app.update(); app.update_idletasks()
                    shots["map_tool_editor"] = str(grab_widget_screenshot(map_top, "map_tool_editor") or "")
                    # Toggle drawing tools to surface shape controls
                    ctrl._on_drawing_tool_change("Rectangle"); app.update();
                    shots["map_tool_rectangle"] = str(grab_widget_screenshot(map_top, "map_tool_rectangle") or "")
                    ctrl._on_drawing_tool_change("Oval"); app.update();
                    shots["map_tool_oval"] = str(grab_widget_screenshot(map_top, "map_tool_oval") or "")
                    # Back to token mode
                    ctrl._on_drawing_tool_change("Token"); app.update();
                except Exception:
                    pass
    except Exception:
        pass

    # Try GM screen only if possible
    try:
        app.open_gm_screen()
        app.update()
        shots["gm_screen"] = str(grab_widget_screenshot(app, "gm_screen") or "")
    except Exception:
        pass

    # Close app
    try:
        app.destroy()
    except Exception:
        pass

    # Filter out empty paths
    return {k: v for k, v in shots.items() if v}


def build_html(api_data, menu_data, shots):
    def esc(s):
        return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    sections = []

    # Overview
    sections.append(
        """
        <section id="overview">
          <h1>GMCampaignDesigner Documentation</h1>
          <p>This document provides an overview of the application's features, UI, right-click context menus, and a module API reference generated from the source code.</p>
          <p>Version generated on: {ts}</p>
        </section>
        """.format(ts=time.strftime("%Y-%m-%d %H:%M:%S"))
    )

    # UI Screenshots section
    if shots:
        items = []
        for key, path in sorted(shots.items()):
            rel = Path(path).relative_to(DOCS_DIR)
            title = key.replace('_',' ').title()
            items.append(f"<figure class='shot'><img src='{rel.as_posix()}' alt='{esc(title)}' /><figcaption>{esc(title)}</figcaption></figure>")
        sections.append("<section id='screenshots'><h2>UI Screenshots</h2>" + "\n".join(items) + "</section>")

    # Context menus
    if menu_data:
        blocks = []
        for m in menu_data:
            items = ''.join(f"<li>{esc(lbl)}</li>" for lbl in m["items"])
            blocks.append(f"<div class='menu-block'><h3>{esc(m['module'])}</h3><ul>{items}</ul></div>")
        sections.append("<section id='context-menus'><h2>Right-Click Menus</h2>" + "\n".join(blocks) + "</section>")

    # API Reference
    api_blocks = []
    for mod in api_data:
        fn_list = ''.join(
            f"<li><code>{esc(f['name'])}()</code> — {esc(f['doc'])}</li>" for f in mod["functions"]
        )
        class_blocks = []
        for c in mod["classes"]:
            methods = ''.join(
                f"<li><code>{esc(m['name'])}()</code> — {esc(m['doc'])}</li>" for m in c["methods"]
            )
            class_blocks.append(
                f"<div class='class'><h4>class {esc(c['name'])}</h4><p>{esc(c['doc'])}</p><ul>{methods}</ul></div>"
            )
        api_blocks.append(
            f"<section class='module'><h3>{esc(mod['module'])}</h3><p>{esc(mod['doc'])}</p>"
            f"<h4>Functions</h4><ul>{fn_list}</ul>" + ''.join(class_blocks) + "</section>"
        )
    sections.append("<section id='api'><h2>Module API Reference</h2>" + "\n".join(api_blocks) + "</section>")

    html = f"""
<!DOCTYPE html>
<html lang='en'>
<head>
  <meta charset='utf-8' />
  <title>GMCampaignDesigner Documentation</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 24px; color: #111; }}
    h1, h2, h3, h4 {{ color: #0b3d6e; }}
    code {{ background: #f2f4f8; padding: 2px 4px; border-radius: 3px; }}
    section {{ margin-bottom: 36px; }}
    figure.shot {{ margin: 0 0 24px 0; }}
    figure.shot img {{ max-width: 100%; height: auto; border: 1px solid #ddd; border-radius: 4px; display: block; }}
    figure.shot figcaption {{ color: #666; font-size: 0.9em; margin-top: 6px; }}
    .menu-block {{ margin-bottom: 16px; }}
    ul {{ margin-top: 8px; }}
  </style>
  <meta name='viewport' content='width=device-width, initial-scale=1'>
  <meta name='generator' content='generate_docs.py'>
  <meta name='robots' content='noindex'>
  <meta http-equiv='X-UA-Compatible' content='IE=edge' />
  <meta name='description' content='Auto-generated documentation for GMCampaignDesigner'>
  <meta name='theme-color' content='#0b3d6e' />
  <meta name='og:title' content='GMCampaignDesigner Documentation' />
  <meta name='og:type' content='website' />
  <meta name='og:description' content='Auto-generated documentation for GMCampaignDesigner' />
  <meta name='og:image' content='images/main_window.png' />
  <meta name='og:image:alt' content='Main Window Screenshot' />
  <meta name='twitter:card' content='summary_large_image' />
  <meta name='twitter:title' content='GMCampaignDesigner Documentation' />
  <meta name='twitter:image' content='images/main_window.png' />
  <meta name='twitter:image:alt' content='Main Window Screenshot' />
  <meta name='apple-mobile-web-app-title' content='GMCampaignDesigner Docs' />
</head>
<body>
  {''.join(sections)}
</body>
</html>
"""
    return html


def main():
    ensure_dirs()

    files = discover_python_files()
    # Build API data
    api_data = [parse_module_api(p) for p in files]

    # Extract context menus (right-click)
    menu_data = []
    for p in files:
        menu_data.extend(parse_context_menus(p))
    # Include HTML template context menus
    for hp in discover_html_files():
        menu_data.extend(parse_html_context_menus(hp))

    # Try to capture UI screenshots
    shots = screenshot_app_views()

    # Write API + screenshots HTML
    html = build_html(api_data, menu_data, shots)
    (DOCS_DIR / "index.html").write_text(html, encoding="utf-8")
    print(f"Documentation written to: {DOCS_DIR / 'index.html'}")

    # Also write a user manual with curated chapters
    manual = build_user_manual(shots, menu_data, files)
    (DOCS_DIR / "user-manual.html").write_text(manual, encoding="utf-8")
    print(f"User manual written to: {DOCS_DIR / 'user-manual.html'}")


def build_user_manual(shots, menu_data, py_files):
    def img(key, alt=None):
        p = shots.get(key)
        if not p:
            return ""
        rel = Path(p).relative_to(DOCS_DIR).as_posix()
        caption = alt or key.replace('_', ' ').title()
        return f"<figure class='shot'><img class='manual-shot' src='{rel}' alt='{caption}' /><figcaption>{caption}</figcaption></figure>"

    def section(title, body):
        return f"<section><h2 id='{title.lower().replace(' ', '-')}'>{title}</h2>{body}</section>"

    # Helpers to pull right-click menus by area without showing module filenames
    def collect_items(filter_fn):
        items = []
        for m in menu_data:
            if filter_fn(m.get('module', '')):
                items.extend(m.get('items') or [])
        # Deduplicate while preserving order
        seen = set(); out = []
        for it in items:
            if it not in seen:
                seen.add(it); out.append(it)
        return out

    entity_menu = collect_items(lambda mod: 'generic/generic_list_view.py' in mod.replace('\\','/'))
    graph_menu_all = collect_items(lambda mod: any(s in mod.replace('\\','/') for s in [
        'npcs/npc_graph_editor.py','pcs/pc_graph_editor.py','factions/faction_graph_editor.py','scenarios/scenario_graph_editor.py'
    ]))
    map_menu_all = collect_items(lambda mod: 'maps/controllers/display_map_controller.py' in mod.replace('\\','/'))
    clues_menu = collect_items(lambda mod: 'web/templates/clues.html' in mod.replace('\\','/'))

    # Heuristic grouping for graph editor menus
    arrow_items = [i for i in graph_menu_all if 'Arrow' in i]
    node_items = [i for i in graph_menu_all if 'Node' in i or i in ('Change Color','Display Portrait','Display Portrait Window')]
    shape_items_graph = [i for i in graph_menu_all if 'Shape' in i and i not in arrow_items]

    # Heuristic grouping for map tool menus
    map_token_items = [i for i in map_menu_all if 'Token' in i or i in ('Show Portrait','Change Border Color','Resize Token')]
    map_shape_items = [i for i in map_menu_all if 'Shape' in i and i not in map_token_items]

    parts = [
        "<html><head><meta charset='utf-8'><title>GMCampaignDesigner User Manual</title>"
        "<link rel='stylesheet' href='user-manual.css'></head><body>"
        "<header><h1>GMCampaignDesigner — User Manual</h1></header>"
        "<nav>"
        "<a href='#getting-started'>Getting Started</a>"
        "<a href='#ui-overview'>UI Overview</a>"
        "<a href='#managing-entities'>Managing Entities</a>"
        "<a href='#graph-editors'>Graph Editors</a>"
        "<a href='#gm-screen'>GM Screen</a>"
        "<a href='#scenario-tools'>Scenario Tools</a>"
        "<a href='#map-tool'>Map Tool</a>"
        "<a href='#context-menus'>Right-Click Menus</a>"
        "<a href='#tips'>Tips</a>"
        "</nav><div class='container'>"
    ]

    parts.append(section("Getting Started",
        "<ul>"
        "<li>Launch the app: <code>python main_window.py</code>.</li>"
        "<li>Choose or create a campaign database via the left sidebar (Change Data Storage).</li>"
        "<li>Populate PCs, NPCs, Creatures, Places, Objects, Informations, Clues, and Maps.</li>"
        "</ul>" + img("main_window", "Main window")
    ))

    parts.append(section("UI Overview",
        "<p>The left sidebar provides quick access to tools and entity managers."
        " Hover each icon to see its name. Click to open the corresponding manager in the main area."
        " Use the top-right banner toggle (when available) to show PCs at a glance.</p>"
        + "".join(img(f"entity_{k}", f"{k.title()} view") for k in [
            "scenarios","pcs","npcs","creatures","factions","places","objects","informations","clues","maps"
        ])
    ))

    # Managing Entities with right-click menu details
    ent_menu_html = ''.join(f"<li>{i}</li>" for i in entity_menu) if entity_menu else ''
    clues_html = ''
    if clues_menu:
        # Map clues menus into card/link actions
        card_actions = [i for i in clues_menu if 'Link' not in i]
        link_actions = [i for i in clues_menu if 'Link' in i]
        clues_html = (
            "<p><b>Clues board:</b> Right-click a card for: "
            + ", ".join(card_actions) + ". Right-click a link for: "
            + ", ".join(link_actions) + ".</p>"
        )
    parts.append(section("Managing Entities",
        "<p>Each list supports filtering, sorting by column, and context actions:</p>"
        "<ul>"
        "<li><b>Add/Edit:</b> Double-click a row or use toolbar buttons to edit details.</li>"
        "<li><b>Duplicate/Delete:</b> Right-click a row to duplicate or delete.</li>"
        "<li><b>Import/Export:</b> Buttons allow saving to and loading from JSON.</li>"
        "<li><b>Columns & Fields:</b> Right-click to show/hide columns and pick which fields display.</li>"
        "<li><b>Colors & Portraits:</b> Assign row colors; show portrait if available.</li>"
        "</ul>"
        + ("<p><b>Right-click menu includes:</b></p><ul>" + ent_menu_html + "</ul>" if ent_menu_html else "")
        + img("entity_scenarios", "Scenarios List")
        + clues_html
    ))

    # Graph Editors with right-click and shortcuts
    ge_node_html = ''.join(f"<li>{i}</li>" for i in node_items) if node_items else ''
    ge_link_html = ''
    if arrow_items:
        ge_link_html = (
            "<li><b>Arrow Mode submenu:</b> " + ", ".join(arrow_items) + "</li>"
        )
    ge_shape_html = ''.join(f"<li>{i}</li>" for i in shape_items_graph) if shape_items_graph else ''
    parts.append(section("Graph Editors",
        "<p>Visual editors for NPCs, PCs, Factions, and Scenarios let you:</p>"
        "<ul>"
        "<li><b>Add nodes:</b> Use dedicated add actions or double-click (where available).</li>"
        "<li><b>Drag to move:</b> Left-click and drag nodes to arrange.</li>"
        "<li><b>Create links:</b> Select first node, then second; enter link text when prompted.</li>"
        "<li><b>Zoom/Pan:</b> Mouse wheel to zoom; Shift+wheel to pan horizontally.</li>"
        "</ul>"
        + ("<p><b>Right-click a node for:</b></p><ul>" + ge_node_html + "</ul>" if ge_node_html else "")
        + ("<p><b>Right-click a link for:</b></p><ul>" + ge_link_html + "</ul>" if ge_link_html else "")
        + ("<p><b>Right-click a shape for:</b></p><ul>" + ge_shape_html + "</ul>" if ge_shape_html else "")
        + img("npc_graph", "NPC Graph") + img("pc_graph", "PC Graph")
        + img("faction_graph", "Faction Graph") + img("scenario_graph", "Scenario Graph")
    ))

    parts.append(section("GM Screen",
        "<p>Browse and present a scenario with a condensed GM-focused layout:</p>"
        "<ul>"
        "<li>Pick a scenario from the list, then drill into details.</li>"
        "<li><b>Search:</b> Press <code>Ctrl+F</code> to open global search within GM Screen.</li>"
        "<li><b>Banner:</b> Show PCs at the top for quick reference.</li>"
        "</ul>"
        + img("gm_screen", "GM Screen")
    ))

    parts.append(section("Scenario Tools",
        "<p>Two helpers streamline content:</p>"
        "<ul>"
        "<li><b>Generator:</b> Creates scenario outlines; adjust options, then generate and refine.</li>"
        "<li><b>Importer:</b> Parse external scenario documents and map fields before saving.</li>"
        "</ul>"
        + img("scenario_generator", "Scenario Generator") + img("scenario_importer", "Scenario Importer")
    ))

    # Map Tool with right-click and shortcuts
    map_tok_html = ''.join(f"<li>{i}</li>" for i in map_token_items) if map_token_items else ''
    map_shape_html = ''.join(f"<li>{i}</li>" for i in map_shape_items) if map_shape_items else ''
    parts.append(section("Map Tool",
        "<p>Open a separate window to display and edit maps, tokens, auras, fog, and shapes.</p>"
        "<ul>"
        "<li><b>Select a Map:</b> Choose from your maps list.</li>"
        "<li><b>Fog of War:</b> Add/Remove/Clear/Reset fog; <code>[</code> and <code>]</code> adjust brush size; Rectangle/Circle shapes.</li>"
        "<li><b>Tokens:</b> Add NPC/Creature/PC tokens; adjust Token Size slider.</li>"
        "<li><b>Shapes:</b> Switch Active Tool to Rectangle or Oval; set Fill/Border colors and fill mode.</li>"
        "<li><b>Fullscreen/Web:</b> Mirror the map to a separate window or a web client.</li>"
        "<li><b>Context Menus:</b> Right-click tokens/shapes for actions like resize, color, z-order, copy, delete.</li>"
        "</ul>"
        + ("<p><b>Token right-click includes:</b></p><ul>" + map_tok_html + "</ul>" if map_tok_html else "")
        + ("<p><b>Shape right-click includes:</b></p><ul>" + map_shape_html + "</ul>" if map_shape_html else "")
        + (img("map_tool_selector", "Map Tool — Selector") if shots.get("map_tool_selector") else "")
        + (img("map_tool_editor", "Map Tool — Editor") if shots.get("map_tool_editor") else "")
        + (img("map_tool_rectangle", "Map Tool — Rectangle Tool") if shots.get("map_tool_rectangle") else "")
        + (img("map_tool_oval", "Map Tool — Oval Tool") if shots.get("map_tool_oval") else "")
    ))

    parts.append(section("Tips",
        "<div class='tip'><b>Screenshots:</b> This manual captures the full screen to avoid cut edges. To regenerate, run <code>python scripts/generate_docs.py</code>.</div>"
        "<div class='tip'><b>Exporting for Foundry:</b> Use <i>Export Scenarios for Foundry</i> from the sidebar to generate a Foundry-ready export.</div>"
        "<div class='tip'><b>Portraits:</b> Generate or associate portraits for NPCs and creatures from the sidebar tools.</div>"
    ))

    parts.append("</div></body></html>")
    return "".join(parts)


if __name__ == "__main__":
    main()
