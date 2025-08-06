import os
import re
import json
import logging
import platform
import html

from flask import (
    Flask, jsonify, render_template, request,
    send_from_directory, redirect, url_for,
    current_app, Blueprint, flash
)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin,
    login_user, login_required,
    logout_user, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

import bleach
from datetime import datetime
from sqlalchemy.orm import joinedload

from modules.helpers.config_helper import ConfigHelper
from modules.generic.generic_model_wrapper import GenericModelWrapper
from modules.helpers.text_helpers import format_multiline_text, rtf_to_html

# ──────────────────────────────────────────────────────────────────────────────
# Set up logging
# ──────────────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

app = Flask(__name__)
# register a Jinja filter so you can do {{ entry.attachments|loads }}
app.jinja_env.filters['loads'] = json.loads

# ──────────────────────────────────────────────────────────────────────────────
# Paths & DB Name
# ──────────────────────────────────────────────────────────────────────────────
raw_db_path = ConfigHelper.get("Database", "path", fallback="default_campaign.db").strip()
is_windows_style_path = re.match(r"^[a-zA-Z]:[\\/]", raw_db_path)
if platform.system() != "Windows" and is_windows_style_path:
    drive_letter = raw_db_path[0].upper()
    subpath = raw_db_path[2:].lstrip("/\\").replace("\\", "/")
    if subpath.lower().startswith("synologydrive/"):
        subpath = subpath[len("synologydrive/"):]
    synology_base = "/volume1/homes/llankar/Drive"
    DB_PATH = os.path.join(synology_base, subpath)
else:
    DB_PATH = raw_db_path if os.path.exists(raw_db_path) else os.path.abspath(os.path.normpath(raw_db_path))

DB_NAME = os.path.basename(DB_PATH).replace(".db", "")

# ──────────────────────────────────────────────────────────────────────────────
# Flask Config for SQLAlchemy and Auth
# ──────────────────────────────────────────────────────────────────────────────
app.config['SECRET_KEY'] = 'your-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{DB_PATH}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'auth.login'

# ──────────────────────────────────────────────────────────────────────────────
# Models
# ──────────────────────────────────────────────────────────────────────────────
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)

class JournalEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    tags = db.Column(db.String(200), nullable=True)  # comma-separated tags
    attachments = db.Column(db.Text, nullable=True)  # JSON-encoded list of filenames
    user = db.relationship('User', backref='journal_entries')

# ──────────────────────────────────────────────────────────────────────────────
# Authentication Blueprint
# ──────────────────────────────────────────────────────────────────────────────
auth_bp = Blueprint('auth', __name__)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('welcome'))
        flash('Invalid credentials', 'danger')
    return render_template('login.html')
@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username','').strip()
        password = request.form.get('password','')
        password2 = request.form.get('password2','')

        # Simple validation
        if not username or not password:
            flash('Username and password are required', 'danger')
            return redirect(url_for('auth.register'))
        if password != password2:
            flash('Passwords do not match', 'danger')
            return redirect(url_for('auth.register'))
        if User.query.filter_by(username=username).first():
            flash('Username already taken', 'danger')
            return redirect(url_for('auth.register'))

        # Create & log in new user
        pw_hash = generate_password_hash(password)
        user = User(username=username, password_hash=pw_hash)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        return redirect(url_for('welcome'))

    return render_template('register.html')
@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))

app.register_blueprint(auth_bp)

# ──────────────────────────────────────────────────────────────────────────────
# Journal Blueprint
# ──────────────────────────────────────────────────────────────────────────────
journal_bp = Blueprint('journal', __name__, url_prefix='/journals')

@journal_bp.route('/', methods=['GET'])
@login_required
def list_entries():
    # eager‐load .user to avoid extra queries
    entries = (JournalEntry.query
            .options(joinedload(JournalEntry.user))
            .order_by(JournalEntry.created_at.desc())
            .all())
    return render_template('journals.html', entries=entries)
@journal_bp.route('/<int:entry_id>', methods=['GET'])
@login_required
def view_entry(entry_id):
    # Fetch any entry by its ID (no user_id check)
    entry = JournalEntry.query.get_or_404(entry_id)
    return render_template('journal_view.html', entry=entry)

