from __future__ import annotations

from __future__ import annotations

from flask import Blueprint, jsonify, request

from modules.whiteboard.utils.remote_access_guard import RemoteAccessGuard


def _extract_token() -> str | None:
    return request.headers.get("X-Map-Token") or request.args.get("token")


def register_map_api(app, controller, access_guard: RemoteAccessGuard | None):
    access_guard = access_guard or RemoteAccessGuard(enabled=False, token="")
    blueprint = Blueprint("map_api", __name__)

    def _require_access():
        token = _extract_token()
        if not access_guard.enabled:
            return jsonify({"message": "Editing is currently disabled"}), 403
        if not access_guard.is_request_authorized(token):
            return jsonify({"message": "Invalid or missing token"}), 401
        return None

    @blueprint.route("/api/status", methods=["GET"])
    def api_status():
        viewport_size, render_offset, base_size = controller._web_render_geometry()
        tokens = controller._describe_remote_tokens(render_offset=render_offset)
        return jsonify(
            {
                "editing_enabled": bool(access_guard.enabled),
                "refresh_ms": int(getattr(controller, "_web_refresh_ms", 200)),
                "use_mjpeg": bool(getattr(controller, "_web_use_mjpeg", True)),
                "zoom": float(getattr(controller, "zoom", 1.0)),
                "pan": [float(getattr(controller, "pan_x", 0.0)), float(getattr(controller, "pan_y", 0.0))],
                "render_size": [int(viewport_size[0]), int(viewport_size[1])],
                "render_offset": [float(render_offset[0]), float(render_offset[1])],
                "map_size": [int(base_size[0]), int(base_size[1])],
                "tokens": tokens,
            }
        )

    @blueprint.route("/api/tokens/move", methods=["POST"])
    def api_move_token():
        unauthorized = _require_access()
        if unauthorized:
            return unauthorized
        payload = request.get_json(silent=True) or {}
        token_id = payload.get("token_id")
        position = payload.get("position") or []
        if not token_id:
            return jsonify({"message": "token_id is required"}), 400
        if not isinstance(position, (list, tuple)) or len(position) != 2:
            return jsonify({"message": "position must include x and y"}), 400
        try:
            controller.handle_remote_token_move(token_id=str(token_id), position=position)
        except ValueError as exc:
            return jsonify({"message": str(exc)}), 400
        except Exception as exc:  # noqa: BLE001
            return jsonify({"message": f"Unable to move token: {exc}"}), 500
        return jsonify({"status": "ok"})

    @blueprint.route("/api/strokes", methods=["POST"])
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

    @blueprint.route("/api/text", methods=["POST"])
    def api_text():
        unauthorized = _require_access()
        if unauthorized:
            return unauthorized
        payload = request.get_json(silent=True) or {}
        text = str(payload.get("text") or "").strip()
        position = payload.get("position") or []
        color = payload.get("color") or "#000000"
        size = payload.get("size") or 24
        text_id = payload.get("text_id")
        if not text:
            return jsonify({"message": "Text content is required"}), 400
        if not isinstance(position, (list, tuple)) or len(position) != 2:
            return jsonify({"message": "Position must be a two element array"}), 400
        try:
            controller.handle_remote_text(
                text=text,
                position=position,
                color=str(color),
                size=float(size),
                text_id=str(text_id) if text_id else None,
            )
        except ValueError as exc:
            return jsonify({"message": str(exc)}), 400
        except Exception as exc:  # noqa: BLE001
            return jsonify({"message": f"Unable to place text: {exc}"}), 500
        return jsonify({"status": "ok"})

    app.register_blueprint(blueprint)

