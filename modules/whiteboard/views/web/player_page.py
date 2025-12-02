from __future__ import annotations

from urllib.parse import urlencode


def _script_block(board_width: int, board_height: int, refresh_ms: int, use_mjpeg: bool) -> str:
    return f"""
    <script>
        (() => {{
            const boardSize = {{ width: {board_width}, height: {board_height} }};
            let drawing = false;
            let points = [];
            let currentScale = 1;
            let currentToken = new URLSearchParams(window.location.search).get('token') || '';
            let editingEnabled = false;

            const previewImg = document.getElementById('boardPreview');
            const canvas = document.getElementById('boardCanvas');
            const ctx = canvas.getContext('2d');
            const statusEl = document.getElementById('status');
            const undoBtn = document.getElementById('undoBtn');
            const textBtn = document.getElementById('textBtn');

            function resizeCanvas() {{
                const wrapper = document.getElementById('boardContainer');
                const scale = Math.min(wrapper.clientWidth / boardSize.width, wrapper.clientHeight / boardSize.height);
                currentScale = scale || 1;
                canvas.style.width = `${{boardSize.width * currentScale}}px`;
                canvas.style.height = `${{boardSize.height * currentScale}}px`;
                previewImg.style.width = canvas.style.width;
                previewImg.style.height = canvas.style.height;
            }}

            function getBoardCoords(evt) {{
                const rect = canvas.getBoundingClientRect();
                const x = (evt.clientX - rect.left) * (boardSize.width / rect.width);
                const y = (evt.clientY - rect.top) * (boardSize.height / rect.height);
                return [x, y];
            }}

            function setStatus(message, isError=false) {{
                statusEl.textContent = message;
                statusEl.style.color = isError ? '#b91c1c' : '#111827';
            }}

            function api(url, body={{}}) {{
                const headers = {{ 'Content-Type': 'application/json' }};
                if (currentToken) {{
                    headers['X-Whiteboard-Token'] = currentToken;
                }}
                return fetch(url, {{
                    method: 'POST',
                    headers,
                    body: JSON.stringify(body)
                }}).then(resp => resp.json().then(data => {{ return {{ status: resp.status, data }}; }}));
            }}

            function refreshPreview() {{
                if ({'true' if use_mjpeg else 'false'}) {{
                    previewImg.src = '/stream.mjpg';
                }} else {{
                    previewImg.src = `/board.png?ts=${{Date.now()}}`;
                    setTimeout(refreshPreview, {refresh_ms});
                }}
            }}

            function sendStroke() {{
                if (!points.length) return;
                api('/api/strokes', {{ points, color: '#ff0000', width: 4 }})
                    .then(result => {{
                        if (result.status >= 400) {{
                            setStatus(result.data.message || 'Unable to send stroke', true);
                        }} else {{
                            setStatus('Stroke sent');
                        }}
                    }})
                    .catch(() => setStatus('Network error', true));
                points = [];
            }}

            function handlePointerDown(evt) {{
                if (!editingEnabled) return;
                drawing = true;
                points = [];
                points.push(getBoardCoords(evt));
            }}

            function handlePointerMove(evt) {{
                if (!drawing || !editingEnabled) return;
                const pos = getBoardCoords(evt);
                points.push(pos);
            }}

            function handlePointerUp(evt) {{
                if (!drawing || !editingEnabled) return;
                drawing = false;
                points.push(getBoardCoords(evt));
                sendStroke();
            }}

            function handleText() {{
                if (!editingEnabled) return;
                const text = prompt('Enter text to place on the board:');
                if (!text) return;
                canvas.addEventListener('click', function handler(evt) {{
                    canvas.removeEventListener('click', handler);
                    const [x, y] = getBoardCoords(evt);
                    api('/api/text', {{ text, position: [x, y], color: '#000000', size: 24 }})
                        .then(result => {{
                            if (result.status >= 400) {{
                                setStatus(result.data.message || 'Unable to place text', true);
                            }} else {{
                                setStatus('Text placed');
                            }}
                        }})
                        .catch(() => setStatus('Network error', true));
                }});
            }}

            function handleUndo() {{
                api('/api/undo').then(result => {{
                    if (result.status >= 400) {{
                        setStatus(result.data.message || 'Unable to undo', true);
                    }} else {{
                        setStatus('Undo processed');
                    }}
                }}).catch(() => setStatus('Network error', true));
            }}

            function syncStatus() {{
                fetch('/api/status')
                    .then(resp => resp.json())
                    .then(data => {{
                        editingEnabled = !!data.editing_enabled;
                        undoBtn.disabled = !editingEnabled;
                        textBtn.disabled = !editingEnabled;
                        setStatus(editingEnabled ? 'Editing enabled' : 'Editing disabled');
                        if (!data.use_mjpeg) {{
                            setTimeout(refreshPreview, {refresh_ms});
                        }}
                    }})
                    .catch(() => setStatus('Unable to fetch status', true));
            }}

            window.addEventListener('resize', resizeCanvas);
            canvas.addEventListener('pointerdown', handlePointerDown);
            canvas.addEventListener('pointermove', handlePointerMove);
            canvas.addEventListener('pointerup', handlePointerUp);
            canvas.addEventListener('pointerleave', handlePointerUp);
            textBtn.addEventListener('click', handleText);
            undoBtn.addEventListener('click', handleUndo);

            resizeCanvas();
            syncStatus();
            refreshPreview();
        }})();
    </script>
    """


def build_player_page(board_size: tuple[int, int], refresh_ms: int, use_mjpeg: bool, token: str | None = None) -> str:
    params = {}
    if token:
        params["token"] = token
    query = urlencode(params)
    query_suffix = f"?{query}" if query else ""
    width, height = board_size
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset='utf-8'>
        <title>Player Whiteboard</title>
        <style>
            body {{ margin: 0; background: #f9fafb; font-family: 'Segoe UI', Tahoma, sans-serif; }}
            #boardContainer {{ position: relative; width: 100vw; height: 100vh; display: flex; align-items: center; justify-content: center; overflow: hidden; }}
            #boardPreview {{ position: absolute; top: 0; left: 0; width: 100%; height: 100%; object-fit: contain; }}
            #boardCanvas {{ position: relative; touch-action: none; width: 100%; height: 100%; background: transparent; }}
            #toolbar {{ position: fixed; top: 12px; left: 50%; transform: translateX(-50%); display: flex; gap: 8px; background: rgba(255, 255, 255, 0.95); padding: 8px 12px; border-radius: 10px; box-shadow: 0 8px 20px rgba(0,0,0,0.15); }}
            #toolbar button {{ border: none; padding: 10px 14px; border-radius: 8px; cursor: pointer; font-weight: 600; background: #2563eb; color: #fff; }}
            #toolbar button:disabled {{ background: #9ca3af; cursor: not-allowed; }}
            #status {{ position: fixed; bottom: 10px; left: 50%; transform: translateX(-50%); background: rgba(255,255,255,0.95); padding: 6px 10px; border-radius: 8px; box-shadow: 0 4px 16px rgba(0,0,0,0.08); font-weight: 600; }}
        </style>
    </head>
    <body>
        <div id="toolbar">
            <button id="textBtn">Place Text</button>
            <button id="undoBtn">Undo</button>
        </div>
        <div id="boardContainer">
            <img id="boardPreview" src="/board.png{query_suffix}" alt="Whiteboard preview" />
            <canvas id="boardCanvas" width="{width}" height="{height}"></canvas>
        </div>
        <div id="status">Loading…</div>
        {_script_block(width, height, refresh_ms, use_mjpeg)}
    </body>
    </html>
    """

