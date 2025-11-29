import threading
import time
import io
from flask import Flask, Response
from werkzeug.serving import make_server

from modules.helpers.config_helper import ConfigHelper
from modules.helpers.logging_helper import log_module_import
from modules.whiteboard.utils.whiteboard_renderer import render_whiteboard_image

log_module_import(__name__)


def open_whiteboard_display(controller, port=None):
    if port is None:
        port = int(ConfigHelper.get("WhiteboardServer", "port", fallback=32500))
    if getattr(controller, "_whiteboard_web_thread", None):
        return

    app = Flask(__name__)
    controller._whiteboard_web_app = app
    controller._whiteboard_port = port

    try:
        refresh_ms = int(ConfigHelper.get("WhiteboardServer", "refresh_ms", fallback=200))
    except Exception:
        refresh_ms = 200
    controller._whiteboard_refresh_ms = refresh_ms

    try:
        use_mjpeg_raw = str(ConfigHelper.get("WhiteboardServer", "use_mjpeg", fallback="1") or "")
        controller._whiteboard_use_mjpeg = use_mjpeg_raw.strip().lower() in ("1", "true", "yes", "on")
    except Exception:
        controller._whiteboard_use_mjpeg = True

    @app.route("/")
    def index():
        use_mjpeg = bool(getattr(controller, "_whiteboard_use_mjpeg", True))
        img_src = "/stream.mjpg" if use_mjpeg else "/board.png?ts=0"
        refresh_script = "" if use_mjpeg else f"""
        <script>
            document.addEventListener('DOMContentLoaded', () => {{
                const REFRESH_MS = {int(getattr(controller, '_whiteboard_refresh_ms', 200))};
                const img = document.getElementById('boardImage');
                function scheduleNext() {{ setTimeout(reloadImage, REFRESH_MS); }}
                function reloadImage() {{ img.src = '/board.png?ts=' + Date.now(); }}
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
        <title>Player Whiteboard</title>
        <style>
            body {{ margin: 0; background: #fff; display: flex; align-items: center; justify-content: center; }}
            img {{ max-width: 100%; max-height: 100vh; object-fit: contain; }}
        </style>
        {refresh_script}
        </head>
        <body>
        <img id='boardImage' src='{img_src}'>
        </body>
        </html>
        """

    @app.route("/board.png")
    def board_png():
        controller._update_web_display_whiteboard()
        data = getattr(controller, "_whiteboard_image_bytes", None)
        if not data:
            return ("No whiteboard image", 404)
        return Response(
            data,
            mimetype="image/png",
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )

    @app.route("/stream.mjpg")
    def stream_mjpeg():
        boundary = "frame"
        interval = max(1, int(getattr(controller, "_whiteboard_refresh_ms", 200))) / 1000.0

        def frame_bytes():
            if hasattr(controller, "_render_whiteboard_image"):
                img = controller._render_whiteboard_image()
            else:
                origin = (0.0, 0.0)
                try:
                    origin = controller._current_view_origin()
                except Exception:
                    pass
                img = render_whiteboard_image(
                    controller.whiteboard_items,
                    getattr(controller, "board_size", (1920, 1080)),
                    font_cache=getattr(controller, "_font_cache", None),
                    grid_origin=origin,
                    zoom=getattr(controller, "view_zoom", 1.0),
                )
            buf = io.BytesIO()
            try:
                img.save(buf, format="JPEG", quality=85)
                return buf.getvalue()
            finally:
                buf.close()

        def generate():
            while True:
                data = frame_bytes()
                if data is None:
                    time.sleep(interval)
                    continue
                yield (
                    b"--" + boundary.encode("ascii") + b"\r\n"
                    + b"Content-Type: image/jpeg\r\n"
                    + b"Content-Length: " + str(len(data)).encode("ascii") + b"\r\n\r\n" + data + b"\r\n"
                )
                time.sleep(interval)

        return Response(generate(), mimetype=f"multipart/x-mixed-replace; boundary={boundary}")

    def run_app():
        try:
            import logging as _logging
            _logging.getLogger("werkzeug").setLevel(_logging.ERROR)
            try:
                controller._whiteboard_web_app.logger.setLevel(_logging.ERROR)
            except Exception:
                pass
        except Exception:
            pass
        controller._whiteboard_server = make_server("0.0.0.0", port, app, threaded=True)
        controller._whiteboard_server.serve_forever()

    controller._whiteboard_web_thread = threading.Thread(target=run_app, daemon=True)
    controller._whiteboard_web_thread.start()


def close_whiteboard_display(controller):
    thread = getattr(controller, "_whiteboard_web_thread", None)
    server = getattr(controller, "_whiteboard_server", None)
    if not thread:
        return
    try:
        if server:
            server.shutdown()
    except Exception:
        pass
    thread.join(timeout=2)
    controller._whiteboard_web_thread = None
    controller._whiteboard_server = None
    controller._whiteboard_web_app = None
