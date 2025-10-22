import os
import sys
import ast
import re
import time
import copy
import shutil
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



def _safe_get_source(src: str, node):
    if node is None:
        return None
    try:
        segment = ast.get_source_segment(src, node)
        if segment is not None:
            return segment.strip()
    except Exception:
        pass
    try:
        return ast.unparse(node).strip()
    except Exception:
        return None


def _format_arg(arg, src: str):
    name = arg.arg
    annotation = _safe_get_source(src, getattr(arg, "annotation", None))
    if annotation:
        return f"{name}: {annotation}"
    return name


def _collect_param_info(node: ast.FunctionDef, src: str):
    params = []
    args = node.args
    positional = list(args.posonlyargs) + list(args.args)
    defaults = [None] * (len(positional) - len(args.defaults)) + list(args.defaults)
    posonly_count = len(args.posonlyargs)
    for idx, arg in enumerate(positional):
        params.append({
            "name": arg.arg,
            "base_name": arg.arg,
            "annotation": _safe_get_source(src, getattr(arg, "annotation", None)),
            "default": _safe_get_source(src, defaults[idx]) if defaults[idx] is not None else None,
            "kind": "positional-only" if idx < posonly_count else "positional-or-keyword",
        })
    if args.vararg:
        params.append({
            "name": f"*{args.vararg.arg}",
            "base_name": args.vararg.arg,
            "annotation": _safe_get_source(src, getattr(args.vararg, "annotation", None)),
            "default": None,
            "kind": "var-positional",
        })
    if args.kwonlyargs:
        for arg, default in zip(args.kwonlyargs, args.kw_defaults):
            params.append({
                "name": arg.arg,
                "base_name": arg.arg,
                "annotation": _safe_get_source(src, getattr(arg, "annotation", None)),
                "default": _safe_get_source(src, default) if default is not None else None,
                "kind": "keyword-only",
            })
    if args.kwarg:
        params.append({
            "name": f"**{args.kwarg.arg}",
            "base_name": args.kwarg.arg,
            "annotation": _safe_get_source(src, getattr(args.kwarg, "annotation", None)),
            "default": None,
            "kind": "var-keyword",
        })
    return params


def _summarize_params(params):
    parts = []
    for info in params:
        if info["base_name"] in {"self", "cls"}:
            continue
        traits = []
        kind = info["kind"]
        if kind == "positional-only":
            traits.append("positional-only")
        elif kind == "keyword-only":
            traits.append("keyword-only")
        elif kind == "var-positional":
            traits.append("variadic positional")
        elif kind == "var-keyword":
            traits.append("variadic keyword")
        annotation = info.get("annotation")
        if annotation:
            traits.append(f"type {annotation}")
        default = info.get("default")
        if default is not None:
            traits.append(f"default {default}")
        if traits:
            parts.append(f"{info['base_name']} ({', '.join(traits)})")
        else:
            parts.append(info["base_name"])
    if parts:
        return "Parameters: " + "; ".join(parts) + "."
    return ""


def _build_signature(node: ast.FunctionDef, src: str):
    args = node.args
    pieces = []
    positional = list(args.posonlyargs) + list(args.args)
    defaults = [None] * (len(positional) - len(args.defaults)) + list(args.defaults)
    posonly_count = len(args.posonlyargs)
    for idx, arg in enumerate(positional):
        text = _format_arg(arg, src)
        default_node = defaults[idx]
        if default_node is not None:
            default_text = _safe_get_source(src, default_node)
            if default_text is not None:
                text = f"{text}={default_text}"
        pieces.append(text)
        if posonly_count and idx == posonly_count - 1:
            pieces.append("/")
    if args.vararg:
        pieces.append(f"*{_format_arg(args.vararg, src)}")
    elif args.kwonlyargs:
        pieces.append("*")
    for arg, default in zip(args.kwonlyargs, args.kw_defaults):
        text = _format_arg(arg, src)
        if default is not None:
            default_text = _safe_get_source(src, default)
            if default_text is not None:
                text = f"{text}={default_text}"
        pieces.append(text)
    if args.kwarg:
        pieces.append(f"**{_format_arg(args.kwarg, src)}")
    params = ", ".join(filter(None, pieces))
    return f"{node.name}({params})"


