import io
import logging
import threading
import time
from pathlib import Path

from flask import Flask, Response, jsonify, render_template_string, request, send_from_directory
from werkzeug.serving import make_server
from PIL import Image, ImageDraw
from modules.helpers.config_helper import ConfigHelper
from modules.helpers.logging_helper import log_module_import
from modules.whiteboard.utils.remote_access_guard import RemoteAccessGuard
from modules.maps.utils.text_items import TextFontCache
from modules.maps.views.web_map_api import register_map_api
from modules.scenarios.plot_twist_panel import get_latest_plot_twist, roll_plot_twist

log_module_import(__name__)

# Simple Flask app to serve the current map image

def open_web_display(self, port=None):
    if port is None:
        port = int(ConfigHelper.get("MapServer", "map_port", fallback=32000))
    if getattr(self, '_web_server_thread', None):
        return  # already running
    static_dir = Path(__file__).resolve().parents[3] / "static"
    self._web_app = Flask(
        __name__,
        static_folder=str(static_dir),
        static_url_path="/static",
    )
    _favicon_path = static_dir / "favicon.ico"
    self._web_port = port
    try:
        map_token_raw = str(ConfigHelper.get("MapServer", "gm_token", fallback="") or "")
    except Exception:
        map_token_raw = ""
    try:
        edit_enabled_raw = str(ConfigHelper.get("MapServer", "remote_edit_enabled", fallback="0") or "")
        edit_enabled = edit_enabled_raw.strip().lower() in ("1", "true", "yes", "on")
    except Exception:
        edit_enabled = False
    self._map_remote_access_guard = RemoteAccessGuard(
        enabled=edit_enabled,
        token=map_token_raw,
    )

    controller = self
    # Polling interval for clients, in milliseconds (lower = smoother, higher = less CPU)
    try:
        self._web_refresh_ms = int(ConfigHelper.get("MapServer", "map_refresh_ms", fallback=200))
    except Exception:
        self._web_refresh_ms = 200
    # Whether to use MJPEG streaming instead of polling PNGs
    try:
        use_mjpeg_raw = str(ConfigHelper.get("MapServer", "use_mjpeg", fallback="1") or "")
        self._web_use_mjpeg = use_mjpeg_raw.strip().lower() in ("1", "true", "yes", "y", "on")
    except Exception:
        self._web_use_mjpeg = True

    register_map_api(self._web_app, controller=self, access_guard=self._map_remote_access_guard)

    def _plot_twist_payload(result):
        if not result:
            return {"has_result": False}
        payload = result.to_payload()
        payload["has_result"] = True
        return payload

    @self._web_app.route('/plot_twist')
    def plot_twist():
        return jsonify(_plot_twist_payload(get_latest_plot_twist()))

    @self._web_app.route('/plot_twist/roll', methods=['POST'])
    def plot_twist_roll():
        return jsonify(_plot_twist_payload(roll_plot_twist()))

    @self._web_app.route('/')
    def index():
        # Basic HTML page that reloads the map image periodically so
        # changes on the GM side appear without requiring a manual refresh.
        use_mjpeg = bool(getattr(controller, '_web_use_mjpeg', True))
        img_src = '/stream.mjpg' if use_mjpeg else '/map.png?ts=0'
        refresh_script = "" if use_mjpeg else f"""
        <script>
            document.addEventListener('DOMContentLoaded', () => {{
                const REFRESH_MS = {int(getattr(controller, '_web_refresh_ms', 200))};
                const img = document.getElementById('mapImage');
                function scheduleNext() {{ setTimeout(reloadImage, REFRESH_MS); }}
                function reloadImage() {{ img.src = '/map.png?ts=' + Date.now(); }}
                img.onload = scheduleNext;
                img.onerror = scheduleNext;
                setTimeout(reloadImage, REFRESH_MS);
            }});
        </script>
        """
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
        <meta charset='utf-8'>
        <title>Map Display</title>
        <style>
            body {{ margin: 0; font-family: 'Segoe UI', Tahoma, sans-serif; background: #0b1220; }}
            img {{ max-width: 100%; height: auto; display: block; }}
            #plotTwistPopup {{
                position: fixed;
                top: 16px;
                right: 16px;
                width: min(340px, calc(100% - 32px));
                background: rgba(15, 23, 42, 0.92);
                color: #e2e8f0;
                border-radius: 12px;
                box-shadow: 0 16px 30px rgba(0, 0, 0, 0.35);
                padding: 14px 16px;
                z-index: 100;
            }}
            #plotTwistPopup h2 {{
                margin: 0 0 8px 0;
                font-size: 16px;
            }}
            #plotTwistResult {{
                font-size: 14px;
                line-height: 1.4;
                margin-bottom: 8px;
            }}
            #plotTwistMeta {{
                font-size: 12px;
                color: #94a3b8;
                margin-bottom: 10px;
            }}
            #plotTwistButton {{
                background: #38bdf8;
                border: none;
                color: #0f172a;
                padding: 6px 12px;
                border-radius: 8px;
                font-weight: 700;
                cursor: pointer;
            }}
            #plotTwistButton:active {{
                transform: translateY(1px);
            }}
        </style>
        {refresh_script}
        </head>
        <body>
        <div id="plotTwistPopup">
            <h2>Plot Twist</h2>
            <div id="plotTwistResult">Loading latest twist…</div>
            <div id="plotTwistMeta"></div>
            <button id="plotTwistButton" type="button">Roll another</button>
        </div>
        <img id='mapImage' src='{img_src}'>
        <script>
            const plotTwistResult = document.getElementById('plotTwistResult');
            const plotTwistMeta = document.getElementById('plotTwistMeta');
            const plotTwistButton = document.getElementById('plotTwistButton');

            function renderPlotTwist(data) {{
                if (!data || !data.has_result) {{
                    plotTwistResult.textContent = 'No plot twist rolled yet.';
                    plotTwistMeta.textContent = '';
                    return;
                }}
                plotTwistResult.textContent = data.result || 'No plot twist rolled yet.';
                const table = data.table ? `${{data.table}}` : 'Plot Twist';
                const roll = data.roll !== undefined ? `Roll ${{data.roll}}` : 'Roll ?';
                const stamp = data.timestamp ? data.timestamp : '';
                plotTwistMeta.textContent = `${{table}} · ${{roll}} · ${{stamp}}`;
            }}

            async function fetchPlotTwist() {{
                try {{
                    const response = await fetch('/plot_twist');
                    if (!response.ok) return;
                    const data = await response.json();
                    renderPlotTwist(data);
                }} catch (err) {{
                    plotTwistResult.textContent = 'Unable to load plot twist.';
                }}
            }}

            async function rollPlotTwist() {{
                try {{
                    const response = await fetch('/plot_twist/roll', {{ method: 'POST' }});
                    if (!response.ok) return;
                    const data = await response.json();
                    renderPlotTwist(data);
                }} catch (err) {{
                    plotTwistResult.textContent = 'Unable to roll a plot twist.';
                }}
            }}

            plotTwistButton.addEventListener('click', rollPlotTwist);
            fetchPlotTwist();
            setInterval(fetchPlotTwist, 30000);
        </script>
        </body>
        </html>
        """

    @self._web_app.route('/favicon.ico')
    def favicon():
        if _favicon_path.exists():
            return send_from_directory(static_dir, 'favicon.ico')
        return ('', 204)

    @self._web_app.route('/player')
    def player():
        token_param = request.args.get('token', '')
        return render_template_string(
            """
            <!DOCTYPE html>
            <html lang='en'>
            <head>
                <meta charset='utf-8'>
                <meta name='viewport' content='width=device-width, initial-scale=1'>
                <title>Remote Map</title>
                <link rel="preload" href="{{ script_path }}" as="script">
                <style>
                    html, body { margin: 0; padding: 0; height: 100%; }
                    body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', Tahoma, sans-serif; }
                    #mapStage { position: relative; width: 100%; height: 100%; overflow: hidden; user-select: none; }
                    #mapImage { width: 100%; height: 100%; object-fit: contain; background: #0b1220; pointer-events: none; user-select: none; -webkit-user-drag: none; }
                    #tokenLayer { position: absolute; inset: 0; pointer-events: auto; user-select: none; }
                    .token { position: absolute; width: 48px; height: 48px; border-radius: 12px; background: rgba(14,165,233,0.85); border: 2px solid rgba(255,255,255,0.8); color: #0b1220; font-weight: 800; display: grid; place-items: center; pointer-events: auto; touch-action: none; box-shadow: 0 10px 25px rgba(0,0,0,0.35); user-select: none; -webkit-user-drag: none; }
                    #drawLayer { position: absolute; inset: 0; pointer-events: auto; touch-action: none; }
                    #status { position: fixed; bottom: 12px; left: 12px; padding: 10px 12px; background: rgba(15,23,42,0.9); border-radius: 10px; box-shadow: 0 10px 25px rgba(0,0,0,0.35); font-weight: 700; }
                    #plotTwistPopup { position: fixed; top: 12px; right: 12px; width: min(340px, calc(100% - 24px)); background: rgba(15, 23, 42, 0.92); color: #e2e8f0; border-radius: 12px; box-shadow: 0 16px 30px rgba(0, 0, 0, 0.35); padding: 14px 16px; z-index: 200; }
                    #plotTwistPopup h2 { margin: 0 0 8px 0; font-size: 16px; }
                    #plotTwistResult { font-size: 14px; line-height: 1.4; margin-bottom: 8px; }
                    #plotTwistMeta { font-size: 12px; color: #94a3b8; margin-bottom: 10px; }
                    #plotTwistButton { background: #38bdf8; border: none; color: #0f172a; padding: 6px 12px; border-radius: 8px; font-weight: 700; cursor: pointer; }
                    #plotTwistButton:active { transform: translateY(1px); }
                </style>
            </head>
            <body>
                <div id="plotTwistPopup">
                    <h2>Plot Twist</h2>
                    <div id="plotTwistResult">Loading latest twist…</div>
                    <div id="plotTwistMeta"></div>
                    <button id="plotTwistButton" type="button">Roll a twist</button>
                </div>
                <div id='mapStage'>
                    <img id='mapImage' src='/map.png' alt='Map' draggable='false'>
                    <canvas id='drawLayer'></canvas>
                    <div id='tokenLayer'></div>
                    <div id='status'>Connecting…</div>
                </div>
                <script>
                    window.MAP_REMOTE_TOKEN = {{ token|tojson }};
                </script>
                <script src='{{ script_path }}' defer></script>
                <script src='/static/maptool_web/plot_twist.js' defer></script>
            </body>
            </html>
            """,
            token=token_param,
            script_path='/static/maptool_web/player.js'
        )

    @self._web_app.route('/map.png')
    def map_png():
        # Rebuild the composited image for each request so movement and fog
        # changes are reflected immediately.
        controller._update_web_display_map()
        data = getattr(controller, '_web_image_bytes', None)
        if not data:
            return ('No map image', 404)
        return Response(
            data,
            mimetype='image/png',
            headers={
                'Cache-Control': 'no-cache, no-store, must-revalidate',
                'Pragma': 'no-cache',
                'Expires': '0',
            },
        )

    @self._web_app.route('/stream.mjpg')
    def stream_mjpeg():
        boundary = 'frame'
        interval = max(1, int(getattr(controller, '_web_refresh_ms', 200))) / 1000.0

        def _ensure_rgb(img):
            if img is None:
                return None
            if img.mode == 'RGB':
                return img
            try:
                return img.convert('RGB')
            except Exception:
                pass
            try:
                # Normalize to RGBA first so exotic modes (e.g. RGBA;16B) can be flattened.
                rgba = img.convert('RGBA')
                alpha = rgba.getchannel('A')
                opaque = Image.new('RGB', rgba.size, (0, 0, 0))
                opaque.paste(rgba.convert('RGB'), mask=alpha)
                return opaque
            except Exception:
                logging.getLogger(__name__).exception("Failed to convert map image to RGB for MJPEG stream")
                return None

        def frame_bytes():
            # Compose a JPEG-encoded frame from the current map state
            img = _ensure_rgb(_render_map_image(controller))
            if img is None:
                return None
            buf = io.BytesIO()
            try:
                img.save(buf, format='JPEG', quality=80)
                return buf.getvalue()
            finally:
                buf.close()

        def generate():
            while True:
                data = frame_bytes()
                if data is None:
                    time.sleep(interval)
                    continue
                # multipart/x-mixed-replace chunk
                yield (b"--" + boundary.encode('ascii') + b"\r\n"
                       b"Content-Type: image/jpeg\r\n"
                       b"Content-Length: " + str(len(data)).encode('ascii') + b"\r\n\r\n" + data + b"\r\n")
                time.sleep(interval)

        return Response(generate(), mimetype=f'multipart/x-mixed-replace; boundary={boundary}')

    def run_app():
        try:
            import logging as _logging
            # Suppress werkzeug request logs
            _logging.getLogger('werkzeug').setLevel(_logging.ERROR)
            try:
                self._web_app.logger.setLevel(_logging.ERROR)
            except Exception:
                pass
        except Exception:
            pass
        try:
            from werkzeug.serving import WSGIRequestHandler as _WSGIRequestHandler
            class _QuietHandler(_WSGIRequestHandler):
                def log(self, type, message, *args):
                    pass
            self._web_server = make_server('0.0.0.0', port, self._web_app, threaded=True, request_handler=_QuietHandler)
        except Exception:
            self._web_server = make_server('0.0.0.0', port, self._web_app, threaded=True)
        self._web_server.serve_forever()

    self._web_server_thread = threading.Thread(target=run_app, daemon=True)
    self._web_server_thread.start()


def _web_render_geometry(self):
    base = getattr(self, '_video_current_frame_pil', None) or getattr(self, 'base_img', None)
    if base is None:
        base_size = (1920, 1080)
    else:
        base_size = base.size
    zoom = float(getattr(self, 'zoom', 1.0))
    pan_x = float(getattr(self, 'pan_x', 0.0))
    pan_y = float(getattr(self, 'pan_y', 0.0))
    sw, sh = int(base_size[0] * zoom), int(base_size[1] * zoom)
    x0, y0 = int(pan_x), int(pan_y)
    min_x, min_y = min(0, x0), min(0, y0)
    max_x, max_y = max(sw, x0 + sw), max(sh, y0 + sh)
    width, height = max_x - min_x, max_y - min_y
    self._web_view_size = (width, height)
    self._web_view_origin = (min_x, min_y)
    self._web_base_size = base_size
    return (width, height), (min_x, min_y), base_size


def _describe_remote_tokens(self, render_offset=None):
    if render_offset is None:
        _, render_offset, _ = _web_render_geometry(self)
    min_x, min_y = render_offset
    zoom = float(getattr(self, 'zoom', 1.0))
    pan_x = float(getattr(self, 'pan_x', 0.0))
    pan_y = float(getattr(self, 'pan_y', 0.0))
    tokens = []
    for idx, token in enumerate(getattr(self, 'tokens', []) or []):
        if str(token.get('type', 'token')).lower() != 'token':
            continue
        if not bool(token.get('player_visible', True)):
            continue
        if str(token.get('entity_type', '')).upper() != 'PC':
            continue
        remote_id = token.get('remote_id') or f"pc-{idx}-{token.get('entity_id') or token.get('entity_type') or 'token'}"
        token['remote_id'] = remote_id
        pos = token.get('position') or (0.0, 0.0)
        try:
            pos_x, pos_y = float(pos[0]), float(pos[1])
        except Exception:
            pos_x, pos_y = 0.0, 0.0
        size_px = token.get('size', getattr(self, 'token_size', 64))
        try:
            size_px = float(size_px)
        except Exception:
            size_px = float(getattr(self, 'token_size', 64))
        screen_x = float(pos_x * zoom + pan_x - min_x)
        screen_y = float(pos_y * zoom + pan_y - min_y)
        tokens.append(
            {
                'id': remote_id,
                'entity_id': str(token.get('entity_id') or ""),
                'label': str(token.get('entity_id') or token.get('entity_type') or 'PC'),
                'position': [pos_x, pos_y],
                'screen_position': [screen_x, screen_y],
                'size': size_px,
                'screen_size': size_px * zoom,
                'border_color': token.get('border_color', '#0ea5e9'),
            }
        )
    return tokens


def _render_map_image(self):
    base = getattr(self, '_video_current_frame_pil', None) or getattr(self, 'base_img', None)
    if not base:
        return None
    try:
        base = base.copy()
    except Exception:
        pass
    (width, height), (min_x, min_y), base_size = _web_render_geometry(self)
    sw, sh = int(base_size[0] * self.zoom), int(base_size[1] * self.zoom)
    x0, y0 = int(self.pan_x), int(self.pan_y)
    img = Image.new('RGBA', (width, height), (0, 0, 0, 255))
    base_resized = base.resize((sw, sh), Image.LANCZOS)
    img.paste(base_resized, (x0 - min_x, y0 - min_y))

    draw = ImageDraw.Draw(img)
    for item in self.tokens:
        item_type = item.get('type', 'token')
        xw, yw = item.get('position', (0, 0))
        sx = int(xw * self.zoom + self.pan_x - min_x)
        sy = int(yw * self.zoom + self.pan_y - min_y)
        if item_type == 'marker':
            continue
        if item_type == 'token':
            if not bool(item.get('player_visible', True)):
                continue
            source = item.get('source_image')
            pil = item.get('pil_image')
            size_px = item.get('size')
            if size_px is None:
                if source is not None:
                    size_px = source.size[0]
                elif pil is not None:
                    size_px = pil.size[0]
                else:
                    size_px = getattr(self, 'token_size', 64)
            try:
                size_px = max(1, int(size_px))
            except Exception:
                size_px = max(1, int(getattr(self, 'token_size', 64)))

            if source is not None:
                nw = nh = max(1, int(size_px * self.zoom))
                if nw <= 0 or nh <= 0:
                    continue
                img_r = source.resize((nw, nh), Image.LANCZOS)
            elif pil:
                tw, th = pil.size
                nw, nh = int(tw * self.zoom), int(th * self.zoom)
                if nw <= 0 or nh <= 0:
                    continue
                img_r = pil.resize((nw, nh), Image.LANCZOS)
            else:
                continue

            img.paste(img_r, (sx, sy), img_r.convert('RGBA'))
            draw.rectangle([sx - 3, sy - 3, sx + nw + 3, sy + nh + 3], outline=item.get('border_color', '#0000ff'), width=3)
        elif item_type in ['rectangle', 'oval']:
            shape_w = int(item.get('width', 50) * self.zoom)
            shape_h = int(item.get('height', 50) * self.zoom)
            fill_color = None
            if item.get('is_filled', True):
                fc = item.get('fill_color')
                fill_color = fc if fc else None
            border_color = item.get('border_color', '#000000') or None
            if item_type == 'rectangle':
                draw.rectangle([sx, sy, sx + shape_w, sy + shape_h], fill=fill_color, outline=border_color, width=2)
            else:
                draw.ellipse([sx, sy, sx + shape_w, sy + shape_h], fill=fill_color, outline=border_color, width=2)
        elif item_type == 'whiteboard':
            points = item.get('points') or []
            if len(points) < 2:
                continue
            screen_points = []
            for px, py in points:
                screen_points.extend([sx + (px - xw) * self.zoom, sy + (py - yw) * self.zoom])
            color = item.get('color', '#FF0000')
            width = item.get('width', 4)
            draw.line(screen_points, fill=color, width=int(max(1, width)), joint='curve')
        elif item_type == 'text':
            text_value = item.get('text', '')
            color = item.get('color', '#FF0000')
            size = int(item.get('text_size', getattr(self, 'text_size', 24)))
            font_cache = getattr(self, '_text_font_cache', None)
            if font_cache is None:
                font_cache = TextFontCache()
                setattr(self, '_text_font_cache', font_cache)
            font = font_cache.pil_font(size)
            try:
                draw.text((sx, sy), text_value, fill=color, font=font, anchor='lt')
            except Exception:
                draw.text((sx, sy), text_value, fill=color, font=font)

    if self.mask_img:
        mask_copy = self.mask_img.copy()
        _, _, _, alpha = mask_copy.split()
        processed_alpha = alpha.point(lambda a: 255 if a > 0 else 0)
        mask_copy.putalpha(processed_alpha)
        mask_resized = mask_copy.resize((sw, sh), Image.LANCZOS)
        img.paste(mask_resized, (x0 - min_x, y0 - min_y), mask_resized)

    return img


def _update_web_display_map(self):
    if not getattr(self, '_web_server_thread', None):
        return
    img = _render_map_image(self)
    if img is None:
        return
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    self._web_image_bytes = buf.getvalue()
    buf.close()

def close_web_display(self, port=None):
    """Shut down the web display server if it is running.

    The server is stopped using Werkzeug's ``shutdown`` API rather than
    sending an HTTP request to a dedicated route.
    """

    thread = getattr(self, '_web_server_thread', None)
    if not thread:
        return

    if port is None:
        port = getattr(
            self,
            '_web_port',
            int(ConfigHelper.get("MapServer", "map_port", fallback=32000)),
        )

    if getattr(self, '_web_server', None):
        try:
            self._web_server.shutdown()
        except Exception:
            pass

    for _ in range(5):  # wait up to ~5 seconds total
        thread.join(timeout=1)
        if not thread.is_alive():
            break

    if thread.is_alive():
        logging.warning("Web display server did not shut down within timeout.")
    else:
        self._web_server_thread = None
        self._web_server = None
        self._web_app = None
