import io
import threading
import logging
from flask import Flask, send_file
from werkzeug.serving import make_server
from PIL import Image, ImageDraw
from modules.helpers.config_helper import ConfigHelper

# Simple Flask app to serve the current map image

def open_web_display(self, port=None):
    if port is None:
        port = int(ConfigHelper.get("MapServer", "map_port", fallback=32000))
    if getattr(self, '_web_server_thread', None):
        return  # already running
    self._web_app = Flask(__name__)
    self._web_port = port

    controller = self

    @self._web_app.route('/')
    def index():
        # Basic HTML page that reloads the map image periodically so
        # changes on the GM side appear without requiring a manual refresh.
        return """
        <!DOCTYPE html>
        <html>
        <head>
        <meta charset='utf-8'>
        <title>Map Display</title>
        <style>
            body { margin: 0; }
            img { max-width: 100%; height: auto; }
        </style>
        <script>
            function reloadImage() {
                const img = document.getElementById('mapImage');
                img.src = '/map.png?ts=' + Date.now();
            }
            setInterval(reloadImage, 1000);
        </script>
        </head>
        <body>
        <img id='mapImage' src='/map.png?ts=0'>
        </body>
        </html>
        """

    @self._web_app.route('/map.png')
    def map_png():
        controller._update_web_display_map()
        data = getattr(controller, '_web_image_bytes', None)
        if not data:
            return ('No map image', 404)
        buf = io.BytesIO(data)
        resp = send_file(buf, mimetype='image/png', max_age=0)
        resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        resp.headers['Pragma'] = 'no-cache'
        resp.headers['Expires'] = '0'
        return resp

    def run_app():
        self._web_server = make_server('0.0.0.0', port, self._web_app, threaded=True)
        self._web_server.serve_forever()

    self._web_server_thread = threading.Thread(target=run_app, daemon=True)
    self._web_server_thread.start()


def _render_map_image(self):
    if not self.base_img:
        return None
    w, h = self.base_img.size
    sw, sh = int(w * self.zoom), int(h * self.zoom)
    x0, y0 = int(self.pan_x), int(self.pan_y)
    min_x, min_y = min(0, x0), min(0, y0)
    max_x, max_y = max(sw, x0 + sw), max(sh, y0 + sh)
    width, height = max_x - min_x, max_y - min_y
    img = Image.new('RGBA', (width, height), (0, 0, 0, 255))
    base_resized = self.base_img.resize((sw, sh), Image.LANCZOS)
    img.paste(base_resized, (x0 - min_x, y0 - min_y))

    draw = ImageDraw.Draw(img)
    for item in self.tokens:
        item_type = item.get('type', 'token')
        xw, yw = item.get('position', (0, 0))
        sx = int(xw * self.zoom + self.pan_x - min_x)
        sy = int(yw * self.zoom + self.pan_y - min_y)
        if item_type == 'token':
            pil = item.get('pil_image')
            if pil:
                tw, th = pil.size
                nw, nh = int(tw * self.zoom), int(th * self.zoom)
                img_r = pil.resize((nw, nh), Image.LANCZOS)
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
