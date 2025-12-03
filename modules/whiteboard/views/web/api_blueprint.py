from __future__ import annotations

from flask import jsonify, request

from modules.whiteboard.utils.remote_access_guard import RemoteAccessGuard


def _extract_token() -> str | None:
    return request.headers.get("X-Whiteboard-Token") or request.args.get("token")


def register_whiteboard_api(app, controller, access_guard: RemoteAccessGuard | None):
    access_guard = access_guard or RemoteAccessGuard(enabled=False, token="")
    def _require_access():
        token = _extract_token()
        if not access_guard.enabled:
            return jsonify({"message": "Editing is currently disabled"}), 403
        if not access_guard.is_request_authorized(token):
            return jsonify({"message": "Invalid or missing token"}), 401
        return None

    @app.route("/api/status", methods=["GET"])
    def api_status():
        return jsonify(
            {
                "editing_enabled": bool(access_guard.enabled),
                "board_size": list(getattr(controller, "board_size", (1920, 1080))),
                "refresh_ms": int(getattr(controller, "_whiteboard_refresh_ms", 200)),
                "use_mjpeg": bool(getattr(controller, "_whiteboard_use_mjpeg", True)),
                "text_size": int(getattr(controller, "text_size", 24)),
            }
        )

    @app.route("/api/strokes", methods=["POST"])
    def api_strokes():
        unauthorized = _require_access()
        if unauthorized:
            return unauthorized
        payload = request.get_json(silent=True) or {}
        points = payload.get("points") or []
        color = payload.get("color") or "#ff0000"
        width = payload.get("width") or 4
        if not isinstance(points, list) or len(points) < 2:
            return jsonify({"message": "At least two points are required"}), 400
        try:
            controller.handle_remote_stroke(points=points, color=str(color), width=float(width))
        except ValueError as exc:
            return jsonify({"message": str(exc)}), 400
        except Exception as exc:  # noqa: BLE001
            return jsonify({"message": f"Unable to add stroke: {exc}"}), 500
        return jsonify({"status": "ok"})

    @app.route("/api/text", methods=["POST"])
    def api_text():
        unauthorized = _require_access()
        if unauthorized:
            return unauthorized
        payload = request.get_json(silent=True) or {}
        text = str(payload.get("text") or "").strip()
        position = payload.get("position") or []
        color = payload.get("color") or "#000000"
        size = payload.get("size") or 24
        if not text:
            return jsonify({"message": "Text content is required"}), 400
        if not isinstance(position, (list, tuple)) or len(position) != 2:
            return jsonify({"message": "Position must be a two element array"}), 400
        try:
            controller.handle_remote_text(text=text, position=position, color=str(color), size=float(size))
        except ValueError as exc:
            return jsonify({"message": str(exc)}), 400
        except Exception as exc:  # noqa: BLE001
            return jsonify({"message": f"Unable to place text: {exc}"}), 500
        return jsonify({"status": "ok"})

    @app.route("/api/undo", methods=["POST"])
    def api_undo():
        unauthorized = _require_access()
        if unauthorized:
            return unauthorized
        try:
            controller.handle_remote_undo()
        except Exception as exc:  # noqa: BLE001
            return jsonify({"message": f"Unable to undo: {exc}"}), 500
        return jsonify({"status": "ok"})