@journal_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new_entry():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        raw_content = request.form.get('content', '').strip()
        # option A: use set union
        allowed_tags = bleach.sanitizer.ALLOWED_TAGS.union({'p','h1','h2','br'})
        content = bleach.clean(
            raw_content,
            tags=allowed_tags,
            attributes={'a': ['href', 'title']},
            strip=True
        )
        tags = request.form.get('tags', '').strip()
        # handle attachments
        files = request.files.getlist('attachments')
        saved = []
        for f in files:
            if f and f.filename:
                fn = secure_filename(f.filename)
                path = os.path.join(app.config['UPLOAD_FOLDER'], fn)
                f.save(path)
                saved.append(fn)
        entry = JournalEntry(
            user_id=current_user.id,
            title=title,
            content=content,
            tags=tags
        )
        attachments=json.dumps(saved)
        db.session.add(entry)
        db.session.commit()
        return redirect(url_for('journal.list_entries'))
    return render_template('journal_edit.html', entry=None)

@journal_bp.route('/edit/<int:entry_id>', methods=['GET', 'POST'])
@login_required
def edit_entry(entry_id):
    entry = JournalEntry.query.get_or_404(entry_id)
    if entry.user_id != current_user.id:
        return redirect(url_for('journal.list_entries'))
    if request.method == 'POST':
        entry.title = request.form.get('title', '').strip()
        raw_content = request.form.get('content', '').strip()
        # option A: use set union
        allowed_tags = bleach.sanitizer.ALLOWED_TAGS.union({'p','h1','h2','br'})
        entry.content = bleach.clean(
            raw_content,
            tags=allowed_tags,
            attributes={'a': ['href', 'title']},
            strip=True)
        entry.tags = request.form.get('tags', '').strip()
        # append new attachments
        existing = json.loads(entry.attachments or '[]')
        for f in request.files.getlist('attachments'):
            if f and f.filename:
                fn = secure_filename(f.filename)
                f.save(os.path.join(app.config['UPLOAD_FOLDER'], fn))
                existing.append(fn)
        entry.attachments = json.dumps(existing)
        db.session.commit()
        return redirect(url_for('journal.view_entry', entry_id=entry.id))
    return render_template('journal_edit.html', entry=entry)

@journal_bp.route('/delete/<int:entry_id>', methods=['POST'])
@login_required
def delete_entry(entry_id):
    entry = JournalEntry.query.get_or_404(entry_id)
    if entry.user_id == current_user.id:
        db.session.delete(entry)
        db.session.commit()
    return redirect(url_for('journal.list_entries'))

app.register_blueprint(journal_bp)

