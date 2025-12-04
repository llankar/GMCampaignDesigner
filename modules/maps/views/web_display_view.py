import io
import threading
import logging
import time
from flask import Flask, Response
from werkzeug.serving import make_server
from PIL import Image, ImageDraw
from modules.helpers.config_helper import ConfigHelper
from modules.helpers.logging_helper import log_module_import
from modules.maps.utils.text_items import TextFontCache

log_module_import(__name__)

# Simple Flask app to serve the current map image

def open_web_display(self, port=None):
    if port is None:
        port = int(ConfigHelper.get("MapServer", "map_port", fallback=32000))
    if getattr(self, '_web_server_thread', None):
        return  # already running
    self._web_app = Flask(__name__)
    self._web_port = port

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
            body {{ margin: 0; }}
            img {{ max-width: 100%; height: auto; }}
        </style>
        {refresh_script}
        </head>
        <body>
        <img id='mapImage' src='{img_src}'>
        </body>
        </html>
        """

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


def _render_map_image(self):
    base = getattr(self, '_video_current_frame_pil', None) or getattr(self, 'base_img', None)
    if not base:
        return None
    try:
        base = base.copy()
    except Exception:
        pass
    w, h = base.size
    sw, sh = int(w * self.zoom), int(h * self.zoom)
    x0, y0 = int(self.pan_x), int(self.pan_y)
    min_x, min_y = min(0, x0), min(0, y0)
    max_x, max_y = max(sw, x0 + sw), max(sh, y0 + sh)
    width, height = max_x - min_x, max_y - min_y
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
