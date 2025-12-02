import io
import threading
import time
from flask import Flask, Response
from werkzeug.serving import make_server

from modules.helpers.config_helper import ConfigHelper
from modules.helpers.logging_helper import log_module_import
from modules.whiteboard.utils.whiteboard_renderer import render_whiteboard_image
from modules.whiteboard.views.web.api_blueprint import register_whiteboard_api
from modules.whiteboard.views.web.player_page import build_player_page

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

    register_whiteboard_api(app, controller, getattr(controller, "remote_access_guard", None))

    @app.route("/")
    def index():
        use_mjpeg = bool(getattr(controller, "_whiteboard_use_mjpeg", True))
        refresh_ms = int(getattr(controller, "_whiteboard_refresh_ms", 200))
        token = getattr(getattr(controller, "remote_access_guard", None), "token", None)
        return build_player_page(getattr(controller, "board_size", (1920, 1080)), refresh_ms, use_mjpeg, token)

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
                img = controller._render_whiteboard_image(
                    for_player=True,
                    viewport_size=getattr(controller, "board_size", (1920, 1080)),
                    origin=(0.0, 0.0),
                    zoom=1.0,
                )
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
                    for_player=True,
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