def _describe_function(node: ast.FunctionDef, src: str):
    doc = (ast.get_docstring(node) or "").strip()
    params = _summarize_params(_collect_param_info(node, src))
    returns = _safe_get_source(src, node.returns)
    return_text = f"Returns: {returns}." if returns else ""
    chunks = [chunk for chunk in (doc, params, return_text) if chunk]
    if not chunks:
        chunks.append("No inline documentation available.")
    return " ".join(chunks)


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
    api["doc"] = (ast.get_docstring(tree) or "").strip()
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            api["functions"].append({
                "name": node.name,
                "lineno": node.lineno,
                "signature": _build_signature(node, src),
                "doc": _describe_function(node, src),
            })
        elif isinstance(node, ast.ClassDef):
            bases = []
            for base in node.bases:
                base_src = _safe_get_source(src, base)
                if base_src:
                    bases.append(base_src)
            klass = {
                "name": node.name,
                "lineno": node.lineno,
                "doc": (ast.get_docstring(node) or "").strip(),
                "bases": bases,
                "methods": [],
            }
            for sub in node.body:
                if isinstance(sub, ast.FunctionDef):
                    klass["methods"].append({
                        "name": sub.name,
                        "lineno": sub.lineno,
                        "signature": _build_signature(sub, src),
                        "doc": _describe_function(sub, src),
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
    os.environ["DOCS_MODE"] = "1"
    sys.path.insert(0, str(ROOT))
    try:
        import tkinter as tk  # noqa: F401 - imported to ensure Tk initialises
        import customtkinter as ctk
        from main_window import MainWindow
        from modules.generic.generic_model_wrapper import GenericModelWrapper
        from modules.helpers.template_loader import load_template
        from modules.generic.entity_detail_factory import create_scenario_detail_frame
        from modules.generic.custom_fields_editor import CustomFieldsEditor
        from modules.generic.generic_editor_window import GenericEditorWindow
    except Exception:
        return {}

    shots = {}

    app = MainWindow()
    app.update()
    shots["main_window"] = str(grab_widget_screenshot(app, "main_window") or "")

    def capture_sidebar_sections():
        try:
            children = list(app.sidebar_inner.winfo_children())
            if not children:
                return
            container = children[-1]
            sections = [child for child in container.winfo_children() if isinstance(child, ctk.CTkFrame)]
            keys = [
                ("accordion_data_system", "Data & System"),
                ("accordion_campaign_workshop", "Campaign Workshop"),
                ("accordion_relations_graphs", "Relations & Graphs"),
                ("accordion_utilities", "Utilities"),
            ]
            for idx, (shot_key, _title) in enumerate(keys):
                if idx >= len(sections):
                    break
                section_frame = sections[idx]
                header = None
                for child in section_frame.winfo_children():
                    if isinstance(child, ctk.CTkFrame):
                        header = child
                        break
                if header is None:
                    continue
                header.event_generate("<Enter>")
                app.update_idletasks()
                app.update()
                shots[shot_key] = str(grab_widget_screenshot(app, shot_key) or "")
            if len(sections) > 1:
                header = None
                for child in sections[1].winfo_children():
                    if isinstance(child, ctk.CTkFrame):
                        header = child
                        break
                if header:
                    header.event_generate("<Enter>")
                    app.update_idletasks()
                    app.update()
        except Exception:
            pass

    capture_sidebar_sections()

    for ent in ["scenarios", "pcs", "npcs", "creatures", "factions", "places", "objects", "informations", "clues", "books", "maps"]:
        try:
            app.open_entity(ent)
            app.update()
            shots[f"entity_{ent}"] = str(grab_widget_screenshot(app, f"entity_{ent}") or "")
        except Exception:
            pass

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
    try:
        app.open_scenario_builder()
        app.update()
        shots["scenario_builder"] = str(grab_widget_screenshot(app, "scenario_builder") or "")
    except Exception:
        pass
    try:
        app.open_scene_flow_viewer()
        app.update(); app.update_idletasks()
        import customtkinter as ctk
        tops = [w for w in app.winfo_children() if isinstance(w, ctk.CTkToplevel)]
        sf_top = tops[-1] if tops else None
        if sf_top:
            shots["scene_flow_viewer"] = str(grab_widget_screenshot(sf_top, "scene_flow_viewer") or "")
    except Exception:
        pass

    def build_sample_scenario(template):
        sample = {}
        for field in template.get("fields", []):
            name = field.get("name")
            ftype = field.get("type")
            if not name:
                continue
            if name == "Title":
                sample[name] = "Sample Scenario Overview"
                continue
            if name == "Summary":
                sample[name] = "A quick overview tying together stakes, goals, and hooks."
                continue
            if name == "Secrets":
                sample[name] = "Important twists and truths reserved for the GM."
                continue
            if ftype == "longtext":
                sample[name] = {"text": f"{name} details and notes."}
            elif ftype == "list_longtext":
                sample[name] = [
                    {"text": f"{name} entry 1"},
                    {"text": f"{name} entry 2"},
                ]
            elif ftype == "list":
                sample[name] = [f"{name} item 1", f"{name} item 2"]
            elif ftype == "boolean":
                sample[name] = False
            else:
                sample[name] = f"{name} details"
        sample.setdefault("Title", "Sample Scenario Overview")
        sample.setdefault("Summary", "A quick overview tying together stakes, goals, and hooks.")
        sample.setdefault("Secrets", "Important twists and truths reserved for the GM.")
        return sample

    scenario_wrapper = None
    scenario_template = None
    scenario_item = None
    try:
        scenario_template = load_template("scenarios")
    except Exception:
        scenario_template = None
    try:
        scenario_wrapper = GenericModelWrapper("scenarios")
        existing = scenario_wrapper.load_items()
        if existing:
            scenario_item = copy.deepcopy(existing[0])
    except Exception:
        scenario_wrapper = None
    if scenario_item is None and scenario_template:
        scenario_item = build_sample_scenario(scenario_template)
    if scenario_item and scenario_template is None:
        try:
            scenario_template = load_template("scenarios")
        except Exception:
            scenario_template = None

    if scenario_item:
        detail_top = None
        try:
            detail_top = ctk.CTkToplevel(app)
            detail_top.title("Scenario Detail Preview")
            detail_top.geometry("1400x900")
            detail_top.lift()
            detail_top.focus_force()
            create_scenario_detail_frame("Scenarios", scenario_item, detail_top, open_entity_callback=None)
            detail_top.update_idletasks()
            detail_top.update()
            shots["scenario_detail"] = str(grab_widget_screenshot(detail_top, "scenario_detail") or "")
        except Exception:
            pass
        finally:
            if detail_top is not None:
                try:
                    detail_top.destroy()
                except Exception:
                    pass
                app.update()

    if scenario_item and scenario_template:
        editor_window = None
        try:
            editor_window = GenericEditorWindow(
                app,
                copy.deepcopy(scenario_item),
                scenario_template,
                scenario_wrapper or GenericModelWrapper("scenarios"),
                creation_mode=False
            )
            editor_window.update_idletasks()
            editor_window.update()
            shots["scenario_editor"] = str(grab_widget_screenshot(editor_window, "scenario_editor") or "")
        except Exception:
            pass
        finally:
            if editor_window is not None:
                try:
                    editor_window.destroy()
                except Exception:
                    pass
                app.update()

    fields_editor = None
    try:
        fields_editor = CustomFieldsEditor(app)
        fields_editor.update_idletasks()
        fields_editor.update()
        shots["custom_fields_editor"] = str(grab_widget_screenshot(fields_editor, "custom_fields_editor") or "")
    except Exception:
        pass
    finally:
        if fields_editor is not None:
            try:
                fields_editor.destroy()
            except Exception:
                pass
            app.update()

    def ensure_map_samples(ctrl):
        if not ctrl:
            return []
        try:
            existing = ctrl._maps if getattr(ctrl, '_maps', None) else {}
        except Exception:
            existing = {}
        try:
            from modules.helpers.config_helper import ConfigHelper
            campaign_dir = Path(ConfigHelper.get_campaign_dir())
        except Exception:
            campaign_dir = None
        valid_names = []
        if campaign_dir is not None:
            for key, item in existing.items():
                if not isinstance(item, dict):
                    continue
                image_rel = item.get('Image')
                if not image_rel:
                    continue
                full_path = (campaign_dir / image_rel).resolve()
                if full_path.exists():
                    valid_names.append(key)
        else:
            valid_names = [key for key, item in existing.items() if isinstance(item, dict) and item.get('Image')]
        if valid_names:
            return valid_names
        if campaign_dir is None:
            return []
        map_dir = campaign_dir / 'assets' / 'images' / 'map_images'
        try:
            map_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            return []
        sample_sources = [
            ROOT / 'assets' / 'images' / 'Unnamed_1689623850560.png',
            ROOT / 'assets' / 'images' / 'Unnamed_1957333036608.png',
            ROOT / 'assets' / 'images' / 'Unnamed_2378696683072.png',
        ]
        generated = {}
        for idx, src in enumerate(sample_sources, 1):
            if not src.exists():
                continue
            dest = map_dir / f'docs_sample_map_{idx}.png'
            try:
                shutil.copyfile(src, dest)
            except Exception:
                continue
            rel = dest.relative_to(campaign_dir).as_posix()
            generated[f'Docs Sample Map {idx}'] = {
                'Name': f'Docs Sample Map {idx}',
                'Description': 'Auto-generated sample map for documentation screenshots.',
                'Image': rel,
                'FogMaskPath': '',
                'Tokens': '[]',
                'token_size': 64,
                'pan_x': 0,
                'pan_y': 0,
                'zoom': 1.0,
            }
        if generated:
            ctrl._maps = generated
            return list(generated.keys())
        return []



    try:
        app.map_tool()
        app.update(); app.update_idletasks()
        tops = [w for w in app.winfo_children() if isinstance(w, ctk.CTkToplevel)]
        map_top = tops[-1] if tops else None
        if map_top:
            shots["map_tool_selector"] = str(grab_widget_screenshot(map_top, "map_tool_selector") or "")
            ctrl = getattr(app, 'map_controller', None)
            map_names = ensure_map_samples(ctrl)
            if ctrl and map_names:
                for idx, name in enumerate(map_names[:2], 1):
                    try:
                        ctrl._on_display_map("maps", name)
                        app.update(); app.update_idletasks()
                        key = f"map_tool_map{idx}"
                        shots[key] = str(grab_widget_screenshot(map_top, key) or "")
                    except Exception:
                        continue
                try:
                    ctrl._on_drawing_tool_change("Rectangle"); app.update()
                    shots["map_tool_rectangle"] = str(grab_widget_screenshot(map_top, "map_tool_rectangle") or "")
                    ctrl._on_drawing_tool_change("Oval"); app.update()
                    shots["map_tool_oval"] = str(grab_widget_screenshot(map_top, "map_tool_oval") or "")
                    ctrl._on_drawing_tool_change("Token"); app.update()
                except Exception:
                    pass
    except Exception:
        pass



    # World Map (nested navigation)
    try:
        app.open_world_map()
        app.update(); app.update_idletasks()
        tops = [w for w in app.winfo_children() if isinstance(w, ctk.CTkToplevel)]
        wm_top = tops[-1] if tops else None
        if wm_top:
            shots["world_map"] = str(grab_widget_screenshot(wm_top, "world_map") or "")
    except Exception:
        pass

    # Dice Roller and Dice Bar
    try:
        app.open_dice_roller()
        app.update(); app.update_idletasks()
        tops = [w for w in app.winfo_children() if isinstance(w, ctk.CTkToplevel)]
        dr_top = tops[-1] if tops else None
        if dr_top:
            shots["dice_roller"] = str(grab_widget_screenshot(dr_top, "dice_roller") or "")
    except Exception:
        pass
    try:
        app.open_dice_bar()
        app.update(); app.update_idletasks()
        tops = [w for w in app.winfo_children() if isinstance(w, ctk.CTkToplevel)]
        db_top = tops[-1] if tops else None
        if db_top:
            shots["dice_bar"] = str(grab_widget_screenshot(db_top, "dice_bar") or "")
    except Exception:
        pass

    # Sound & Music Manager + Audio Controls Bar
    try:
        app.open_sound_manager()
        app.update(); app.update_idletasks()
        tops = [w for w in app.winfo_children() if isinstance(w, ctk.CTkToplevel)]
        sm_top = tops[-1] if tops else None
        if sm_top:
            shots["sound_manager"] = str(grab_widget_screenshot(sm_top, "sound_manager") or "")
    except Exception:
        pass
    try:
        app.open_audio_bar()
        app.update(); app.update_idletasks()
        tops = [w for w in app.winfo_children() if isinstance(w, ctk.CTkToplevel)]
        ab_top = tops[-1] if tops else None
        if ab_top:
            shots["audio_bar"] = str(grab_widget_screenshot(ab_top, "audio_bar") or "")
    except Exception:
        pass

    # Book Viewer (generate a sample PDF if needed)
    try:
        from modules.helpers.config_helper import ConfigHelper
        from modules.books.book_viewer import open_book_viewer
        try:
            from pypdf import PdfWriter
        except Exception:
            PdfWriter = None  # pragma: no cover - fallback if pypdf unavailable

        campaign_dir = Path(ConfigHelper.get_campaign_dir())
        books_dir = campaign_dir / "assets" / "books"
        books_dir.mkdir(parents=True, exist_ok=True)
        sample_pdf = books_dir / "docs_sample.pdf"
        if not sample_pdf.exists() and PdfWriter is not None:
            try:
                writer = PdfWriter()
                # A4 portrait in points
                writer.add_blank_page(width=595, height=842)
                with sample_pdf.open("wb") as fh:
                    writer.write(fh)
            except Exception:
                pass
        if sample_pdf.exists():
            rel = sample_pdf.relative_to(campaign_dir).as_posix()
            book_record = {"Title": "Docs Sample Book", "Attachment": rel, "PageCount": 1}
            open_book_viewer(app, book_record)
            app.update(); app.update_idletasks()
            tops = [w for w in app.winfo_children() if isinstance(w, ctk.CTkToplevel)]
            bv_top = tops[-1] if tops else None
            if bv_top:
                shots["book_viewer"] = str(grab_widget_screenshot(bv_top, "book_viewer") or "")
    except Exception:
        pass

    try:
        app.open_gm_screen()
        app.update()
        shots["gm_screen"] = str(grab_widget_screenshot(app, "gm_screen") or "")
    except Exception:
        pass

    try:
        app.destroy()
    except Exception:
        pass

    return {k: v for k, v in shots.items() if v}



def build_html(api_data, menu_data, shots):
    def esc(s):
        return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def render_image(key):
        path = shots.get(key)
        if not path:
            return ""
        try:
            rel = Path(path).relative_to(DOCS_DIR).as_posix()
        except Exception:
            rel = Path(path).as_posix()
        title = key.replace("_", " " ).title()
        return f"<figure class='shot'><img src='{rel}' alt='{esc(title)}' /><figcaption>{esc(title)}</figcaption></figure>"

    sections = []

    sections.append(
        """
        <section id=\"overview\">
          <h1>GMCampaignDesigner Documentation</h1>
          <p>This document provides an overview of the application's features, UI, right-click context menus, and a module API reference generated from the source code.</p>
          <p>Version generated on: {ts}</p>
        </section>
        """.format(ts=time.strftime("%Y-%m-%d %H:%M:%S"))
    )

    if shots:
        used = set()
        group_chunks = []

        def add_group(title, keys):
            items = []
            for key in keys:
                if key in shots and key not in used:
                    rendered = render_image(key)
                    if rendered:
                        items.append(rendered)
                        used.add(key)
            if items:
                group_chunks.append(f"<h3>{esc(title)}</h3>" + "".join(items))

        add_group("Main Window & Sidebar", [
            "main_window",
            "accordion_data_system",
            "accordion_campaign_workshop",
            "accordion_relations_graphs",
            "accordion_utilities",
        ])

        entity_keys = [k for k in sorted(shots) if k.startswith("entity_") and k not in used]
        if entity_keys:
            group_chunks.append("<h3>Entity Managers</h3>" + "".join(render_image(k) for k in entity_keys))
            used.update(entity_keys)

        add_group("Detail & Editor Windows", ["scenario_detail", "scenario_editor", "custom_fields_editor"])
        add_group("Graph Editors", ["npc_graph", "pc_graph", "faction_graph", "scenario_graph"])
        add_group("GM & Scenario Tools", ["gm_screen", "scenario_generator", "scenario_importer"])
        add_group("Map Tools", ["map_tool_selector", "map_tool_map1", "map_tool_map2", "map_tool_rectangle", "map_tool_oval"])

        remaining = [k for k in sorted(shots) if k not in used]
        if remaining:
            group_chunks.append("<h3>Additional Views</h3>" + "".join(render_image(k) for k in remaining))

        sections.append("<section id='screenshots'><h2>UI Screenshots</h2>" + "".join(group_chunks) + "</section>")

    if menu_data:
        blocks = []
        for m in menu_data:
            items = ''.join(f"<li>{esc(lbl)}</li>" for lbl in m["items"])
            blocks.append(f"<div class='menu-block'><h3>{esc(m['module'])}</h3><ul>{items}</ul></div>")
        sections.append("<section id='context-menus'><h2>Right-Click Menus</h2>" + "\n".join(blocks) + "</section>")

    api_blocks = []
    for mod in api_data:
        fn_list = ''.join(
            f"<li><code>{esc(f['signature'])}</code> &ndash; {esc(f['doc'])}</li>" for f in mod["functions"]
        )
        class_blocks = []
        for c in mod["classes"]:
            bases = f" ({', '.join(esc(b) for b in c.get('bases', []) if b)})" if c.get("bases") else ""
            methods = ''.join(
                f"<li><code>{esc(m['signature'])}</code> &ndash; {esc(m['doc'])}</li>" for m in c["methods"]
            )
            class_blocks.append(
                f"<div class='class'><h4>class {esc(c['name'])}{bases}</h4><p>{esc(c['doc'])}</p><ul>{methods}</ul></div>"
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
        try:
            rel = Path(p).relative_to(DOCS_DIR).as_posix()
        except Exception:
            rel = Path(p).as_posix()
        caption = alt or key.replace('_', ' ').title()
        return f"<figure class='shot'><img class='manual-shot' src='{rel}' alt='{caption}' /><figcaption>{caption}</figcaption></figure>"

    def section(title, body):
        return f"<section><h2 id='{title.lower().replace(' ', '-')}'>{title}</h2>{body}</section>"

    def collect_items(filter_fn):
        items = []
        for m in menu_data:
            if filter_fn(m.get('module', '')):
                items.extend(m.get('items') or [])
        seen = set()
        ordered = []
        for item in items:
            if item not in seen:
                seen.add(item)
                ordered.append(item)
        return ordered

    entity_menu = collect_items(lambda mod: 'generic/generic_list_view.py' in mod.replace('\\', '/'))
    graph_menu_all = collect_items(lambda mod: any(s in mod.replace('\\', '/') for s in [
        'npcs/npc_graph_editor.py', 'pcs/pc_graph_editor.py', 'factions/faction_graph_editor.py', 'scenarios/scenario_graph_editor.py'
    ]))
    map_menu_all = collect_items(lambda mod: 'maps/controllers/display_map_controller.py' in mod.replace('\\', '/'))
    clues_menu = collect_items(lambda mod: 'web/templates/clues.html' in mod.replace('\\', '/'))

    arrow_items = [i for i in graph_menu_all if 'Arrow' in i]
    node_items = [i for i in graph_menu_all if 'Node' in i or i in ('Change Color', 'Display Portrait', 'Display Portrait Window')]
    shape_items_graph = [i for i in graph_menu_all if 'Shape' in i and i not in arrow_items]

    map_token_items = [i for i in map_menu_all if 'Token' in i or i in ('Show Portrait', 'Change Border Color', 'Resize Token')]
    map_shape_items = [i for i in map_menu_all if 'Shape' in i and i not in map_token_items]

    accordion_sections = [
        (
            'Data & System',
            'Switch between campaign databases and configure global integrations.',
            [
                '<b>Change Data Storage</b>: Choose which SQLite campaign file to work with.',
                '<b>Set SwarmUI Path</b>: Point the portrait generator at your SwarmUI installation.',
                '<b>Customize Fields</b>: Open the custom field editor (see Editor Tools).',
            ],
            'accordion_data_system',
        ),
        (
            'Campaign Workshop',
            'Access every entity manager from a single place.',
            [
                '<b>Manage Scenarios</b>: Maintain adventure outlines and summaries.',
                '<b>Manage NPCs / PCs / Creatures</b>: Track cast members, their traits, and portraits.',
                '<b>Manage Places, Factions, Objects, Informations, Clues, Books, Maps</b>: Open the corresponding list view.',
            ],
            'accordion_campaign_workshop',
        ),
        (
            'Relations & Graphs',
            'Open visual editors to map relationships between entities.',
            [
                '<b>NPC / PC / Faction / Scenario Graph Editor</b>: Launch the graph workspace focused on that entity type.',
            ],
            'accordion_relations_graphs',
        ),
        (
            'Utilities',
            'Launch helper tools for session prep and presentation.',
            [
                '<b>Generate Scenario</b>, <b>Scenario Builder Wizard</b>, and <b>AI Wizard</b>: Automate outline or content generation.',
                '<b>Import Scenario</b>: Map external documents into campaign data.',
                '<b>GM Screen</b>, <b>Scene Flow Viewer</b>, <b>World Map</b>, and <b>Map Tool</b>: Present scenario details or share battle/world maps.',
                '<b>Dice Bar</b> and <b>Open Dice Roller</b>: Quick always-on-top roller and full formula roller.',
                '<b>Sound &amp; Music Manager</b> and <b>Audio Controls Bar</b>: Organize playlists and control playback.',
                '<b>Export Scenarios</b> / <b>Export for Foundry</b>: Produce shareable outputs.',
            ],
            'accordion_utilities',
        ),
    ]

    parts = [
        "<html><head><meta charset='utf-8'><title>GMCampaignDesigner User Manual</title>",
        "<link rel='stylesheet' href='user-manual.css'></head><body>",
        "<header><h1>GMCampaignDesigner User Manual</h1></header>",
        "<nav><a href='#getting-started'>Getting Started</a><a href='#sidebar-accordion'>Sidebar Accordion</a><a href='#entity-managers'>Entity Managers</a><a href='#detail-windows'>Detail Windows</a><a href='#editor-tools'>Editor Tools</a><a href='#graph-editors'>Graph Editors</a><a href='#gm-screen'>GM Screen</a><a href='#scenario-tools'>Scenario Tools</a><a href='#scene-flow'>Scene Flow</a><a href='#map-tool'>Map Tool</a><a href='#world-map'>World Map</a><a href='#dice-roller'>Dice Roller</a><a href='#audio-&-music'>Audio &amp; Music</a><a href='#books'>Books</a><a href='#tips'>Tips</a></nav><div class='container'>"
    ]

    parts.append(section('Getting Started',
        "<ul>"
        "<li>Launch the app: <code>python main_window.py</code>.</li>"
        "<li>Select or create a campaign database from <b>Data & System &rarr; Change Data Storage</b>.</li>"
        "<li>Populate PCs, NPCs, Creatures, Places, Objects, Informations, Clues, and Maps.</li>"
        "</ul>" + img('main_window', 'Main window overview')
    ))

    accordion_html = [
        "<p>The sidebar groups every command inside collapsible sections. Hover a blue header to expand its button grid; moving the pointer away collapses it after a short delay. The Campaign Workshop section reopens automatically when idle.</p>"
    ]
    for title, description, bullet_points, shot_key in accordion_sections:
        accordion_html.append(f"<h3>{title}</h3>")
        accordion_html.append(f"<p>{description}</p>")
        accordion_html.append("<ul>" + ''.join(f"<li>{item}</li>" for item in bullet_points) + "</ul>")
        accordion_html.append(img(shot_key, f"{title} section"))
    parts.append(section('Sidebar Accordion', ''.join(accordion_html)))

    ent_menu_html = ''.join(f"<li>{item}</li>" for item in entity_menu) if entity_menu else ''
    clues_html = ''
    if clues_menu:
        card_actions = [i for i in clues_menu if 'Link' not in i]
        link_actions = [i for i in clues_menu if 'Link' in i]
        clues_html = (
            "<p><b>Clues board:</b> Right-click a clue card for: "
            + ', '.join(card_actions)
            + ". Right-click a link for: "
            + ', '.join(link_actions)
            + ".</p>"
        )

    entity_parts = [
        "<p>Expand <b>Campaign Workshop</b> and click a manager button to open the list view. Each view supports column sorting, instant filtering, grouping, and rich editing:</p>",
        "<ul>",
        "<li><b>Quick edit:</b> Double-click a row to launch the Generic Editor window. Use the toolbar buttons to add new entries.</li>",
        "<li><b>Right-click options:</b> Duplicate, delete, recolor rows, show portraits, export data, or send a card to the second screen." + ("<ul>" + ent_menu_html + "</ul>" if ent_menu_html else "") + "</li>",
        "<li><b>Import/Export:</b> Use the dedicated buttons to load or save JSON, or open the AI Wizard for assisted authoring.</li>",
        "<li><b>Second screen:</b> Display selected fields on a player-facing monitor from the context menu.</li>",
        "</ul>",
        clues_html,
        ''.join(img(f"entity_{k}", f"{k.title()} manager") for k in [
            'scenarios', 'pcs', 'npcs', 'creatures', 'factions', 'places', 'objects', 'informations', 'clues', 'maps'
        ])
    ]
    entity_body = ''.join(part for part in entity_parts if part)
    parts.append(section('Entity Managers', entity_body))

    detail_body = ''.join([
        "<p><b>EntityDetailFactory</b> renders rich detail viewsâ€”used inside the GM Screen and any pop-out detail window. Select a scenario and choose <i>Open in GM Screen</i> (from the scenario list) or open the GM Screen from Utilities, then pick a tab to see the structured layout with collapsible scenes, linked NPC tables, and quick navigation.</p>",
        "<p>The preview below shows the standalone layout with an <b>Edit</b> button that reopens the Generic Editor for the same record.</p>",
        img('scenario_detail', 'Scenario detail view')
    ])
    parts.append(section('Detail Windows', detail_body))

    editor_body = ''.join([
        "<p>The <b>Generic Editor</b> window opens when you add or double-click an item. Fields are generated from the active template and include quick actions:</p>",
        "<ul>",
        "<li><b>Action bar:</b> Save, cancel, and scenario-aware AI buttons appear based on the entity type.</li>",
        "<li><b>Rich text:</b> Long-form fields use the RichTextEditor with inline toolbars and AI helpers.</li>",
        "<li><b>Linked lists:</b> Multiselect comboboxes let you associate NPCs, Places, Factions, and more.</li>",
        "<li><b>Portraits & files:</b> Manage artwork attachments directly from the editor.</li>",
        "</ul>",
        img('scenario_editor', 'Generic Editor window'),
        "<p>Use <b>Data & System &rarr; Customize Fields</b> to tailor the schema per entity. The editor below lets you add new fields, set types, and choose linked entities.</p>",
        img('custom_fields_editor', 'Custom Fields Editor')
    ])
    parts.append(section('Editor Tools', editor_body))

    ge_node_html = ''.join(f"<li>{i}</li>" for i in node_items) if node_items else ''
    ge_link_html = ''
    if arrow_items:
        ge_link_html = "<li><b>Arrow Mode submenu:</b> " + ', '.join(arrow_items) + "</li>"
    ge_shape_html = ''.join(f"<li>{i}</li>" for i in shape_items_graph) if shape_items_graph else ''
    parts.append(section('Graph Editors',
        "<p>Visual editors for NPCs, PCs, Factions, and Scenarios let you map relationships and story beats.</p>"
        "<ul>"
        "<li><b>Add nodes:</b> Use the toolbar actions or double-click (where available) to create a node.</li>"
        "<li><b>Drag to arrange:</b> Left-click and drag nodes to reposition; mouse wheel zooms the canvas.</li>"
        "<li><b>Create links:</b> Select a source node, then a target node, and enter link text when prompted.</li>"
        "</ul>"
        + ("<p><b>Right-click a node for:</b></p><ul>" + ge_node_html + "</ul>" if ge_node_html else "")
        + ("<p><b>Right-click a link for:</b></p><ul>" + ge_link_html + "</ul>" if ge_link_html else "")
        + ("<p><b>Right-click a shape for:</b></p><ul>" + ge_shape_html + "</ul>" if ge_shape_html else "")
        + img('npc_graph', 'NPC Graph') + img('pc_graph', 'PC Graph')
        + img('faction_graph', 'Faction Graph') + img('scenario_graph', 'Scenario Graph')
    ))

    parts.append(section('GM Screen',
        "<p>The GM Screen consolidates scenario prep: select a scenario to open tabs for NPCs, Places, scenes, and notes. Use <code>Ctrl+F</code> for instant search, toggle the PC banner for quick reference, and click any linked entity to open its detail frame.</p>"
        + img('gm_screen', 'GM Screen overview')
    ))

    parts.append(section('Scenario Tools',
        "<p>Scenario toolkit for rapid authoring:</p>"
        "<ul>"
        "<li><b>Scenario Builder Wizard:</b> Plan scenes step-by-step, link NPCs/Places/Maps, and preview a scene flow before saving.</li>"
        "<li><b>Scenario Generator:</b> Configure prompts and let the AI draft outline sections you can review and tweak.</li>"
        "<li><b>Scenario Importer:</b> Map headings from external documents into template fields before saving.</li>"
        "</ul>"
        + img('scenario_builder', 'Scenario Builder Wizard') + img('scenario_generator', 'Scenario Generator') + img('scenario_importer', 'Scenario Importer')
    ))

    map_tok_html = ''.join(f"<li>{i}</li>" for i in map_token_items) if map_token_items else ''
    map_shape_html = ''.join(f"<li>{i}</li>" for i in map_shape_items) if map_shape_items else ''
    

    parts.append(section('Scene Flow',
        "<p>Visualize your scenario as a flow of scenes and links. Drag nodes to rearrange, connect scenes with labeled links, and preview the structure before a session.</p>"
        "<ul>"
        "<li><b>Open:</b> Utilities &rarr; Open Scene Flow Viewer (or add a tab inside the GM Screen).</li>"
        "<li><b>Nodes & links:</b> Create, rename, colorize scenes; add directional links with labels.</li>"
        "<li><b>Layout:</b> Pan and zoom the canvas; arrange scenes for readability.</li>"
        "</ul>"
        + (img('scene_flow_viewer', 'Scene Flow Viewer') if shots.get('scene_flow_viewer') else '')
    ))
    parts.append(section('Map Tool',

        "<p>The Map Tool opens in its own window so you can prep encounters while the campaign lists stay visible. Use the selector view to choose or import a battle map, then switch to the editor to reveal fog, drop tokens, and broadcast to players.</p>"

        "<ul>"

        "<li><b>Map selector:</b> Browse the maps table, double-click to load, or right-click to import directories of images.</li>"

        "<li><b>Fog of war:</b> Paint additive or subtractive fog with brush shortcuts (<code>[</code>/<code>]</code>) and reset the mask with a single click.</li>"

        "<li><b>Tokens & auras:</b> Add NPC, PC, or creature tokens, colour their borders, track HP overlays, and duplicate or delete entries through the context menu.</li>"

        "<li><b>Drawing tools:</b> Switch between Token, Rectangle, and Oval modes to sketch zones, spell areas, or light auras with filled/outline styles.</li>"

        "<li><b>Broadcast & sync:</b> Mirror the current map to fullscreen or the web client; pan and zoom updates are pushed live.</li>"

        "</ul>"

        + ("<p><b>Token right-click includes:</b></p><ul>" + map_tok_html + "</ul>" if map_tok_html else "")

        + ("<p><b>Shape right-click includes:</b></p><ul>" + map_shape_html + "</ul>" if map_shape_html else "")

        + (img('map_tool_selector', 'Map Tool selector') if shots.get('map_tool_selector') else '')

        + (img('map_tool_map1', 'Map Tool - urban encounter') if shots.get('map_tool_map1') else '')

        + (img('map_tool_map2', 'Map Tool - mystical ruins') if shots.get('map_tool_map2') else '')

        + (img('map_tool_rectangle', 'Rectangle tool options') if shots.get('map_tool_rectangle') else '')

        + (img('map_tool_oval', 'Oval tool options') if shots.get('map_tool_oval') else '')

    ))





    

    parts.append(section('World Map',
        "<p>The World Map window lets you navigate nested maps, place NPC/PC/Creature/Place tokens, and drill down to regional maps while reviewing a compact inspector for the selected entity.</p>"
        "<ul>"
        "<li><b>Open:</b> Utilities &rarr; Open World Map (or from the GM Screen via <i>Add Panel &rarr; World Map</i>).</li>"
        "<li><b>Select map:</b> Load an existing entry or create a new one and assign a background image.</li>"
        "<li><b>Tokens:</b> Add NPCs, PCs, Creatures, Places, and Maps as pins. Selecting a Map token opens its child map.</li>"
        "<li><b>Pan &amp; zoom:</b> Middle-drag to pan; mouse wheel to zoom. View state persists per map.</li>"
        "<li><b>Inspector:</b> Click a token to view summary, notes, and quick stats; switch tabs to review more context.</li>"
        "</ul>"
        + img('world_map', 'World Map')
    ))

    parts.append(section('Dice Roller',
        "<p>Use the full Dice Roller for formula-based rolls with polyhedral previews, or the compact Dice Bar for always-on-top quick rolls.</p>"
        "<ul>"
        "<li><b>Open:</b> Utilities &rarr; Dice Bar and Utilities &rarr; Open Dice Roller.</li>"
        "<li><b>System presets:</b> Supported dice and default formulas adapt to the selected campaign system.</li>"
        "<li><b>Formula entry:</b> Build expressions (e.g., <code>2d20+5</code>), double-click presets to add dice, press Enter or click Roll.</li>"
        "<li><b>Exploding:</b> Toggle exploding dice to reroll max results.</li>"
        "<li><b>Results &amp; history:</b> See grouped breakdowns and totals; recent rolls are logged for reuse.</li>"
        "</ul>"
        + img('dice_roller', 'Dice Roller') + img('dice_bar', 'Dice Bar')
    ))

    parts.append(section('Audio & Music',
        "<p>Organize and play background music and sound effects, with persistent playlists per section.</p>"
        "<ul>"
        "<li><b>Open:</b> Utilities &rarr; Sound &amp; Music Manager. Use tabs for Music, Ambience, and SFX.</li>"
        "<li><b>Library:</b> Create types, add files or entire folders, rescan, and remove tracks.</li>"
        "<li><b>Playback:</b> Play/Pause, Next/Prev, volume, and per-section loop. Last playlist and loop settings are restored.</li>"
        "<li><b>AI Sorting:</b> Optionally categorize folders with local AI (if configured).</li>"
        "<li><b>Audio Controls Bar:</b> Utilities &rarr; Audio Controls Bar opens a compact always-on-top controller.</li>"
        "</ul>"
        + img('sound_manager', 'Sound & Music Manager') + img('audio_bar', 'Audio Controls Bar')
    ))

    parts.append(section('Books',
        "<p>Store and browse PDFs tied to your campaign. Imported books are indexed so you can search and reference excerpts.</p>"
        "<ul>"
        "<li><b>Open:</b> Campaign Workshop &rarr; Manage Books.</li>"
        "<li><b>Import:</b> Add individual PDFs or a whole folder. Indexing runs in the background.</li>"
        "<li><b>View:</b> Double-click a row or choose <i>Open Book</i> to launch the viewer. Use page navigation, zoom, and find (Prev/Next).</li>"
        "<li><b>Excerpts:</b> Export page ranges to <code>assets/books/excerpts</code>; excerpts appear in the <b>Excerpts</b> column for quick access.</li>"
        "</ul>"
        + img('entity_books', 'Books Manager') + img('book_viewer', 'Book Viewer')
    ))
    parts.append(section('Tips',
        "<div class='tip'><b>Screenshots:</b> Run <code>python scripts/generate_docs.py</code> to refresh this manual after UI changes.</div>"
        "<div class='tip'><b>Exports:</b> Use <i>Export Scenarios</i> or <i>Export for Foundry</i> (Utilities section) to share content.</div>"
        "<div class='tip'><b>Portrait workflow:</b> Generate or link portraits from the Utilities section; double-click a portrait in any list to pop it out.</div>"
    ))

    parts.append("</div></body></html>")
    return ''.join(parts)



if __name__ == "__main__":
    main()