# ──────────────────────────────────────────────────────────────────────────────
# Directories for assets
# ──────────────────────────────────────────────────────────────────────────────
CURRENT_DIR    = os.path.dirname(__file__)
BASE_DIR       = os.path.dirname(DB_PATH)
GRAPH_DIR      = os.path.join(BASE_DIR, "assets", "graphs")
PORTRAITS_DIR  = os.path.join(BASE_DIR, "assets", "portraits")
FALLBACK_PORTRAIT = "/assets/images/fallback.png"
UPLOAD_FOLDER  = os.path.join(BASE_DIR, "assets", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

logging.debug("DB_PATH: %s", DB_PATH)
logging.debug("GRAPH_DIR: %s", GRAPH_DIR)
logging.debug("PORTRAITS_DIR: %s", PORTRAITS_DIR)

# ──────────────────────────────────────────────────────────────────────────────
# Shared positions JSON file (for clues)
# ──────────────────────────────────────────────────────────────────────────────
POSITIONS_FILE = os.path.join(BASE_DIR, "data", "save", "clue_positions.json")
LINKS_FILE     = os.path.join(BASE_DIR, "data", "save", "clue_links.json")

def load_links():
    try:
        with open(LINKS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_links_list(links_list):
    os.makedirs(os.path.dirname(LINKS_FILE), exist_ok=True)
    with open(LINKS_FILE, "w", encoding="utf-8") as f:
        json.dump(links_list, f, indent=2)

def save_link(link):
    links = load_links()
    links.append(link)
    os.makedirs(os.path.dirname(LINKS_FILE), exist_ok=True)
    with open(LINKS_FILE, "w", encoding="utf-8") as f:
        json.dump(links, f, indent=2)

@app.route('/api/clue-link-delete', methods=['POST'])
def delete_clue_link():
    data = request.get_json() or {}
    idx = data.get("index")
    if idx is None:
        return jsonify(error="Missing index"), 400
    links = load_links()
    try:
        idx = int(idx)
        if 0 <= idx < len(links):
            links.pop(idx)
            save_links_list(links)
            return jsonify(success=True)
    except (ValueError, TypeError):
        pass
    return jsonify(error="Invalid index"), 404

@app.route('/api/clue-delete', methods=['POST'])
def delete_clue():
    data = request.get_json() or {}
    name = data.get("name", "").strip()
    if not name:
        return jsonify(error="Missing clue name"), 400

    wrapper = GenericModelWrapper("clues")
    items = wrapper.load_items()

    removed_ids = [str(i) for i, c in enumerate(items)
                if c.get("Name", "").strip() == name]
    if not removed_ids:
        return jsonify(error="Clue not found"), 404

    new_items = [c for c in items if c.get("Name", "").strip() != name]
    wrapper.save_items(new_items)

    links = load_links()
    filtered_links = [
        l for l in links
        if l.get("from") not in removed_ids and l.get("to") not in removed_ids
    ]
    save_links_list(filtered_links)

    return jsonify(success=True)

def load_positions():
    try:
        with open(POSITIONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_positions(positions):
    os.makedirs(os.path.dirname(POSITIONS_FILE), exist_ok=True)
    with open(POSITIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(positions, f, indent=2)

# ──────────────────────────────────────────────────────────────────────────────
# Data loaders
# ──────────────────────────────────────────────────────────────────────────────
def get_graph_list():
    try:
        files = [f for f in os.listdir(GRAPH_DIR+"/npcs/") if f.lower().endswith(".json")]
        logging.debug("Found graph files: %s", files)
        return files
    except Exception as e:
        logging.error("Error listing graph files: %s", e)
        return []

def get_portrait_mapping():
    mapping = {}
    try:
        npc_wrapper = GenericModelWrapper("npcs")
        for npc in npc_wrapper.load_items():
            name = npc.get("Name","").strip()
            portrait = npc.get("Portrait","").strip()
            if name and portrait:
                mapping[name] = portrait
                logging.debug("Mapping NPC portrait: %s -> %s", name, portrait)
    except Exception as e:
        logging.error("Error loading NPCs: %s", e)
    return mapping

def get_places_list():
    try:
        wrapper = GenericModelWrapper("places")
        filtered = []
        for p in wrapper.load_items():
            if p.get("PlayerDisplay") in (True,"True","true",1,"1"):
                p["DisplayDescription"] = format_multiline_text(p.get("Description","")) if p.get("Description") else ""
                portrait = str(p.get("Portrait") or "").strip()
                if portrait:
                    portrait = portrait.replace("\\","/").lstrip("/")
                    p["PortraitURL"] = f"/portraits/{os.path.basename(portrait)}"
                else:
                    p["PortraitURL"] = None
                filtered.append(p)
        logging.debug("Filtered places for display: %d", len(filtered))
        return filtered
    except Exception as e:
        logging.error("Error loading places: %s", e)
        return []

def get_informations_list():
    try:
        wrapper = GenericModelWrapper("informations")
        filtered = []
        for info in wrapper.load_items():
            if info.get("PlayerDisplay") in (True,"True","true",1,"1"):
                info["DisplayInformation"] = format_multiline_text(info.get("Information",""))
                info["DisplayLevel"]       = format_multiline_text(info.get("Level",""))
                filtered.append(info)
        logging.debug("Filtered informations: %d", len(filtered))
        return filtered
    except Exception as e:
        logging.error("Error loading informations: %s", e)
        return []

def get_clues_list():
    wrapper = GenericModelWrapper("clues")
    filtered = []
    for clue in wrapper.load_items():
        if clue.get("PlayerDisplay") in (True,"True","true",1,"1"):
            desc = clue.get("Description", "")
            # if it's RTF‐JSON, convert to HTML; else just escape lines
            if isinstance(desc, dict) and "text" in desc:
                clue["DisplayDescription"] = rtf_to_html(desc)
            else:
                # fallback: plain text with linebreaks
                text = str(desc).replace("\n", "<br>")
                clue["DisplayDescription"] = html.escape(text)
            portrait = str(clue.get("Portrait") or "").strip()
            if portrait:
                portrait = portrait.replace("\\","/").lstrip("/")
                clue["PortraitURL"] = f"/portraits/{os.path.basename(portrait)}"
            else:
                clue["PortraitURL"] = None

            filtered.append(clue)
    return filtered

# ──────────────────────────────────────────────────────────────────────────────
# Routes
# ──────────────────────────────────────────────────────────────────────────────
@app.route('/')
def default():
    return redirect(url_for('welcome'))

@app.route('/welcome')
def welcome():
    # look for a matching background
    two_up = os.path.dirname( os.path.dirname(CURRENT_DIR) )
    asset_dir = os.path.join(two_up,"assets", "images", "backgrounds")
    fname = f"background.png"
    if os.path.exists(os.path.join(asset_dir, fname)):
        bg_path = asset_dir+"/"+fname
    else:
        bg_path = asset_dir+fname+f"/default_campaign.png"

    return render_template(
        'welcome.html',
        db_name=DB_NAME,
        bg_image=bg_path
    )
@app.route('/npc')
def npc_view():
    selected = request.args.get("graph")
    if selected:
        title = os.path.splitext(selected)[0]
        return render_template('npcs.html',
                            page_title=title,
                            selected_graph=selected)
    else:
        return render_template('npc_list.html',
                            graph_files=get_graph_list())

@app.route('/locations')
def locations_view():
    return render_template('locations.html',
                        places=get_places_list(),
                        db_name=DB_NAME)

@app.route('/news')
def news_view():
    return render_template('news_board.html',
                        informations=get_informations_list(),
                        db_name=DB_NAME)

@app.route('/clues')
def clues_view():
    links = [
        {"from":"0","to":"2","text":"leads to","color":"#d6336c"},
        {"from":"2","to":"5","text":"related","color":"#198754"},
        {"from":"5","to":"0","text":"contains","color":"#0d6efd"},
    ]
    return render_template('clues.html',
                        clues=get_clues_list(),
                        links=links,
                        db_name=DB_NAME)

@app.route('/api/clue-links', methods=['GET'])
def get_clue_links():
    return jsonify(load_links())

@app.route('/api/clue-link', methods=['POST'])
def add_clue_link():
    link = request.get_json()
    save_link(link)
    return ('', 204)

@app.route('/api/npc-graph')
def npc_graph():
    graph_file = request.args.get("graph")
    if not graph_file:
        return jsonify(error="No graph specified"), 400
    path = os.path.join(GRAPH_DIR+"/npcs/", graph_file)
    if not os.path.exists(path):
        return jsonify(error="Graph file not found"), 404
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    portrait_map = get_portrait_mapping()
    npcs = []
    try:
        npcs = GenericModelWrapper("npcs").load_items()
    except:
        pass
    for node in data.get("nodes", []):
        name = node.get("npc_name","")
        src = portrait_map.get(name,"").strip()
        node["portrait"] = os.path.basename(src) if src else FALLBACK_PORTRAIT
        match = next((n for n in npcs if n.get("Name","").strip() == name), None)
        node["background"] = format_multiline_text(match.get("Background","")) if match else "(No background)"
    return jsonify(data)

@app.route('/api/clue-positions', methods=['GET'])
def get_clue_positions():
    return jsonify(load_positions())

@app.route('/api/clue-position', methods=['POST'])
def set_clue_position():
    data = request.get_json() or {}
    cid = str(data.get("id"))
    x = data.get("x")
    y = data.get("y")
    if cid is None or x is None or y is None:
        return jsonify(error="Missing id, x, or y"), 400
    positions = load_positions()
    positions[cid] = {"x": float(x), "y": float(y)}
    save_positions(positions)
    return jsonify(success=True)

@app.route("/portraits/<path:filename>")
def get_portrait(filename):
    return send_from_directory(PORTRAITS_DIR, filename)

@app.route("/assets/<path:filename>")
def get_asset(filename):
    two_up = os.path.dirname( os.path.dirname(CURRENT_DIR) )
    asset_dir = os.path.join(two_up,"assets", "images")
   
    return send_from_directory(asset_dir, filename)

@app.route("/assets/css/<path:filename>")
def get_css(filename):
        # climb two levels up from CURRENT_DIR, then into “assets/css”
        two_up = os.path.dirname(os.path.dirname(CURRENT_DIR))
        css_dir = os.path.join(two_up, "assets", "css")
        return send_from_directory(css_dir, filename)

@app.route('/api/clue-positions', methods=['POST'])
def set_all_clue_positions():
    positions = request.get_json() or {}
    save_positions(positions)
    return jsonify(success=True)

@app.route('/uploads/informations/<path:filename>')
def information_upload(filename):
    return send_from_directory(
        app.config['UPLOAD_FOLDER'],
        filename,
        as_attachment=True
    )
@app.route('/uploads/clues/<path:filename>')
def clue_upload(filename):
    return send_from_directory(
        app.config['UPLOAD_FOLDER'],
        filename,
        as_attachment=True
    )
@app.route('/informations/add', methods=['GET', 'POST'])
def add_information():
    if request.method == 'POST':
        title = request.form.get('Title', '').strip()
        info_txt = request.form.get('Information', '').strip()
        level = request.form.get('Level', '').strip()
        display = bool(request.form.get('PlayerDisplay'))
        npcs = request.form.getlist('NPCs')

        attachment = request.files.get('Attachment')
        filename = ""
        if attachment and attachment.filename:
            filename = attachment.filename
            save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            attachment.save(save_path)

        wrapper = GenericModelWrapper("informations")
        items = wrapper.load_items()
        items.append({
            "Title": title,
            "Information": info_txt,
            "Level": level,
            "PlayerDisplay": display,
            "NPCs": npcs,
            "Attachment": filename
        })
        wrapper.save_items(items)
        return redirect(url_for('news_view'))

    return render_template('add_information.html')

@app.route('/factions')
def factions_view():
    selected = request.args.get("graph")
    if selected:
        title = os.path.splitext(selected)[0]
        return render_template('factions.html',
                            page_title=title,
                            selected_graph=selected)
    else:
        try:
            files = [
                f for f in os.listdir(GRAPH_DIR+"/factions/")
                if f.lower().endswith('.json')
            ]
        except Exception:
            files = []
        return render_template('faction_list.html',
                            graph_files=files)

@app.route('/api/faction-graph')
def faction_graph():
    graph_file = request.args.get("graph")
    if not graph_file:
        return jsonify(error="No graph specified"), 400
    path = os.path.join(GRAPH_DIR+"/factions/", graph_file)
    if not os.path.exists(path):
        return jsonify(error="Graph file not found"), 404
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    for node in data.get("nodes", []):
        node["portrait"] = FALLBACK_PORTRAIT
        node["background"] = node.get("description", "(No description)")
    return jsonify(data)


@app.route('/clues/add', methods=['GET','POST'])
def add_clue():
    wrapper = GenericModelWrapper("clues")
    if request.method == 'POST':
        # parse the RTF-JSON
        desc = json.loads(request.form['Description'])
        items = wrapper.load_items()
        items.append({
        "Name":          request.form['Name'].strip(),
        "Type":          request.form['Type'].strip(),
        "Description":   desc,
        "PlayerDisplay": bool(request.form.get('PlayerDisplay'))
        })
        wrapper.save_items(items)
        return redirect(url_for('clues_view'))

    return render_template('clue_form.html', clue=None)


@app.route('/clues/edit/<int:idx>', methods=['GET','POST'])
def edit_clue(idx):
    wrapper = GenericModelWrapper("clues")
    items   = wrapper.load_items()
    if idx < 0 or idx >= len(items):
        return redirect(url_for('clues_view'))

    if request.method == 'POST':
        # parse the RTF-JSON
        desc = json.loads(request.form['Description'])
        items[idx] = {
        "Name":          request.form['Name'].strip(),
        "Type":          request.form['Type'].strip(),
        "Description":   desc,
        "PlayerDisplay": bool(request.form.get('PlayerDisplay'))
        }
        wrapper.save_items(items)
        return redirect(url_for('clues_view'))

    # GET: just hand the existing dict back into your form
    return render_template('clue_form.html', clue=items[idx])
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    port = int(ConfigHelper.get('WebServer', 'web_port', fallback=31000))
    app.run(host='0.0.0.0', port=port, debug=True)
