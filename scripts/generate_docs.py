"""Script entry point for generating project documentation snapshots."""

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
    """Handle discover python files."""
    files = []
    # Include top-level key files
    for name in ["main_window.py", "campaign_generator.py"]:
        # Process each name from ['main_window.py', 'campaign_generator.py'].
        p = ROOT / name
        if p.exists():
            files.append(p)
    # Include all module files (skip venv, dist, etc.)
    for p in MODULES_DIR.rglob("*.py"):
        files.append(p)
    return sorted(set(files))


def discover_html_files():
    """Handle discover HTML files."""
    files = []
    for p in (MODULES_DIR / "web" / "templates").rglob("*.html"):
        files.append(p)
    return sorted(set(files))



def _safe_get_source(src: str, node):
    """Internal helper for safe get source."""
    if node is None:
        return None
    try:
        # Keep safe get source resilient if this step fails.
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
    """Format arg."""
    name = arg.arg
    annotation = _safe_get_source(src, getattr(arg, "annotation", None))
    if annotation:
        return f"{name}: {annotation}"
    return name


def _collect_param_info(node: ast.FunctionDef, src: str):
    """Collect param info."""
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
    """Internal helper for summarize params."""
    parts = []
    for info in params:
        # Process each info from params.
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
    """Build signature."""
    args = node.args
    pieces = []
    positional = list(args.posonlyargs) + list(args.args)
    defaults = [None] * (len(positional) - len(args.defaults)) + list(args.defaults)
    posonly_count = len(args.posonlyargs)
    for idx, arg in enumerate(positional):
        # Process each (idx, arg) from enumerate(positional).
        text = _format_arg(arg, src)
        default_node = defaults[idx]
        if default_node is not None:
            # Handle the branch where default node is available.
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
        # Process each (arg, default) from zip(args.kwonlyargs, args.kw_defaults).
        text = _format_arg(arg, src)
        if default is not None:
            # Handle the branch where default is available.
            default_text = _safe_get_source(src, default)
            if default_text is not None:
                text = f"{text}={default_text}"
        pieces.append(text)
    if args.kwarg:
        pieces.append(f"**{_format_arg(args.kwarg, src)}")
    params = ", ".join(filter(None, pieces))
    return f"{node.name}({params})"


def _describe_function(node: ast.FunctionDef, src: str):
    """Internal helper for describe function."""
    doc = (ast.get_docstring(node) or "").strip()
    params = _summarize_params(_collect_param_info(node, src))
    returns = _safe_get_source(src, node.returns)
    return_text = f"Returns: {returns}." if returns else ""
    chunks = [chunk for chunk in (doc, params, return_text) if chunk]
    if not chunks:
        chunks.append("No inline documentation available.")
    return " ".join(chunks)


def parse_module_api(py_path: Path):
    """Parse module API."""
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
            # Handle the branch where isinstance(node, ast.ClassDef).
            bases = []
            for base in node.bases:
                # Process each base from node.bases.
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
    """Parse context menus."""
    try:
        src = py_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return []
    menus = []
    # Heuristic: find right-click handlers and nearby menu definitions
    if "<Button-3>" in src or "Menu(" in src:
        # Handle the branch where '<Button-3>' is in src or 'Menu(' is in src.
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
    """Parse HTML context menus."""
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
    """Ensure dirs."""
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)


def grab_widget_screenshot(widget, name: str):
    """Handle grab widget screenshot."""
    def settle_widget(target, cycles=6, delay=0.05):
        """Allow Tk geometry and deferred drawing callbacks to settle."""
        for _ in range(cycles):
            try:
                target.update_idletasks()
                target.update()
            except Exception:
                break
            time.sleep(delay)

    def raise_window_for_capture(target):
        """Bring a Tk toplevel to the foreground so ImageGrab sees the real pixels."""
        if os.name != "nt":
            return
        try:
            import ctypes
        except Exception:
            return

        try:
            hwnd = int(target.winfo_id())
        except Exception:
            return

        SW_RESTORE = 9
        user32 = ctypes.windll.user32
        try:
            user32.ShowWindow(hwnd, SW_RESTORE)
            user32.BringWindowToTop(hwnd)
            user32.SetForegroundWindow(hwnd)
        except Exception:
            return

    # Update geometry and bring to front
    top = None
    try:
        # Keep grab widget screenshot resilient if this step fails.
        top = widget.winfo_toplevel()
        if top is not None:
            # Handle the branch where top is available.
            top.lift()
            top.focus_force()
            try:
                top.attributes("-topmost", True)
            except Exception:
                pass
            raise_window_for_capture(top)
    except Exception:
        top = None
    settle_widget(top or widget, cycles=8, delay=0.06)
    # Compute absolute screen bbox
    try:
        # Keep grab widget screenshot resilient if this step fails.
        x = widget.winfo_rootx()
        y = widget.winfo_rooty()
        w = widget.winfo_width()
        h = widget.winfo_height()
        screen_w = widget.winfo_screenwidth()
        screen_h = widget.winfo_screenheight()
    except Exception:
        return None
    if w <= 1 or h <= 1:
        return None

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
        # Keep grab widget screenshot resilient if this step fails.
        # Tk/CustomTkinter windows need screen capture here; PrintWindow drops
        # custom-drawn surfaces and returns mostly black images on Windows.
        img = ImageGrab.grab(bbox=bbox)
        img.save(img_path)
        return img_path
    except Exception:
        return None
    finally:
        if top is not None:
            try:
                top.attributes("-topmost", False)
            except Exception:
                pass



