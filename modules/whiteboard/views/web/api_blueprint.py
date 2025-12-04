from __future__ import annotations

from flask import jsonify, request

from modules.whiteboard.utils.remote_access_guard import RemoteAccessGuard
from modules.whiteboard.utils.uploaded_images import save_uploaded_image


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
        viewport_size = getattr(controller, "_web_view_size", None)
        origin = getattr(controller, "_web_view_origin", None)
        if viewport_size is None or origin is None:
            try:
                viewport_size, origin, _ = controller._web_render_geometry()
            except Exception:
                viewport_size = getattr(controller, "board_size", (1920, 1080))
                origin = (0.0, 0.0)

        images = []
        for item in getattr(controller, "whiteboard_items", []) or []:
            if not isinstance(item, dict) or item.get("type") != "image":
                continue
            position = item.get("position") or (0.0, 0.0)
            pos_x = pos_y = 0.0
            if isinstance(position, (list, tuple)) and len(position) >= 2:
                pos_x = float(position[0])
                pos_y = float(position[1])

            size = item.get("size") if isinstance(item.get("size"), dict) else {}
            images.append(
                {
                    "image_id": item.get("image_id"),
                    "position": [pos_x, pos_y],
                    "size": {
                        "width": float(size.get("width", 0.0)),
                        "height": float(size.get("height", 0.0)),
                    },
                }
            )

        return jsonify(
            {
                "editing_enabled": bool(access_guard.enabled),
                "board_size": list(viewport_size),
                "board_origin": list(origin),
                "refresh_ms": int(getattr(controller, "_whiteboard_refresh_ms", 200)),
                "use_mjpeg": bool(getattr(controller, "_whiteboard_use_mjpeg", True)),
                "text_size": int(getattr(controller, "text_size", 24)),
                "web_text_scale": float(
                    getattr(controller, "get_web_text_scale", lambda: 1.0)()
                ),
                "zoom": float(getattr(controller, "view_zoom", 1.0)),
                "images": images,
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

    @app.route("/api/images/upload", methods=["POST"])
    def api_image_upload():
        unauthorized = _require_access()
        if unauthorized:
            return unauthorized

        file = request.files.get("file")
        if not file:
            return jsonify({"message": "Image file is required"}), 400

        try:
            uploaded = save_uploaded_image(file)
        except ValueError as exc:
            return jsonify({"message": str(exc)}), 400
        except Exception as exc:  # noqa: BLE001
            return jsonify({"message": f"Unable to store image: {exc}"}), 500

        return jsonify(
            {
                "asset_key": uploaded.asset_key,
                "width": uploaded.width,
                "height": uploaded.height,
            }
        )

    @app.route("/api/images/place", methods=["POST"])
    def api_image_place():
        unauthorized = _require_access()
        if unauthorized:
            return unauthorized

        payload = request.get_json(silent=True) or {}
        asset_key = payload.get("asset_key") or payload.get("asset")
        position = payload.get("position") or []
        size = payload.get("size") or {}
        if not asset_key:
            return jsonify({"message": "asset_key is required"}), 400
        if not isinstance(position, (list, tuple)) or len(position) != 2:
            return jsonify({"message": "Position must include x and y"}), 400
        try:
            image_id = controller.handle_remote_image(asset_key=asset_key, position=position, size=size)
        except ValueError as exc:
            return jsonify({"message": str(exc)}), 400
        except Exception as exc:  # noqa: BLE001
            return jsonify({"message": f"Unable to place image: {exc}"}), 500
        return jsonify({"status": "ok", "image_id": image_id})

    @app.route("/api/images/resize", methods=["POST"])
    def api_image_resize():
        unauthorized = _require_access()
        if unauthorized:
            return unauthorized

        payload = request.get_json(silent=True) or {}
        image_id = payload.get("image_id")
        size = payload.get("size") or {}
        if not image_id:
            return jsonify({"message": "image_id is required"}), 400

        try:
            controller.handle_remote_image_resize(image_id=image_id, size=size)
        except ValueError as exc:
            return jsonify({"message": str(exc)}), 400
        except Exception as exc:  # noqa: BLE001
            return jsonify({"message": f"Unable to resize image: {exc}"}), 500

        return jsonify({"status": "ok", "image_id": image_id})

    @app.route("/api/images/move", methods=["POST"])
    def api_image_move():
        unauthorized = _require_access()
        if unauthorized:
            return unauthorized

        payload = request.get_json(silent=True) or {}
        image_id = payload.get("image_id")
        position = payload.get("position") or []
        if not image_id:
            return jsonify({"message": "image_id is required"}), 400

        try:
            controller.handle_remote_image_move(image_id=image_id, position=position)
        except ValueError as exc:
            return jsonify({"message": str(exc)}), 400
        except Exception as exc:  # noqa: BLE001
            return jsonify({"message": f"Unable to move image: {exc}"}), 500

        return jsonify({"status": "ok", "image_id": image_id})

    @app.route("/api/images/delete", methods=["POST"])
    def api_image_delete():
        unauthorized = _require_access()
        if unauthorized:
            return unauthorized

        payload = request.get_json(silent=True) or {}
        image_id = payload.get("image_id")
        if not image_id:
            return jsonify({"message": "image_id is required"}), 400

        try:
            controller.handle_remote_image_delete(image_id=image_id)
        except ValueError as exc:
            return jsonify({"message": str(exc)}), 400
        except Exception as exc:  # noqa: BLE001
            return jsonify({"message": f"Unable to delete image: {exc}"}), 500

        return jsonify({"status": "ok", "image_id": image_id})

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