def screenshot_app_views():
    """Handle screenshot app views."""
    os.environ["DOCS_MODE"] = "1"
    sys.path.insert(0, str(ROOT))
    python_root = Path(sys.base_prefix)
    tcl_root = python_root / "tcl"
    tcl_library = tcl_root / "tcl8.6"
    tk_library = tcl_root / "tk8.6"
    original_cwd = Path.cwd()
    original_tcl_library = os.environ.get("TCL_LIBRARY")
    original_tk_library = os.environ.get("TK_LIBRARY")
    app = None
    def restore_tk_runtime():
        """Restore process state after docs screenshot bootstrap."""
        try:
            os.chdir(original_cwd)
        except Exception:
            pass
        if original_tcl_library is None:
            os.environ.pop("TCL_LIBRARY", None)
        else:
            os.environ["TCL_LIBRARY"] = original_tcl_library
        if original_tk_library is None:
            os.environ.pop("TK_LIBRARY", None)
        else:
            os.environ["TK_LIBRARY"] = original_tk_library

    if tcl_library.exists() and tk_library.exists():
        # Tk can fail on Windows when the process starts on a different drive than
        # the Python installation; switching to the Python root and using relative
        # library paths makes Tcl resolve init.tcl reliably for doc generation.
        os.chdir(python_root)
        os.environ["TCL_LIBRARY"] = "tcl/tcl8.6"
        os.environ["TK_LIBRARY"] = "tcl/tk8.6"
    try:
        # Keep screenshot app views resilient if this step fails.
        import tkinter as tk  # noqa: F401 - imported to ensure Tk initialises
        import customtkinter as ctk
    except Exception:
        restore_tk_runtime()
        return {}

    shots = {}

    def settle_widget(target, cycles=8, delay=0.05):
        """Wait for Tk geometry, fonts, and deferred callbacks to finish."""
        for _ in range(cycles):
            try:
                target.update_idletasks()
                target.update()
            except Exception:
                break
            time.sleep(delay)

    def iter_widgets(root):
        """Yield a widget tree without failing on transient lookup errors."""
        try:
            yield root
            for child in root.winfo_children():
                yield from iter_widgets(child)
        except Exception:
            return

    def find_toplevel(root, *, title_contains=None):
        """Locate a live top-level window by title fragment."""
        matches = []
        for widget in iter_widgets(root):
            try:
                is_top = isinstance(widget, ctk.CTkToplevel)
                exists = widget.winfo_exists()
            except Exception:
                continue
            if not is_top or not exists:
                continue
            if title_contains:
                try:
                    title_value = widget.title() or ""
                except Exception:
                    title_value = ""
                if title_contains.lower() not in title_value.lower():
                    continue
            matches.append(widget)
        return matches[-1] if matches else None

    def destroy_widget(widget):
        """Close a transient widget without failing the generator."""
        if widget is None:
            return
        try:
            widget.destroy()
        except Exception:
            pass

    class StaticWrapper:
        """Small immutable wrapper used for documentation-only demo screens."""

        def __init__(self, items, entity_type=None):
            self._items = [copy.deepcopy(item) for item in items]
            self.entity_type = entity_type or ""

        def load_items(self):
            """Return wrapped items."""
            return [copy.deepcopy(item) for item in self._items]

        def save_item(self, *_args, **_kwargs):
            """Ignore save attempts in docs mode."""
            return None

        def save_items(self, items):
            """Store updated items in memory for widgets that expect persistence."""
            self._items = [copy.deepcopy(item) for item in items]
            return None

    class DocsLayoutStore:
        """Keep GM Table screenshots deterministic and side-effect free."""

        def get_table_layout(self, _table_id):
            """Return empty table layout."""
            return {}

        def save_table_layout(self, _table_id, _layout):
            """Ignore persisted table layouts."""
            return None

        def clear_table_layout(self, _table_id):
            """Ignore cleared table layouts."""
            return None

        def get_table_name(self, _table_id):
            """Return the default docs table name."""
            return "Main"

        def get_scenario_layout(self, _scenario_name):
            """Return empty legacy scenario layout."""
            return {}

        def save_scenario_layout(self, _scenario_name, _layout):
            """Ignore persisted legacy scenario layouts."""
            return None

        def clear_scenario_layout(self, _scenario_name):
            """Ignore cleared legacy scenario layouts."""
            return None

    class DocsSelectionStore:
        """Avoid persisting campaign overview selection state during doc generation."""

        @staticmethod
        def load(_campaign_record):
            """Return empty selection state."""
            return type("_State", (), {"arc_name": "", "scenario_title": ""})()

        @staticmethod
        def save(campaign_record, **_kwargs):
            """Return campaign unchanged."""
            return campaign_record

    demo_scenarios = [
        {
            "Title": "Opening Night at Blackreef",
            "Summary": "A diplomatic gala unravels when a theft exposes the campaign's first conspiracy.",
            "Briefing": "Hold the peace long enough to identify who stole the resonance key.",
            "Objective": "Secure the resonance key before the city council fractures.",
            "Hook": "A trusted envoy disappears during the launch celebration.",
            "Stakes": "If the theft stays unsolved, the alliance collapses by dawn.",
            "Secrets": "The theft was staged by a council patron looking to force martial law.",
            "Scenes": [
                {"Title": "Grand Arrival"},
                {"Title": "Sabotaged Toast"},
                {"Title": "Midnight Pursuit"},
            ],
            "NPCs": ["Ambassador Neris", "Captain Vale"],
            "Places": ["Blackreef Hall", "Skybridge Docks"],
            "Factions": ["City Council", "Harbor Watch"],
            "Villains": ["Patron Selk"],
        },
        {
            "Title": "The Meridian Dead Drop",
            "Summary": "The crew races rival agents across the transit district to intercept a leaking informant.",
            "Briefing": "Trace the courier route and keep the dead drop from reaching a hostile broker.",
            "Objective": "Recover the courier ledger and identify the broker's buyer.",
            "Hook": "A coded message points to a dead drop hidden inside a moving train depot.",
            "Stakes": "If the ledger changes hands, every safehouse in the district is compromised.",
            "Secrets": "The courier is cooperating with the enemy to protect a sibling held off-world.",
            "Scenes": [
                {"Title": "Signal Intercept"},
                {"Title": "Depot Sweep"},
                {"Title": "Broker Exchange"},
            ],
            "NPCs": ["Courier Ryn", "Inspector Morrow"],
            "Places": ["Meridian Depot", "Lower Market"],
            "Factions": ["Rail Syndicate", "Harbor Watch"],
            "Villains": ["Broker Thane"],
        },
        {
            "Title": "Glass Cathedral Breach",
            "Summary": "An extraction mission inside the cathedral archive reveals the villain's larger ritual network.",
            "Briefing": "Enter the archive, steal the ritual ledger, and escape before the vault seals.",
            "Objective": "Expose the ritual network and keep the cathedral relic out of enemy hands.",
            "Hook": "A recovered cipher points to a vault under the cathedral floor.",
            "Stakes": "Failure gives the enemy enough fuel to trigger citywide blackouts.",
            "Secrets": "The relic already holds a fragment of the same energy the party is protecting.",
            "Scenes": [
                {"Title": "Choir Distraction"},
                {"Title": "Archive Vault"},
                {"Title": "Bridge Collapse"},
            ],
            "NPCs": ["Archivist Dema", "Captain Vale"],
            "Places": ["Glass Cathedral", "Flooded Archive"],
            "Factions": ["Choir Militant", "City Council"],
            "Villains": ["Patron Selk"],
        },
        {
            "Title": "Ashfall Extraction",
            "Summary": "The finale forces the crew to evacuate allies while choosing which district to save first.",
            "Briefing": "Coordinate the evacuation and decide how much of the city can still be held.",
            "Objective": "Keep the evacuation corridor open and stop the reactor collapse.",
            "Hook": "The skyline ignites as every unresolved thread converges in the harbor.",
            "Stakes": "Thousands die or flee if the corridor closes before sunrise.",
            "Secrets": "The reactor collapse was triggered early by an insider on the war council.",
            "Scenes": [
                {"Title": "Harbor Fires"},
                {"Title": "Evacuation Line"},
                {"Title": "Reactor Core"},
            ],
            "NPCs": ["Ambassador Neris", "Inspector Morrow"],
            "Places": ["South Harbor", "Reactor Spine"],
            "Factions": ["Harbor Watch", "Rail Syndicate"],
            "Villains": ["War Councillor Voss"],
        },
    ]
    demo_objects = [
        {
            "Name": "Resonance Key",
            "Description": "A council vault key tuned to ritual harmonics and coded council seals.",
            "Stats": "Encrypted access shard",
            "Secrets": "Carries a hidden override signature tied to the sabotage plot.",
            "Category": "Artifact",
        },
        {
            "Name": "Ashfall Transit Case",
            "Description": "Courier-grade case with tamper alarms, false bottom, and city rail tags.",
            "Stats": "Armored shell, biometric latch",
            "Secrets": "Contains the broker ledger and a second decoy compartment.",
            "Category": "Equipment",
        },
        {
            "Name": "Cathedral Relay Lens",
            "Description": "Glass relay lens used to focus blackout rituals across harbor districts.",
            "Stats": "Fragile focus component",
            "Secrets": "Still holds trace energy that identifies the cathedral cell.",
            "Category": "Arcane Device",
        },
    ]
    demo_campaigns = [
        {
            "Name": "Shattered Meridian",
            "Logline": "A city-scale conspiracy thriller where diplomacy, sabotage, and evacuation collide.",
            "Genre": "Science Fiction",
            "Tone": "Tense political survival",
            "Setting": "Meridian Prime, a vertical harbor city balancing trade, ritual tech, and military pressure.",
            "Status": "Running",
            "StartDate": "2187-04-03",
            "EndDate": "",
            "MainObjective": "Hold the coalition together long enough to expose the sabotage network.",
            "Stakes": "Lose the city council and Meridian becomes an occupied war port by the season finale.",
            "Themes": "Trust under pressure\nInfrastructure as battlefield\nSacrifice without certainty",
            "Notes": "Use the campaign builder to keep arc stakes readable and scenario ownership clear.",
            "LinkedScenarios": [scenario["Title"] for scenario in demo_scenarios],
            "Arcs": [
                {
                    "name": "Council Fracture",
                    "summary": "Political sabotage turns routine diplomacy into survival work.",
                    "objective": "Identify who is destabilizing the council and contain the public fallout.",
                    "status": "Running",
                    "thread": "Council sabotage",
                    "scenarios": [
                        "Opening Night at Blackreef",
                        "The Meridian Dead Drop",
                    ],
                },
                {
                    "name": "Cathedral Fallout",
                    "summary": "The conspiracy expands into ritual infrastructure and citywide evacuation planning.",
                    "objective": "Expose the ritual network and keep the harbor alive long enough to evacuate civilians.",
                    "status": "Planned",
                    "thread": "Ritual blackout",
                    "scenarios": [
                        "Glass Cathedral Breach",
                        "Ashfall Extraction",
                    ],
                },
            ],
        }
    ]

    def apply_fallback_assets():
        """Reuse committed screenshots when live capture is unavailable."""
        fallback_assets = {
            "main_window": DOCS_DIR / "images" / "main_window.png",
            "entity_scenarios": DOCS_DIR / "images" / "entity_scenarios.png",
            "entity_pcs": DOCS_DIR / "images" / "entity_pcs.png",
            "entity_npcs": DOCS_DIR / "images" / "entity_npcs.png",
            "entity_creatures": DOCS_DIR / "images" / "entity_creatures.png",
            "entity_factions": DOCS_DIR / "images" / "entity_factions.png",
            "entity_places": DOCS_DIR / "images" / "entity_places.png",
            "entity_informations": DOCS_DIR / "images" / "entity_informations.png",
            "entity_clues": DOCS_DIR / "images" / "entity_clues.png",
            "entity_maps": DOCS_DIR / "images" / "entity_maps.png",
            "entity_books": DOCS_DIR / "images" / "entity_books.png",
            "character_graph": DOCS_DIR / "images" / "character_graph.png",
            "faction_graph": DOCS_DIR / "images" / "faction_graph.png",
            "scenario_graph": DOCS_DIR / "images" / "scenario_graph.png",
            "scenario_editor": DOCS_DIR / "images" / "scenario_editor.png",
            "custom_fields_editor": DOCS_DIR / "images" / "custom_fields_editor.png",
            "map_tool_selector": DOCS_DIR / "images" / "map_tool_selector.png",
            "map_tool_map1": DOCS_DIR / "images" / "map_tool_map1.png",
            "map_tool_map2": DOCS_DIR / "images" / "map_tool_map2.png",
            "map_tool_rectangle": DOCS_DIR / "images" / "map_tool_rectangle.png",
            "map_tool_oval": DOCS_DIR / "images" / "map_tool_oval.png",
            "whiteboard": DOCS_DIR / "images" / "whiteboard.png",
            "world_map": DOCS_DIR / "images" / "world_map.png",
            "dice_roller": DOCS_DIR / "images" / "dice_roller.png",
            "dice_bar": DOCS_DIR / "images" / "dice_bar.png",
            "audio_bar": DOCS_DIR / "images" / "audio_bar.png",
            "book_viewer": DOCS_DIR / "images" / "book_viewer.png",
            "scene_flow_viewer": DOCS_DIR / "images" / "scene_flow_viewer.png",
            "gm_screen": DOCS_DIR / "images" / "gm_screen.png",
        }
        for key, path in fallback_assets.items():
            if (not shots.get(key)) and path.exists():
                shots[key] = str(path)

    def capture_docs_only_windows(master):
        """Capture feature windows that do not require the full application shell."""
        def wait_for_list_rows(view, timeout=8.0):
            """Wait for a GenericListView to finish its first data chunk."""
            deadline = time.time() + timeout
            top = view.winfo_toplevel()
            while time.time() < deadline:
                settle_widget(top, cycles=1, delay=0.04)
                try:
                    tree = getattr(view, "tree", None)
                    if getattr(view, "_initial_dataset_ready", False):
                        if tree is not None and tree.winfo_exists() and tree.get_children():
                            return True
                        if getattr(view, "filtered_items", None):
                            return True
                except Exception:
                    pass
                time.sleep(0.08)
            return False

        objects_top = None
        try:
            from modules.generic.generic_list_view import GenericListView
            from modules.helpers.template_loader import load_template

            objects_top = ctk.CTkToplevel(master)
            objects_top.title("Objects Manager Preview")
            objects_top.geometry("1600x860+80+60")
            objects_top.lift()
            objects_top.focus_force()
            object_view = GenericListView(
                objects_top,
                StaticWrapper(demo_objects, entity_type="objects"),
                load_template("objects"),
            )
            object_view.pack(fill="both", expand=True)
            object_view._load_session_id += 1
            object_view._load_queue = None
            object_view.items = [copy.deepcopy(item) for item in demo_objects]
            object_view.filtered_items = [copy.deepcopy(item) for item in demo_objects]
            object_view.refresh_list(skip_background_fetch=True)
            wait_for_list_rows(object_view)
            shots["entity_objects"] = str(
                grab_widget_screenshot(object_view, "entity_objects") or ""
            )
        except Exception:
            pass
        finally:
            destroy_widget(objects_top)

        detail_top = None
        try:
            from modules.generic.entity_detail_factory import create_scenario_detail_frame

            detail_top = ctk.CTkToplevel(master)
            detail_top.title("Scenario Detail Preview")
            detail_top.geometry("1400x900")
            detail_top.lift()
            detail_top.focus_force()
            detail_frame = create_scenario_detail_frame(
                "Scenarios",
                copy.deepcopy(demo_scenarios[0]),
                detail_top,
                open_entity_callback=None,
            )
            if detail_frame is not None:
                detail_frame.pack(fill="both", expand=True)
            settle_widget(detail_top)
            shots["scenario_detail"] = str(grab_widget_screenshot(detail_top, "scenario_detail") or "")
        except Exception:
            pass
        finally:
            destroy_widget(detail_top)

        generator_top = None
        try:
            from modules.scenarios.scenario_generator_view import ScenarioGeneratorView

            generator_top = ctk.CTkToplevel(master)
            generator_top.title("Scenario Generator Preview")
            generator_top.geometry("1360x900")
            generator_top.lift()
            generator_top.focus_force()
            generator_view = ScenarioGeneratorView(generator_top)
            generator_view.pack(fill="both", expand=True)
            try:
                generator_view.generate_campaign()
            except Exception:
                pass
            settle_widget(generator_top)
            shots["scenario_generator"] = str(
                grab_widget_screenshot(generator_top, "scenario_generator") or ""
            )
        except Exception:
            pass
        finally:
            destroy_widget(generator_top)

        importer_window = None
        try:
            from modules.scenarios.scenario_importer import ScenarioImportWindow

            importer_window = ScenarioImportWindow(master)
            try:
                importer_window.scenario_textbox.insert(
                    "1.0",
                    "Title: Meridian Dead Drop\nSummary: A courier exchange goes bad at the depot.\nSecrets: The broker is working for the council saboteur.",
                )
            except Exception:
                pass
            settle_widget(importer_window)
            shots["scenario_importer"] = str(
                grab_widget_screenshot(importer_window, "scenario_importer") or ""
            )
        except Exception:
            pass
        finally:
            destroy_widget(importer_window)

        scenario_builder_window = None
        try:
            from modules.scenarios.scenario_builder_wizard import ScenarioBuilderWizard

            scenario_builder_window = ScenarioBuilderWizard(master, on_saved=lambda: None)
            scenario_builder_window.wizard_state.update(copy.deepcopy(demo_scenarios[0]))
            try:
                scenario_builder_window._on_wizard_state_changed()
            except Exception:
                pass
            scenario_builder_window._show_step(0)
            settle_widget(scenario_builder_window)
            shots["scenario_builder"] = str(
                grab_widget_screenshot(scenario_builder_window, "scenario_builder") or ""
            )
        except Exception:
            pass
        finally:
            destroy_widget(scenario_builder_window)

        sound_manager_window = None
        try:
            from modules.audio.ui.sound_manager_window import SoundManagerWindow

            sound_manager_window = SoundManagerWindow(master)
            try:
                sound_manager_window.show()
            except Exception:
                pass
            settle_widget(sound_manager_window)
            shots["sound_manager"] = str(
                grab_widget_screenshot(sound_manager_window, "sound_manager") or ""
            )
        except Exception:
            pass
        finally:
            destroy_widget(sound_manager_window)

        builder_window = None
        try:
            from modules.campaigns.ui.campaign_builder_wizard import CampaignBuilderWizard

            builder_window = CampaignBuilderWizard(
                master,
                campaign_wrapper=StaticWrapper(demo_campaigns),
                scenario_wrapper=StaticWrapper(demo_scenarios),
            )
            builder_window._apply_campaign_to_form(demo_campaigns[0])
            builder_window._refresh_arcs_preview()
            builder_window._refresh_review()

            for key, step_index in [
                ("campaign_builder_foundation", 0),
                ("campaign_builder_arcs", 1),
                ("campaign_builder_review", 2),
            ]:
                builder_window._show_step(step_index)
                settle_widget(builder_window)
                shots[key] = str(grab_widget_screenshot(builder_window, key) or "")
        except Exception:
            pass
        finally:
            destroy_widget(builder_window)

        campaign_overview_window = None
        try:
            from modules.campaigns.ui.graphical_display.window import CampaignGraphWindow

            campaign_overview_window = CampaignGraphWindow(
                master,
                campaign_wrapper=StaticWrapper(demo_campaigns),
                scenario_wrapper=StaticWrapper(demo_scenarios),
            )
            if hasattr(campaign_overview_window, "panel"):
                campaign_overview_window.panel._selection_store = DocsSelectionStore()
            settle_widget(campaign_overview_window)
            shots["campaign_overview"] = str(
                grab_widget_screenshot(campaign_overview_window, "campaign_overview") or ""
            )

            panel = getattr(campaign_overview_window, "panel", None)
            if panel is not None:
                try:
                    panel._select_arc(1)
                    panel._select_scenario(1)
                except Exception:
                    pass
                settle_widget(campaign_overview_window)
                shots["campaign_overview_scenario"] = str(
                    grab_widget_screenshot(campaign_overview_window, "campaign_overview_scenario") or ""
                )
        except Exception:
            pass
        finally:
            destroy_widget(campaign_overview_window)

        gm_table_top = None
        try:
            from modules.scenarios.gm_table_view import GMTableView

            gm_table_top = ctk.CTkToplevel(master)
            gm_table_top.title("GM Table Preview")
            gm_table_top.geometry("1720x980")
            gm_table_top.lift()
            gm_table_top.focus_force()

            gm_table_view = GMTableView(
                gm_table_top,
                scenario_item=copy.deepcopy(demo_scenarios[0]),
                root_app=master,
                layout_store=DocsLayoutStore(),
            )
            gm_table_view.wrappers["Scenarios"] = StaticWrapper([copy.deepcopy(demo_scenarios[0])])
            gm_table_view.pack(fill="both", expand=True)

            settle_widget(gm_table_top)
            shots["gm_table_default"] = str(
                grab_widget_screenshot(gm_table_top, "gm_table_default") or ""
            )

            for option in ["Campaign Dashboard", "Scene Flow", "Whiteboard", "Random Tables"]:
                try:
                    gm_table_view._handle_add_option(option)
                    gm_table_top.update_idletasks()
                    gm_table_top.update()
                except Exception:
                    continue
            try:
                gm_table_view._tile_panels()
            except Exception:
                pass
            settle_widget(gm_table_top)
            shots["gm_table_panels"] = str(
                grab_widget_screenshot(gm_table_top, "gm_table_panels") or ""
            )
        except Exception:
            pass
        finally:
            destroy_widget(gm_table_top)

        asset_library_window = None
        try:
            from modules.generic.cross_campaign_asset_library import (
                CrossCampaignAssetLibraryWindow,
                OnlineGalleryDialog,
            )
            from modules.generic.cross_campaign_asset_service import CampaignDatabase
            from modules.generic.github_gallery_client import GalleryBundleSummary

            asset_library_window = CrossCampaignAssetLibraryWindow(master)
            try:
                asset_library_window.gallery_client._token = "docs-demo-token"
                asset_library_window._update_publish_button_state()
            except Exception:
                pass

            if not getattr(asset_library_window, "source_campaigns", None):
                asset_library_window.selected_campaign = CampaignDatabase(
                    name="Docs Demo Campaign",
                    root=ROOT,
                    db_path=ROOT / "docs-demo.db",
                )
                asset_library_window.entity_records = {
                    key: [] for key in asset_library_window.entity_types
                }
                if "npcs" in asset_library_window.entity_records:
                    asset_library_window.entity_records["npcs"] = [
                        {
                            "Name": "Quartermaster Hale",
                            "Description": "Keeps the coalition supplied while hiding a side channel to the resistance.",
                            "Portrait": "docs/images/entity_npcs.png",
                        }
                    ]
                if "maps" in asset_library_window.entity_records:
                    asset_library_window.entity_records["maps"] = [
                        {
                            "Name": "Meridian Harbor",
                            "Description": "A dense operations map used for the campaign finale.",
                            "Image": "docs/images/map_tool_map1.png",
                        }
                    ]
                asset_library_window.populate_lists()

            def capture_asset_library_tab(entity_type: str, shot_key: str) -> bool:
                """Capture a populated asset library tab."""
                tree = asset_library_window.treeviews.get(entity_type)
                if tree is None or not tree.get_children():
                    return False
                label = (
                    asset_library_window.entity_definitions.get(entity_type, {}).get("label")
                    or entity_type.replace("_", " ").title()
                )
                try:
                    asset_library_window.tabview.set(label)
                except Exception:
                    pass
                first_item = tree.get_children()[0]
                tree.selection_set(first_item)
                tree.focus(first_item)
                asset_library_window.update_preview_from_tree(entity_type)
                settle_widget(asset_library_window)
                shots[shot_key] = str(
                    grab_widget_screenshot(asset_library_window, shot_key) or ""
                )
                return True

            captured_overview = False
            for entity_type in ("npcs", "objects", "places", "pcs", "creatures"):
                if capture_asset_library_tab(entity_type, "asset_library_overview"):
                    captured_overview = True
                    break
            if not captured_overview:
                capture_asset_library_tab("maps", "asset_library_overview")
            capture_asset_library_tab("maps", "asset_library_maps")

            fake_bundles = [
                GalleryBundleSummary(
                    release_id=1,
                    asset_id=101,
                    release_name="Meridian Starter Bundle",
                    tag="v1.0.0",
                    asset_name="meridian_starter.zip",
                    download_url="https://example.invalid/meridian_starter.zip",
                    size=18_432_000,
                    published_at=None,
                    author="llankar",
                    description="Starter campaign bundle with maps, NPCs, and handouts.",
                    entity_counts={"maps": 4, "npcs": 12, "objects": 5},
                    source_campaign="Shattered Meridian",
                    manifest_created_at="",
                    metadata={"bundle_mode": "asset_bundle"},
                    html_url="https://example.invalid/releases/meridian-starter",
                    is_draft=False,
                    asset_count=1,
                    asset_download_count=27,
                ),
                GalleryBundleSummary(
                    release_id=2,
                    asset_id=102,
                    release_name="Image Library Expansion",
                    tag="v1.1.0",
                    asset_name="image_library_expansion.zip",
                    download_url="https://example.invalid/image_library_expansion.zip",
                    size=42_880_000,
                    published_at=None,
                    author="llankar",
                    description="Texture and portrait pack for the shared image library.",
                    entity_counts={"image_assets": 48},
                    source_campaign="Shared Media",
                    manifest_created_at="",
                    metadata={"bundle_mode": "asset_bundle"},
                    html_url="https://example.invalid/releases/image-library-expansion",
                    is_draft=False,
                    asset_count=1,
                    asset_download_count=14,
                ),
            ]
            original_list_bundles = getattr(asset_library_window.gallery_client, "list_bundles", None)
            asset_library_window.gallery_client.list_bundles = lambda: fake_bundles
            try:
                asset_library_window.open_online_gallery()
                online_dialog = getattr(asset_library_window, "_online_dialog", None)
                if isinstance(online_dialog, OnlineGalleryDialog):
                    online_dialog._populate(fake_bundles)
                    children = online_dialog.tree.get_children()
                    if children:
                        online_dialog.tree.selection_set(children[0])
                        online_dialog.tree.focus(children[0])
                        online_dialog._on_select(None)
                    settle_widget(online_dialog)
                    shots["asset_library_online_gallery"] = str(
                        grab_widget_screenshot(online_dialog, "asset_library_online_gallery") or ""
                    )
            finally:
                if callable(original_list_bundles):
                    asset_library_window.gallery_client.list_bundles = original_list_bundles
        except Exception:
            pass
        finally:
            dialog = getattr(asset_library_window, "_online_dialog", None) if asset_library_window is not None else None
            destroy_widget(dialog)
            destroy_widget(asset_library_window)

    if os.name == "nt":
        docs_root = None
        try:
            docs_root = ctk.CTk()
            try:
                offscreen_x = docs_root.winfo_screenwidth() + 200
                offscreen_y = docs_root.winfo_screenheight() + 200
                docs_root.geometry(f"1x1+{offscreen_x}+{offscreen_y}")
            except Exception:
                docs_root.geometry("1x1+3000+3000")
            try:
                docs_root.attributes("-alpha", 0)
            except Exception:
                pass
            settle_widget(docs_root, cycles=2, delay=0.02)
            try:
                docs_root.tk.eval("proc bgerror {msg} {}")
            except Exception:
                pass
        except Exception:
            docs_root = None
        try:
            os.chdir(original_cwd)
        except Exception:
            pass
        if docs_root is not None:
            try:
                capture_docs_only_windows(docs_root)
            finally:
                try:
                    docs_root.destroy()
                except Exception:
                    pass
        apply_fallback_assets()
        restore_tk_runtime()
        return {k: v for k, v in shots.items() if v}
    try:
        from main_window import MainWindow
        from modules.generic.generic_model_wrapper import GenericModelWrapper
        from modules.helpers.template_loader import load_template
        from modules.generic.entity_detail_factory import create_scenario_detail_frame
        from modules.generic.custom_fields_editor import CustomFieldsEditor
        from modules.generic.generic_editor_window import GenericEditorWindow
        from modules.pcs.display_pcs import display_pcs_in_banner
        from modules.generic.generic_list_selection_view import GenericListSelectionView
        from modules.generic.generic_list_view import GenericListView
    except Exception:
        restore_tk_runtime()
        return {}
    try:
        app = MainWindow()
    except Exception:
        restore_tk_runtime()
        return {}
    try:
        os.chdir(original_cwd)
    except Exception:
        pass
    settle_widget(app)
    shots["main_window"] = str(grab_widget_screenshot(app, "main_window") or "")

    def capture_sidebar_sections():
        """Handle capture sidebar sections."""
        try:
            # Keep capture sidebar sections resilient if this step fails.
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
                # Process each (idx, (shot_key, _title)) from enumerate(keys).
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
                # Handle the branch where len(sections) > 1.
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

    def wait_for_entity_list(timeout=8.0):
        """Handle wait for entity list."""
        deadline = time.time() + timeout
        last_view = None
        while time.time() < deadline:
            # Keep looping while time.time() < deadline.
            try:
                app.update_idletasks()
                app.update()
            except Exception:
                break
            candidates = [child for child in app.inner_content_frame.winfo_children() if isinstance(child, GenericListView)]
            if candidates:
                # Continue with this path when candidates is set.
                last_view = candidates[-1]
                try:
                    # Keep wait for entity list resilient if this step fails.
                    if getattr(last_view, "_initial_dataset_ready", False):
                        # Handle the branch where getattr(last_view, '_initial_dataset_ready', False).
                        tree = getattr(last_view, "tree", None)
                        if tree is not None and tree.winfo_exists() and tree.get_children():
                            return last_view
                        if getattr(last_view, "filtered_items", None):
                            return last_view
                except Exception:
                    pass
            time.sleep(0.1)
        return last_view

    def ensure_pc_banner():
        """Ensure PC banner."""
        try:
            app.banner_frame.grid(row=0, column=0, sticky="ew")
            app.inner_content_frame.grid(row=1, column=0, sticky="nsew")
        except Exception:
            pass
        try:
            app.content_frame.grid_rowconfigure(0, weight=0)
            app.content_frame.grid_rowconfigure(1, weight=1)
        except Exception:
            pass
        app.banner_visible = True
        try:
            # Keep PC banner resilient if this step fails.
            for child in app.banner_frame.winfo_children():
                child.destroy()
        except Exception:
            pass
        pcs_items = {}
        try:
            pcs_items = {pc.get("Name") or f"PC {idx}": pc for idx, pc in enumerate(app.pc_wrapper.load_items(), 1)}
        except Exception:
            pcs_items = {}
        try:
            display_pcs_in_banner(app.banner_frame, pcs_items)
        except Exception:
            pass
        try:
            app.move_current_view()
        except Exception:
            pass
        app.update_idletasks()
        app.update()

    # Let delayed startup hooks finish, then reset banner/content layout.
    time.sleep(1.0)
    app.update_idletasks()
    app.update()
    try:
        app.clear_current_content()
    except Exception:
        pass
    ensure_pc_banner()

    for ent in ["scenarios", "pcs", "npcs", "creatures", "factions", "places", "objects", "informations", "clues", "books", "maps"]:
        try:
            # Keep screenshot app views resilient if this step fails.
            ensure_pc_banner()
            app.open_entity(ent)
            app.update()
            wait_for_entity_list(timeout=8.0)
            ensure_pc_banner()
            app.update_idletasks()
            app.update()
            shots[f"entity_{ent}"] = str(grab_widget_screenshot(app, f"entity_{ent}") or "")
        except Exception:
            pass

    for key, fn in [
        ("character_graph", app.open_character_graph_editor),
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
        settle_widget(app)
        generator_view = getattr(app, "current_open_view", None) or app
        shots["scenario_generator"] = str(
            grab_widget_screenshot(generator_view, "scenario_generator") or ""
        )
    except Exception:
        pass
    importer_top = None
    try:
        app.open_scenario_importer()
        settle_widget(app)
        importer_top = find_toplevel(app, title_contains="Import Formatted Scenario")
        if importer_top is not None:
            shots["scenario_importer"] = str(
                grab_widget_screenshot(importer_top, "scenario_importer") or ""
            )
    except Exception:
        pass
    finally:
        destroy_widget(importer_top)
    scenario_builder_top = None
    try:
        app.open_scenario_builder()
        settle_widget(app)
        scenario_builder_top = find_toplevel(app, title_contains="Scenario Builder Wizard")
        if scenario_builder_top is not None:
            shots["scenario_builder"] = str(
                grab_widget_screenshot(scenario_builder_top, "scenario_builder") or ""
            )
    except Exception:
        pass
    finally:
        destroy_widget(scenario_builder_top)
    builder_window = None
    try:
        from modules.campaigns.ui.campaign_builder_wizard import CampaignBuilderWizard

        builder_window = CampaignBuilderWizard(
            app,
            campaign_wrapper=StaticWrapper(demo_campaigns),
            scenario_wrapper=StaticWrapper(demo_scenarios),
        )
        builder_window._apply_campaign_to_form(demo_campaigns[0])
        builder_window._refresh_arcs_preview()
        builder_window._refresh_review()

        for key, step_index in [
            ("campaign_builder_foundation", 0),
            ("campaign_builder_arcs", 1),
            ("campaign_builder_review", 2),
        ]:
            builder_window._show_step(step_index)
            settle_widget(builder_window)
            shots[key] = str(grab_widget_screenshot(builder_window, key) or "")
    except Exception:
        pass
    finally:
        if builder_window is not None:
            try:
                builder_window.destroy()
            except Exception:
                pass
            app.update()
    campaign_overview_window = None
    try:
        from modules.campaigns.ui.graphical_display.window import CampaignGraphWindow

        campaign_overview_window = CampaignGraphWindow(
            app,
            campaign_wrapper=StaticWrapper(demo_campaigns),
            scenario_wrapper=StaticWrapper(demo_scenarios),
        )
        if hasattr(campaign_overview_window, "panel"):
            campaign_overview_window.panel._selection_store = DocsSelectionStore()
        settle_widget(campaign_overview_window)
        shots["campaign_overview"] = str(
            grab_widget_screenshot(campaign_overview_window, "campaign_overview") or ""
        )

        panel = getattr(campaign_overview_window, "panel", None)
        if panel is not None:
            try:
                panel._select_arc(1)
                panel._select_scenario(1)
            except Exception:
                pass
            settle_widget(campaign_overview_window)
            shots["campaign_overview_scenario"] = str(
                grab_widget_screenshot(campaign_overview_window, "campaign_overview_scenario") or ""
            )
    except Exception:
        pass
    finally:
        if campaign_overview_window is not None:
            try:
                campaign_overview_window.destroy()
            except Exception:
                pass
            app.update()
    try:
        # Keep screenshot app views resilient if this step fails.
        app.open_scene_flow_viewer()
        settle_widget(app)
        sf_top = getattr(app, "_scene_flow_window", None)
        if sf_top:
            shots["scene_flow_viewer"] = str(grab_widget_screenshot(sf_top, "scene_flow_viewer") or "")
    except Exception:
        pass

    def build_sample_scenario(template):
        """Build sample scenario."""
        sample = {}
        for field in template.get("fields", []):
            # Process each field from template.get('fields', []).
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
        # Keep screenshot app views resilient if this step fails.
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
        # Continue with this path when scenario item is set.
        detail_top = None
        try:
            # Keep screenshot app views resilient if this step fails.
            detail_top = ctk.CTkToplevel(app)
            detail_top.title("Scenario Detail Preview")
            detail_top.geometry("1400x900")
            detail_top.lift()
            detail_top.focus_force()
            detail_frame = create_scenario_detail_frame(
                "Scenarios",
                scenario_item,
                detail_top,
                open_entity_callback=None,
            )
            if detail_frame is not None:
                detail_frame.pack(fill="both", expand=True)
            settle_widget(detail_top)
            shots["scenario_detail"] = str(grab_widget_screenshot(detail_top, "scenario_detail") or "")
        except Exception:
            pass
        finally:
            if detail_top is not None:
                # Handle the branch where detail top is available.
                try:
                    detail_top.destroy()
                except Exception:
                    pass
                app.update()

    if scenario_item and scenario_template:
        # Continue with this path when scenario item is set and scenario template is set.
        editor_window = None
        try:
            # Keep screenshot app views resilient if this step fails.
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
                # Handle the branch where editor window is available.
                try:
                    editor_window.destroy()
                except Exception:
                    pass
                app.update()

    fields_editor = None
    try:
        # Keep screenshot app views resilient if this step fails.
        fields_editor = CustomFieldsEditor(app)
        fields_editor.update_idletasks()
        fields_editor.update()
        shots["custom_fields_editor"] = str(grab_widget_screenshot(fields_editor, "custom_fields_editor") or "")
    except Exception:
        pass
    finally:
        if fields_editor is not None:
            # Handle the branch where fields editor is available.
            try:
                fields_editor.destroy()
            except Exception:
                pass
            app.update()

    def ensure_map_samples(ctrl):
        """Ensure map samples."""
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
                # Process each (key, item) from existing.items().
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
            # Process each (idx, src) from enumerate(sample_sources, 1).
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
        # Keep screenshot app views resilient if this step fails.
        app.map_tool()
        settle_widget(app)
        map_top = getattr(app, "_map_tool_window", None)
        if map_top:
            # Continue with this path when map top is set.
            shots["map_tool_selector"] = str(grab_widget_screenshot(map_top, "map_tool_selector") or "")
            ctrl = getattr(app, 'map_controller', None)
            map_names = ensure_map_samples(ctrl)
            if ctrl and map_names:
                # Continue with this path when ctrl is set and map names is set.
                for idx, name in enumerate(map_names[:2], 1):
                    try:
                        # Keep screenshot app views resilient if this step fails.
                        ctrl._on_display_map("maps", name)
                        settle_widget(map_top)
                        key = f"map_tool_map{idx}"
                        shots[key] = str(grab_widget_screenshot(map_top, key) or "")
                    except Exception:
                        continue
                try:
                    # Keep screenshot app views resilient if this step fails.
                    ctrl._on_drawing_tool_change("Rectangle"); settle_widget(map_top)
                    shots["map_tool_rectangle"] = str(grab_widget_screenshot(map_top, "map_tool_rectangle") or "")
                    ctrl._on_drawing_tool_change("Oval"); settle_widget(map_top)
                    shots["map_tool_oval"] = str(grab_widget_screenshot(map_top, "map_tool_oval") or "")
                    ctrl._on_drawing_tool_change("Token"); settle_widget(map_top)
                except Exception:
                    pass
    except Exception:
        pass

    # Whiteboard (GM view)
    try:
        # Keep screenshot app views resilient if this step fails.
        app.open_whiteboard()
        app.update(); app.update_idletasks()
        ensure_pc_banner()
        shots["whiteboard"] = str(grab_widget_screenshot(app, "whiteboard") or "")
    except Exception:
        pass

    # World Map (nested navigation)
    try:
        # Keep screenshot app views resilient if this step fails.
        app.open_world_map()
        settle_widget(app)
        wm_top = getattr(app, "_world_map_window", None)
        if wm_top:
            shots["world_map"] = str(grab_widget_screenshot(wm_top, "world_map") or "")
    except Exception:
        pass

    # Dice Roller and Dice Bar
    try:
        # Keep screenshot app views resilient if this step fails.
        app.open_dice_roller()
        settle_widget(app)
        dr_top = getattr(app, "dice_roller_window", None)
        if dr_top:
            shots["dice_roller"] = str(grab_widget_screenshot(dr_top, "dice_roller") or "")
    except Exception:
        pass
    try:
        # Keep screenshot app views resilient if this step fails.
        app.open_dice_bar()
        settle_widget(app)
        db_top = getattr(app, "dice_bar_window", None)
        if db_top:
            shots["dice_bar"] = str(grab_widget_screenshot(db_top, "dice_bar") or "")
    except Exception:
        pass

    # Sound & Music Manager + Audio Controls Bar
    try:
        # Keep screenshot app views resilient if this step fails.
        app.open_sound_manager()
        settle_widget(app)
        sm_top = getattr(app, "sound_manager_window", None)
        if sm_top:
            shots["sound_manager"] = str(grab_widget_screenshot(sm_top, "sound_manager") or "")
    except Exception:
        pass
    try:
        # Keep screenshot app views resilient if this step fails.
        app.open_audio_bar()
        settle_widget(app)
        ab_top = getattr(app, "audio_bar_window", None)
        if ab_top:
            shots["audio_bar"] = str(grab_widget_screenshot(ab_top, "audio_bar") or "")
    except Exception:
        pass

    # Book Viewer (generate a sample PDF if needed)
    try:
        # Keep screenshot app views resilient if this step fails.
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
                # Keep screenshot app views resilient if this step fails.
                writer = PdfWriter()
                # A4 portrait in points
                writer.add_blank_page(width=595, height=842)
                with sample_pdf.open("wb") as fh:
                    writer.write(fh)
            except Exception:
                pass
        if sample_pdf.exists():
            # Handle the branch where sample_pdf.exists().
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
        # Keep screenshot app views resilient if this step fails.
        try:
            app._prime_content_frames_for_gm_screen()
        except Exception:
            pass
        app.open_gm_screen()
        app.update()
        ensure_pc_banner()
        try:
            # Keep screenshot app views resilient if this step fails.
            list_selection = None
            for child in app.inner_content_frame.winfo_children():
                if isinstance(child, GenericListSelectionView):
                    list_selection = child
                    break
            if list_selection is not None:
                # Handle the branch where list selection is available.
                items = list_selection.tree.get_children()
                if items:
                    list_selection.tree.selection_set(items[0])
                    list_selection.tree.focus(items[0])
                    list_selection.open_selected()
                    app.update(); app.update_idletasks()
                    ensure_pc_banner()
        except Exception:
            pass
        shots["gm_screen"] = str(grab_widget_screenshot(app, "gm_screen") or "")
    except Exception:
        pass
    gm_table_top = None
    try:
        from modules.scenarios.gm_table_view import GMTableView

        scenario_items = []
        try:
            scenario_items = GenericModelWrapper("scenarios").load_items()
        except Exception:
            scenario_items = []
        gm_table_scenario = copy.deepcopy(scenario_items[0]) if scenario_items else copy.deepcopy(demo_scenarios[0])

        gm_table_top = ctk.CTkToplevel(app)
        gm_table_top.title("GM Table Preview")
        gm_table_top.geometry("1720x980")
        gm_table_top.lift()
        gm_table_top.focus_force()

        gm_table_view = GMTableView(
            gm_table_top,
            scenario_item=gm_table_scenario,
            root_app=app,
            layout_store=DocsLayoutStore(),
        )
        if not scenario_items:
            gm_table_view.wrappers["Scenarios"] = StaticWrapper([gm_table_scenario])
        gm_table_view.pack(fill="both", expand=True)

        for _ in range(6):
            gm_table_top.update_idletasks()
            gm_table_top.update()
            time.sleep(0.05)
        shots["gm_table_default"] = str(
            grab_widget_screenshot(gm_table_top, "gm_table_default") or ""
        )

        for option in ["Campaign Dashboard", "Scene Flow", "Whiteboard", "Random Tables"]:
            try:
                gm_table_view._handle_add_option(option)
                gm_table_top.update_idletasks()
                gm_table_top.update()
            except Exception:
                continue
        try:
            gm_table_view._tile_panels()
        except Exception:
            pass
        for _ in range(6):
            gm_table_top.update_idletasks()
            gm_table_top.update()
            time.sleep(0.05)
        shots["gm_table_panels"] = str(
            grab_widget_screenshot(gm_table_top, "gm_table_panels") or ""
        )
    except Exception:
        pass
    finally:
        if gm_table_top is not None:
            try:
                gm_table_top.destroy()
            except Exception:
                pass
            app.update()
    asset_library_window = None
    try:
        from modules.generic.cross_campaign_asset_library import OnlineGalleryDialog
        from modules.generic.cross_campaign_asset_service import CampaignDatabase
        from modules.generic.github_gallery_client import GalleryBundleSummary

        app.open_cross_campaign_asset_library()
        asset_library_window = getattr(app, "_asset_library_window", None)
        if asset_library_window is not None:
            try:
                asset_library_window.gallery_client._token = "docs-demo-token"
                asset_library_window._update_publish_button_state()
            except Exception:
                pass

            if not getattr(asset_library_window, "source_campaigns", None):
                asset_library_window.selected_campaign = CampaignDatabase(
                    name="Docs Demo Campaign",
                    root=ROOT,
                    db_path=ROOT / "docs-demo.db",
                )
                asset_library_window.entity_records = {
                    key: [] for key in asset_library_window.entity_types
                }
                if "npcs" in asset_library_window.entity_records:
                    asset_library_window.entity_records["npcs"] = [
                        {
                            "Name": "Quartermaster Hale",
                            "Description": "Keeps the coalition supplied while hiding a side channel to the resistance.",
                            "Portrait": "docs/images/entity_npcs.png",
                        }
                    ]
                if "maps" in asset_library_window.entity_records:
                    asset_library_window.entity_records["maps"] = [
                        {
                            "Name": "Meridian Harbor",
                            "Description": "A dense operations map used for the campaign finale.",
                            "Image": "docs/images/map_tool_map1.png",
                        }
                    ]
                asset_library_window.populate_lists()

            def capture_asset_library_tab(entity_type: str, shot_key: str) -> bool:
                """Capture a populated asset library tab."""
                tree = asset_library_window.treeviews.get(entity_type)
                if tree is None or not tree.get_children():
                    return False
                label = (
                    asset_library_window.entity_definitions.get(entity_type, {}).get("label")
                    or entity_type.replace("_", " ").title()
                )
                try:
                    asset_library_window.tabview.set(label)
                except Exception:
                    pass
                first_item = tree.get_children()[0]
                tree.selection_set(first_item)
                tree.focus(first_item)
                asset_library_window.update_preview_from_tree(entity_type)
                asset_library_window.update_idletasks()
                asset_library_window.update()
                shots[shot_key] = str(
                    grab_widget_screenshot(asset_library_window, shot_key) or ""
                )
                return True

            captured_overview = False
            for entity_type in ("npcs", "objects", "places", "pcs", "creatures"):
                if capture_asset_library_tab(entity_type, "asset_library_overview"):
                    captured_overview = True
                    break
            if not captured_overview:
                capture_asset_library_tab("maps", "asset_library_overview")
            capture_asset_library_tab("maps", "asset_library_maps")

            fake_bundles = [
                GalleryBundleSummary(
                    release_id=1,
                    asset_id=101,
                    release_name="Meridian Starter Bundle",
                    tag="v1.0.0",
                    asset_name="meridian_starter.zip",
                    download_url="https://example.invalid/meridian_starter.zip",
                    size=18_432_000,
                    published_at=None,
                    author="llankar",
                    description="Starter campaign bundle with maps, NPCs, and handouts.",
                    entity_counts={"maps": 4, "npcs": 12, "objects": 5},
                    source_campaign="Shattered Meridian",
                    manifest_created_at="",
                    metadata={"bundle_mode": "asset_bundle"},
                    html_url="https://example.invalid/releases/meridian-starter",
                    is_draft=False,
                    asset_count=1,
                    asset_download_count=27,
                ),
                GalleryBundleSummary(
                    release_id=2,
                    asset_id=102,
                    release_name="Image Library Expansion",
                    tag="v1.1.0",
                    asset_name="image_library_expansion.zip",
                    download_url="https://example.invalid/image_library_expansion.zip",
                    size=42_880_000,
                    published_at=None,
                    author="llankar",
                    description="Texture and portrait pack for the shared image library.",
                    entity_counts={"image_assets": 48},
                    source_campaign="Shared Media",
                    manifest_created_at="",
                    metadata={"bundle_mode": "asset_bundle"},
                    html_url="https://example.invalid/releases/image-library-expansion",
                    is_draft=False,
                    asset_count=1,
                    asset_download_count=14,
                ),
            ]
            original_list_bundles = getattr(asset_library_window.gallery_client, "list_bundles", None)
            asset_library_window.gallery_client.list_bundles = lambda: fake_bundles
            try:
                asset_library_window.open_online_gallery()
                online_dialog = getattr(asset_library_window, "_online_dialog", None)
                if isinstance(online_dialog, OnlineGalleryDialog):
                    online_dialog._populate(fake_bundles)
                    children = online_dialog.tree.get_children()
                    if children:
                        online_dialog.tree.selection_set(children[0])
                        online_dialog.tree.focus(children[0])
                        online_dialog._on_select(None)
                    online_dialog.update_idletasks()
                    online_dialog.update()
                    shots["asset_library_online_gallery"] = str(
                        grab_widget_screenshot(online_dialog, "asset_library_online_gallery") or ""
                    )
            finally:
                if callable(original_list_bundles):
                    asset_library_window.gallery_client.list_bundles = original_list_bundles
    except Exception:
        pass
    finally:
        dialog = getattr(asset_library_window, "_online_dialog", None) if asset_library_window is not None else None
        if dialog is not None:
            try:
                dialog.destroy()
            except Exception:
                pass
        if asset_library_window is not None:
            try:
                asset_library_window.destroy()
            except Exception:
                pass
            app.update()

    apply_fallback_assets()

    try:
        app.destroy()
    except Exception:
        pass
    restore_tk_runtime()
    return {k: v for k, v in shots.items() if v}



def build_html(api_data, menu_data, shots):
    """Build HTML."""
    def esc(s):
        """Handle esc."""
        return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def render_image(key):
        """Render image."""
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

    sections.append(
        """
        <section id=\"documentation-refresh\">
          <h2>Refreshing The Documentation</h2>
          <p>Refresh the committed documentation by running <code>python scripts/generate_docs.py</code> from the repository root.</p>
          <ul>
            <li>The script updates <code>docs/index.html</code>, <code>docs/user-manual.html</code>, and screenshot assets in <code>docs/images/</code>.</li>
            <li>Run it after UI, context-menu, screenshot, or API-surface changes so the docs stay aligned with the application.</li>
            <li>Use the same Python environment as the desktop app. The generator opens Tk/customtkinter windows and relies on Pillow <code>ImageGrab</code> for screenshots.</li>
            <li>Review the generated HTML and screenshots before committing them.</li>
          </ul>
          <p>See <code>docs/documentation_maintenance.md</code> for the full maintainer workflow and troubleshooting notes.</p>
        </section>
        """
    )

    if shots:
        # Continue with this path when shots is set.
        used = set()
        group_chunks = []

        def add_group(title, keys):
            """Handle add group."""
            items = []
            for key in keys:
                if key in shots and key not in used:
                    # Handle the branch where key is in shots and key is not in used.
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
        add_group("Campaign Planning", [
            "campaign_builder_foundation",
            "campaign_builder_arcs",
            "campaign_builder_review",
            "campaign_overview",
            "campaign_overview_scenario",
        ])
        add_group("Graph Editors", ["character_graph", "faction_graph", "scenario_graph"])
        add_group("GM & Scenario Tools", ["gm_screen", "scenario_generator", "scenario_importer"])
        add_group("GM Virtual Table", ["gm_table_default", "gm_table_panels"])
        add_group("Cross-campaign Asset Library", [
            "asset_library_overview",
            "asset_library_maps",
            "asset_library_online_gallery",
        ])
        add_group("Map Tools", ["map_tool_selector", "map_tool_map1", "map_tool_map2", "map_tool_rectangle", "map_tool_oval"])
        add_group("Whiteboard", ["whiteboard"])
        add_group("Dice & Music Bars", ["dice_bar", "audio_bar"])

        remaining = [k for k in sorted(shots) if k not in used]
        if remaining:
            group_chunks.append("<h3>Additional Views</h3>" + "".join(render_image(k) for k in remaining))

        sections.append("<section id='screenshots'><h2>UI Screenshots</h2>" + "".join(group_chunks) + "</section>")

    if menu_data:
        # Continue with this path when menu data is set.
        blocks = []
        for m in menu_data:
            items = ''.join(f"<li>{esc(lbl)}</li>" for lbl in m["items"])
            blocks.append(f"<div class='menu-block'><h3>{esc(m['module'])}</h3><ul>{items}</ul></div>")
        sections.append("<section id='context-menus'><h2>Right-Click Menus</h2>" + "\n".join(blocks) + "</section>")

    api_blocks = []
    for mod in api_data:
        # Process each mod from api_data.
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
    """Run the module entry point."""
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
    """Build user manual."""
    def img(key, alt=None):
        """Handle img."""
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
        """Handle section."""
        return f"<section><h2 id='{title.lower().replace(' ', '-')}'>{title}</h2>{body}</section>"

    def collect_items(filter_fn):
        """Collect items."""
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
        'characters/character_graph_editor.py', 'factions/faction_graph_editor.py', 'scenarios/scenario_graph_editor.py'
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
                '<b>Change Data Storage</b>: Open the database manager to select, create, or browse for campaign files.',
                '<b>Switch System</b>: Choose the rules system and visual theme for this campaign.',
                '<b>Manage Campaign Systems</b>: Edit system dice defaults, supported faces, and analyzer config.',
                '<b>Customize Fields</b>: Open the custom field editor (see Editor Tools).',
                '<b>New Entity Type</b>: Add custom entities and templates.',
                '<b>Create/Restore Campaign Backup</b>: Save or recover a full campaign archive.',
                '<b>Cross-campaign Asset Library</b>: Export/import NPCs, Objects, and Maps with media bundles.',
                '<b>Set SwarmUI Path</b>: Point the portrait generator at your SwarmUI installation.',
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
                '<b>Campaign Builder</b>, <b>Generate Scenario</b>, <b>Scenario Builder Wizard</b>, and <b>AI Wizard</b>: Automate outline, arc planning, or content generation.',
                '<b>Import Scenario</b>, <b>Import NPCs/Creatures from PDF</b>, and <b>Import Equipment from PDF</b>: Convert external sources into campaign data.',
                '<b>Campaign Overview</b>, <b>GM Table</b>, <b>GM Screen</b>, <b>Scene Flow Viewer</b>, <b>World Map</b>, <b>Map Tool</b>, and <b>Whiteboard</b>: Present and prep live session visuals.',
                '<b>Portrait tools</b>: Generate portraits (SwarmUI), auto-associate NPC portraits, or import folders of art.',
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
        "<nav><a href='#getting-started'>Getting Started</a><a href='#sidebar-accordion'>Sidebar Accordion</a><a href='#systems-&-data'>Systems &amp; Data</a><a href='#cross-campaign-asset-library'>Cross-Campaign Asset Library</a><a href='#entity-managers'>Entity Managers</a><a href='#detail-windows'>Detail Windows</a><a href='#editor-tools'>Editor Tools</a><a href='#random-tables'>Random Tables</a><a href='#graph-editors'>Graph Editors</a><a href='#campaign-builder'>Campaign Builder</a><a href='#campaign-overview'>Campaign Overview</a><a href='#gm-virtual-table'>GM Virtual Table</a><a href='#gm-screen'>GM Screen</a><a href='#scenario-tools'>Scenario Tools</a><a href='#scene-flow'>Scene Flow</a><a href='#map-tool'>Map Tool</a><a href='#whiteboard'>Whiteboard</a><a href='#world-map'>World Map</a><a href='#exports-&-handouts'>Exports &amp; Handouts</a><a href='#dice-roller'>Dice Roller</a><a href='#audio-&-music'>Audio &amp; Music</a><a href='#books'>Books</a><a href='#web-viewer'>Web Viewer</a><a href='#keyboard-shortcuts'>Keyboard Shortcuts</a><a href='#tips'>Tips</a></nav><div class='container'>"
    ]

    parts.append(section('Getting Started',
        "<ul>"
        "<li>Launch the app: <code>python main_window.py</code>.</li>"
        "<li>Open <b>Data & System &rarr; Change Data Storage</b> to launch the database manager and choose or create a campaign.</li>"
        "<li>Use <b>Switch System</b> (top of the sidebar) to choose the campaign rules system and a visual theme.</li>"
        "<li>Populate PCs, NPCs, Creatures, Places, Objects, Informations, Clues, Maps, and Books.</li>"
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

    parts.append(section('Systems & Data',
        "<p>System selection, backups, and campaign-wide configuration live in the sidebar header and the <b>Data &amp; System</b> accordion.</p>"
        "<ul>"
        "<li><b>Switch System:</b> Pick the active rules system and visual theme; the theme colors update all windows and the PC banner.</li>"
        "<li><b>Manage Campaign Systems:</b> Create, duplicate, and edit systems (default dice formula, supported faces, analyzer config).</li>"
        "<li><b>Change Data Storage:</b> Choose or create campaign database files.</li>"
        "<li><b>Customize Fields</b> and <b>New Entity Type</b>: Tailor entity schemas or define new entity types.</li>"
        "<li><b>Campaign Backups:</b> Create a full archive of the database and assets, or restore from a backup file.</li>"
        "<li><b>Cross-campaign Asset Library:</b> Export/import NPCs, Objects, and Maps with media bundles; optional online gallery publishing.</li>"
        "<li><b>Set SwarmUI Path:</b> Point portrait generation to your SwarmUI install.</li>"
        "</ul>"
    ))
    parts.append(section('Cross-Campaign Asset Library',
        "<p>The Cross-campaign Asset Library is the transfer hub for moving reusable content between campaigns without manually copying database rows or media folders.</p>"
        "<ul>"
        "<li><b>Browse source campaigns:</b> Select a neighboring campaign from the left rail and inspect its NPCs, objects, maps, and other supported entities.</li>"
        "<li><b>Preview before transfer:</b> Each tab shows the selected record's name, summary, and image preview so you can confirm what will be exported or copied.</li>"
        "<li><b>Export bundles:</b> <b>Export Selected…</b> packages chosen records and their media into a portable zip bundle.</li>"
        "<li><b>Copy directly:</b> <b>Copy to Current Campaign</b> imports selected records straight into the active campaign and resolves duplicates interactively.</li>"
        "<li><b>Import bundles:</b> <b>Import Bundle…</b> restores a shared bundle; <b>Import Image Library…</b> limits the import to image-library assets.</li>"
        "<li><b>Online gallery:</b> Publish bundles to GitHub, browse online releases, download shared bundles, or install a full campaign package. Publishing actions require a configured GitHub token.</li>"
        "</ul>"
        + (img('asset_library_overview', 'Cross-campaign Asset Library overview') if shots.get('asset_library_overview') else '')
        + (img('asset_library_maps', 'Cross-campaign Asset Library - maps tab') if shots.get('asset_library_maps') else '')
        + (img('asset_library_online_gallery', 'Online campaign gallery') if shots.get('asset_library_online_gallery') else '')
    ))

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
        "<li><b>Import/Export:</b> Use JSON import/export, the AI Wizard for assisted authoring, or Import Text (Web) for scenarios, creatures, and objects.</li>",
        "<li><b>AI tools:</b> The AI Wizard can generate NPCs, scenarios, and beats with consistency checks; Objects also support AI Categorize for quick classification.</li>",
        "<li><b>Bulk media:</b> Maps can import folders of images; Books can import PDFs or directories of PDFs.</li>",
        "<li><b>Second screen:</b> Display selected fields on a player-facing monitor from the context menu.</li>",
        "</ul>",
        "<p><b>Web text import:</b> Click <i>Import Text (Web)</i> to open the embedded browser, select text on a page, then click Import (or press <code>Ctrl+Shift+I</code>) to open the mapping dialog.</p>",
        clues_html,
        ''.join(img(f"entity_{k}", f"{k.title()} manager") for k in [
            'scenarios', 'pcs', 'npcs', 'creatures', 'factions', 'places', 'objects', 'informations', 'clues', 'maps', 'books'
        ])
    ]
    entity_body = ''.join(part for part in entity_parts if part)
    parts.append(section('Entity Managers', entity_body))

    detail_body = ''.join([
        "<p><b>EntityDetailFactory</b> renders rich detail views used inside the GM Screen and any pop-out detail window. Select a scenario and choose <i>Open in GM Screen</i> (from the scenario list) or open the GM Screen from Utilities, then pick a tab to see the structured layout with collapsible scenes, linked NPC tables, and quick navigation.</p>",
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
        "<p><b>Portrait workflow:</b> Add multiple portraits, set a primary portrait, search the web for images, paste from the clipboard, or generate art via SwarmUI (requires the SwarmUI path in Data &amp; System).</p>",
        img('scenario_editor', 'Generic Editor window'),
        "<p>Use <b>Data & System &rarr; Customize Fields</b> to tailor the schema per entity. The editor below lets you add new fields, set types, and choose linked entities.</p>",
        img('custom_fields_editor', 'Custom Fields Editor')
    ])
    parts.append(section('Editor Tools', editor_body))

    parts.append(section('Random Tables',
        "<p>Create and roll random tables for inspiration or procedural prep. You can open the editor from <b>Relations &amp; Graphs &rarr; Create Random Table</b>, or add a Random Tables panel inside the GM Screen.</p>"
        "<ul>"
        "<li><b>Browse &amp; filter:</b> Filter by category, style, or tag and preview table metadata.</li>"
        "<li><b>Rolls:</b> Roll once or multiple times; results are stored in a running history.</li>"
        "<li><b>Edit &amp; import:</b> Edit tables, import entries from text, or jump to the built-in Plot Twists table.</li>"
        "</ul>"
    ))

    ge_node_html = ''.join(f"<li>{i}</li>" for i in node_items) if node_items else ''
    ge_link_html = ''
    if arrow_items:
        ge_link_html = "<li><b>Arrow Mode submenu:</b> " + ', '.join(arrow_items) + "</li>"
    ge_shape_html = ''.join(f"<li>{i}</li>" for i in shape_items_graph) if shape_items_graph else ''
    parts.append(section('Graph Editors',
        "<p>Visual editors for Characters, Factions, and Scenarios let you map relationships and story beats.</p>"
        "<ul>"
        "<li><b>Add nodes:</b> Use the toolbar actions or double-click (where available) to create a node.</li>"
        "<li><b>Drag to arrange:</b> Left-click and drag nodes to reposition; mouse wheel zooms the canvas.</li>"
        "<li><b>Create links:</b> Select a source node, then a target node, and enter link text when prompted.</li>"
        "</ul>"
        + ("<p><b>Right-click a node for:</b></p><ul>" + ge_node_html + "</ul>" if ge_node_html else "")
        + ("<p><b>Right-click a link for:</b></p><ul>" + ge_link_html + "</ul>" if ge_link_html else "")
        + ("<p><b>Right-click a shape for:</b></p><ul>" + ge_shape_html + "</ul>" if ge_shape_html else "")
        + img('character_graph', 'Character Graph')
        + img('faction_graph', 'Faction Graph') + img('scenario_graph', 'Scenario Graph')
    ))

    parts.append(section('Campaign Builder',
        "<p>The Campaign Builder Wizard is a structured campaign-planning flow for foundation, arc planning, AI-assisted scenario generation, and final review.</p>"
        "<ul>"
        "<li><b>Foundation step:</b> Define campaign identity with name, genre, tone, status, dates, logline, setting, objective, stakes, themes, notes, and optional presets.</li>"
        "<li><b>Arc planner:</b> Build a library of arcs, edit each arc's summary/objective/thread, attach scenarios, and reorder or duplicate arcs.</li>"
        "<li><b>AI operations:</b> Generate arcs from scenarios, generate scenarios per arc, run DB-aware validation, preview forge output, and tune generation defaults.</li>"
        "<li><b>Review &amp; save:</b> Inspect the compiled campaign payload before saving it back into the campaign database.</li>"
        "</ul>"
        + (img('campaign_builder_foundation', 'Campaign Builder - foundation step') if shots.get('campaign_builder_foundation') else '')
        + (img('campaign_builder_arcs', 'Campaign Builder - arcs planner') if shots.get('campaign_builder_arcs') else '')
        + (img('campaign_builder_review', 'Campaign Builder - review step') if shots.get('campaign_builder_review') else '')
    ))

    parts.append(section('Campaign Overview',
        "<p>The campaign overview presents a visual, campaign-facing summary built from arcs, scenarios, linked entities, and briefings. It is useful for reviewing pacing, campaign structure, and scenario dependencies without opening every editor.</p>"
        "<ul>"
        "<li><b>Campaign hero:</b> Review the top-level campaign identity, tone, stakes, and poster-export entry point.</li>"
        "<li><b>Arc navigation:</b> Move across arcs with the stepper and strip while keeping summaries and objectives visible.</li>"
        "<li><b>Scenario focus:</b> Drill into each scenario's hook, objective, stakes, scene count, and link density from the same screen.</li>"
        "<li><b>Entity browser:</b> Open related NPCs, creatures, places, factions, and villains directly from the scenario sidebar.</li>"
        "<li><b>Campaign-facing use:</b> This view is for overview and navigation; detailed live-session prep still lives in the GM Screen and GM Table.</li>"
        "</ul>"
        + (img('campaign_overview', 'Campaign Overview') if shots.get('campaign_overview') else '')
        + (img('campaign_overview_scenario', 'Campaign Overview - scenario focus') if shots.get('campaign_overview_scenario') else '')
    ))

    parts.append(section('GM Virtual Table',
        "<p>The GM Table is the freeform virtual tabletop-style workspace for arranging panels, maps, handouts, and utilities around a single scenario.</p>"
        "<ul>"
        "<li><b>Open:</b> Utilities &rarr; <b>GM Table</b>, then choose a scenario. The default layout opens scenario details and handouts side by side.</li>"
        "<li><b>Toolbar:</b> Use <b>Add Panel</b>, <b>Scene</b>, <b>Map Tool</b>, <b>Player View</b>, <b>Fog</b>, <b>Tile</b>, <b>Cascade</b>, <b>Restore All</b>, <b>Save</b>, and <b>Reset</b> to manage the workspace.</li>"
        "<li><b>Panel types:</b> Add campaign dashboard, world map, map tool, scene flow, whiteboard, random tables, plot twists, image library, handouts, notes, graphs, or entity detail panels.</li>"
        "<li><b>Scenario focus:</b> Layouts persist per scenario, so you can maintain different tabletops for different sessions.</li>"
        "<li><b>Live play:</b> Use the table as the orchestration layer while dedicated tools such as Map Tool and Whiteboard keep their own specialist controls.</li>"
        "</ul>"
        + (img('gm_table_default', 'GM Table - default layout') if shots.get('gm_table_default') else '')
        + (img('gm_table_panels', 'GM Table - expanded panel layout') if shots.get('gm_table_panels') else '')
    ))

    parts.append(section('GM Screen',
        "<p>The GM Screen consolidates scenario prep: select a scenario to open tabs for NPCs, Places, scenes, synopsis, secrets, and notes. Use <code>Ctrl+F</code> for instant search, toggle the PC banner for quick reference, and click any linked entity to open its detail frame.</p>"
        "<ul>"
        "<li><b>PC banner:</b> A one-line, scrollable summary of the party that follows the active theme.</li>"
        "<li><b>Section sidebar:</b> The vertical <b>Sections</b> navigator lets you jump between summary, scenes, synopsis, secrets, notes, and linked-entity views.</li>"
        "<li><b>Panels:</b> Add panels such as Scene Flow, Random Tables, or World Map via the layout manager.</li>"
        "<li><b>Scenario scenes:</b> Scenes can be expanded/collapsed individually and show description, linked entities, maps, and scene-to-scene links.</li>"
        "<li><b>Premium entity cards:</b> NPCs, Places, Creatures, and Villains are displayed as dashboard cards with portraits, chips, and rich text sub-panels.</li>"
        "<li><b>Quick navigation:</b> Collapsible scenes, linked tables, and detail pop-outs keep prep focused.</li>"
        "</ul>"
        + img('gm_screen', 'GM Screen overview')
    ))

    parts.append(section('Scenario Tools',
        "<p>Scenario toolkit for rapid authoring:</p>"
        "<ul>"
        "<li><b>Scenario Builder Wizard:</b> Plan scenes step-by-step, link NPCs/Places/Maps, and preview a scene flow before saving.</li>"
        "<li><b>Scenario Generator:</b> Configure prompts and let the AI draft outline sections you can review and tweak.</li>"
        "<li><b>Scenario Importer:</b> Map headings from external documents into template fields before saving.</li>"
        "<li><b>AI & web import:</b> Use AI helpers and the Web Text Import flow to turn online sources or external text into structured scenario content.</li>"
        "<li><b>PDF Importers:</b> Utilities include Creature and Equipment importers that extract entries from PDFs with a review step.</li>"
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

        "<li><b>Drawing tools:</b> Switch between Token, Rectangle, and Oval modes to sketch zones, spell areas, or light auras with filled/outline styles; add editable text labels and tweak drawing colours.</li>"

        "<li><b>Background rotation:</b> Rotate the map image from the toolbar; rotation is saved with the background for consistent sharing/exports.</li>"

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

    parts.append(section('Whiteboard',
        "<p>The Whiteboard gives you a synchronized canvas for prep and live collaboration. Use it in the GM view, pop a player view to a second screen, or share a web link/QR code.</p>"
        "<ul>"
        "<li><b>Tools:</b> Pen, eraser, stamps, and editable text (double-click to edit); pick colours, sizes, and layers.</li>"
        "<li><b>Layers & grid:</b> Toggle shared/GM layers, enable grid overlay, and snap strokes or stamps to the grid.</li>"
        "<li><b>Pan & zoom:</b> Middle-drag to pan, mouse wheel to zoom; the canvas extends infinitely.</li>"
        "<li><b>Save/load:</b> Whiteboard states are stored in the database with autosave; load previous boards instantly.</li>"
        "<li><b>Player view:</b> Open a fullscreen view on another monitor or share via QR/link for remote collaboration.</li>"
        "</ul>"
        + (img('whiteboard', 'Whiteboard') if shots.get('whiteboard') else '')
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

    parts.append(section('Exports & Handouts',
        "<p>GMCampaignDesigner includes multiple output paths for preparing material for players, collaborators, or VTT use.</p>"
        "<ul>"
        "<li><b>Export Scenarios:</b> Generate shareable scenario documents from selected records.</li>"
        "<li><b>Campaign Dossier:</b> Assemble a broader export package covering scenario and campaign context for prep or sharing.</li>"
        "<li><b>Session Brief export:</b> Produce a focused session-ready summary for quick table use.</li>"
        "<li><b>Export for Foundry:</b> Convert campaign content into a Foundry-friendly format.</li>"
        "<li><b>Newsletters & handouts:</b> Build in-world newsletter-style outputs and other player-facing handouts.</li>"
        "</ul>"
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

    parts.append(section('Web Viewer',
        "<p>The project includes a lightweight web server for remote viewing and collaboration.</p>"
        "<ul>"
        "<li><b>Start:</b> Run <code>python -m modules.web.GM_webviewer</code> (or <code>start_webserver.sh</code> on Linux/macOS).</li>"
        "<li><b>Login:</b> Register an account, then browse NPCs, Places, Factions, News, Journals, and Clues.</li>"
        "<li><b>Clues board:</b> Drag clues, create links, and save positions.</li>"
        "<li><b>Media:</b> Portraits and uploaded assets are served from the active campaign.</li>"
        "</ul>"
    ))

    parts.append(section('Keyboard Shortcuts',
        "<ul>"
        "<li><b>F1</b>: Open GM Screen.</li>"
        "<li><b>F2</b>: Open Map Tool.</li>"
        "<li><b>F3</b>: Open Whiteboard.</li>"
        "<li><b>F4</b>: Open Scenario Builder Wizard.</li>"
        "<li><b>F5</b>: Open World Map.</li>"
        "<li><b>F6</b>: Change Data Storage.</li>"
        "<li><b>F7</b>: Open Sound &amp; Music Manager.</li>"
        "<li><b>F8</b>: Open Dice Roller.</li>"
        "<li><b>F9</b>: Open Campaign Builder.</li>"
        "<li><b>F12</b>: Exit the app.</li>"
        "<li><b>Ctrl+F</b>: Search inside the GM Screen.</li>"
        "<li><b>Ctrl+Shift+I</b>: Send selected text from the Web Text Import browser.</li>"
        "</ul>"
    ))
    parts.append(section('Tips',
        "<div class='tip'><b>Documentation refresh:</b> Run <code>python scripts/generate_docs.py</code> from the repository root after UI, menu, screenshot, or API changes. It refreshes <code>docs/index.html</code>, this manual, and <code>docs/images/</code>.</div>"
        "<div class='tip'><b>Exports:</b> Use <i>Export Scenarios</i>, <i>Campaign Dossier</i>, <i>Session Brief</i>, or <i>Export for Foundry</i> depending on the audience.</div>"
        "<div class='tip'><b>Portrait workflow:</b> Generate or link portraits from the Utilities section; double-click a portrait in any list to pop it out.</div>"
        "<div class='tip'><b>Cross-campaign reuse:</b> Use the Cross-campaign Asset Library to move NPCs, objects, and maps between campaigns with their media.</div>"
        "<div class='tip'><b>AI settings:</b> Configure the local AI endpoint in <code>config/config.ini</code> under the <code>[AI]</code> section.</div>"
        "<div class='tip'><b>Auto-improvement:</b> Configure the Codex CLI integration in <code>config/config.ini</code> under <code>[AutoImprove]</code> before using automated improvement workflows.</div>"
        "<div class='tip'><b>Logging:</b> Enable logs in <code>config/config.ini</code> to troubleshoot AI imports and automated workflows.</div>"
    ))

    parts.append("</div></body></html>")
    return ''.join(parts)



if __name__ == "__main__":
    main()
