from __future__ import annotations

from urllib.parse import urlencode


def _style_block() -> str:
    return """
    <style>
        :root {
            --panel-bg: rgba(255, 255, 255, 0.95);
            --panel-shadow: 0 8px 20px rgba(0, 0, 0, 0.15);
            --accent: #2563eb;
            --accent-muted: #9ca3af;
            --danger: #b91c1c;
        }

        * { box-sizing: border-box; }

        body {
            margin: 0;
            background: #fff;
            font-family: 'Segoe UI', Tahoma, sans-serif;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }

        #boardContainer {
            position: relative;
            width: 100%;
            flex: 1 1 auto;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 0;
            background: #fff;
            overflow: hidden;
        }

        #boardContainer.panning { cursor: grabbing; }

        #boardSurface {
            position: relative;
            background: #fff;
            transform-origin: center center;
        }

        #boardPreview {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            object-fit: contain;
            pointer-events: none;
        }

        #boardCanvas {
            position: absolute;
            top: 0;
            left: 0;
            touch-action: none;
            width: 100%;
            height: 100%;
            background: transparent;
        }

        #toolbar {
            position: sticky;
            top: 12px;
            align-self: center;
            display: flex;
            gap: 8px;
            background: var(--panel-bg);
            padding: 10px 12px;
            border-radius: 10px;
            box-shadow: var(--panel-shadow);
            align-items: center;
            flex-wrap: wrap;
            z-index: 10;
        }

        #toolbar button {
            border: none;
            padding: 10px 14px;
            border-radius: 8px;
            cursor: pointer;
            font-weight: 600;
            background: var(--accent);
            color: #fff;
            transition: background 0.15s ease;
        }

        #toolbar button.secondary { background: #111827; color: #fff; }
        #toolbar button.ghost { background: #e5e7eb; color: #111827; }

        #toolbar button:disabled { background: var(--accent-muted); cursor: not-allowed; }

        #toolbar .field {
            display: flex;
            align-items: center;
            gap: 6px;
            padding: 8px 10px;
            background: #f3f4f6;
            border-radius: 8px;
        }

        #colorSwatch {
            width: 20px;
            height: 20px;
            border-radius: 6px;
            border: 2px solid rgba(0, 0, 0, 0.1);
            box-shadow: inset 0 1px 2px rgba(0, 0, 0, 0.15);
        }

        #toolbar input[type='text'] {
            border: 1px solid #d1d5db;
            border-radius: 6px;
            padding: 8px;
            min-width: 180px;
            font-weight: 600;
        }

        #toolbar select {
            border: 1px solid #d1d5db;
            border-radius: 6px;
            padding: 8px;
            font-weight: 600;
            background: #fff;
        }

        #status {
            position: fixed;
            bottom: 10px;
            left: 50%;
            transform: translateX(-50%);
            background: var(--panel-bg);
            padding: 8px 12px;
            border-radius: 8px;
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08);
            font-weight: 600;
            color: #111827;
            z-index: 10;
        }

        #textDialog {
            position: fixed;
            inset: 0;
            background: rgba(17, 24, 39, 0.45);
            display: none;
            align-items: center;
            justify-content: center;
            padding: 16px;
            z-index: 20;
        }

        #textDialog.visible {
            display: flex;
        }

        #textDialog .modal-card {
            background: #fff;
            border-radius: 12px;
            box-shadow: var(--panel-shadow);
            padding: 18px;
            width: min(520px, 90vw);
            max-width: 640px;
            display: flex;
            flex-direction: column;
            gap: 12px;
        }

        #textDialog h3 {
            margin: 0;
            font-size: 18px;
            color: #111827;
        }

        #textDialog p {
            margin: 0;
            color: #374151;
            line-height: 1.4;
        }

        #textDialog textarea {
            width: 100%;
            min-height: 180px;
            resize: vertical;
            border-radius: 8px;
            border: 1px solid #e5e7eb;
            padding: 10px 12px;
            font-size: 15px;
            font-family: 'Segoe UI', Tahoma, sans-serif;
        }

        #textDialog .actions {
            display: flex;
            justify-content: flex-end;
            gap: 10px;
        }

        #textDialog .actions button {
            padding: 10px 14px;
            border-radius: 8px;
            border: none;
            font-weight: 700;
            cursor: pointer;
        }

        #textDialog .actions .cancel {
            background: #e5e7eb;
            color: #111827;
        }

        #textDialog .actions .save {
            background: var(--accent);
            color: #fff;
        }
    </style>
    """


TEXT_SIZES = [16, 20, 24, 32, 40, 48]
DEFAULT_TEXT_SIZE = 24


def _script_block(
    board_width: int,
    board_height: int,
    origin_x: float,
    origin_y: float,
    refresh_ms: int,
    use_mjpeg: bool,
    text_sizes: list[int],
    default_text_size: int,
) -> str:
    return f"""
    <script>
        (() => {{
            const boardSize = {{ width: {board_width}, height: {board_height} }};
            const boardOrigin = {{ x: {origin_x}, y: {origin_y} }};
            const useMjpeg = {'true' if use_mjpeg else 'false'};
            const refreshDelay = {refresh_ms};
            const allowedTextSizes = [{', '.join(map(str, text_sizes))}];
            let drawing = false;
            let points = [];
            let currentScale = 1;
            let baseScale = 1;
            let zoomLevel = 1;
            let pan = {{ x: 0, y: 0 }};
            let boardOffset = {{ x: 0, y: 0 }};
            let isPanning = false;
            let panStart = {{ x: 0, y: 0 }};
            let drawingArmed = false;
            let currentToken = '';
            let editingEnabled = false;
            let textSize = {default_text_size};
            let sessionColor = '';
            let pinchState = null;
            const activePointers = new Map();

            const previewImg = document.getElementById('boardPreview');
            const canvas = document.getElementById('boardCanvas');
            const surface = document.getElementById('boardSurface');
            const container = document.getElementById('boardContainer');
            const ctx = canvas.getContext('2d');
            const statusEl = document.getElementById('status');
            const undoBtn = document.getElementById('undoBtn');
            const textBtn = document.getElementById('textBtn');
            const drawBtn = document.getElementById('drawBtn');
            const refreshBtn = document.getElementById('refreshBtn');
            const tokenInput = document.getElementById('tokenInput');
            const colorSwatch = document.getElementById('colorSwatch');
            const colorValue = document.getElementById('colorValue');
            const textSizeSelect = document.getElementById('textSizeSelect');
            const textDialog = document.getElementById('textDialog');
            const textInput = document.getElementById('textInput');
            const textCancel = document.getElementById('textCancel');
            const textSave = document.getElementById('textSave');

            function createSessionColor() {{
                const existing = sessionStorage.getItem('whiteboardSessionColor');
                if (existing) {{
                    return existing;
                }}
                const hue = Math.floor(Math.random() * 360);
                const saturation = 70 + Math.floor(Math.random() * 20);
                const lightness = 50 + Math.floor(Math.random() * 10);
                const hsl = `hsl(${{hue}} ${{saturation}}% ${{lightness}}%)`;
                const tempCanvas = document.createElement('canvas');
                const tempCtx = tempCanvas.getContext('2d');
                tempCtx.fillStyle = hsl;
                tempCtx.fillRect(0, 0, 1, 1);
                const data = tempCtx.getImageData(0, 0, 1, 1).data;
                const hex = `#${{[data[0], data[1], data[2]].map(v => v.toString(16).padStart(2, '0')).join('')}}`;
                sessionStorage.setItem('whiteboardSessionColor', hex);
                return hex;
            }}

            function updateSessionColorDisplay() {{
                if (!sessionColor) return;
                colorSwatch.style.backgroundColor = sessionColor;
                colorValue.textContent = sessionColor.toUpperCase();
            }}

            function clamp(value, min, max) {{
                return Math.min(max, Math.max(min, value));
            }}

            function updateBoardGeometry(size, origin) {{
                let changed = false;

                if (size && Number.isFinite(size.width) && Number.isFinite(size.height)) {{
                    const width = Math.max(1, Number(size.width));
                    const height = Math.max(1, Number(size.height));
                    if (width !== boardSize.width || height !== boardSize.height) {{
                        boardSize.width = width;
                        boardSize.height = height;
                        changed = true;
                    }}
                }}

                if (origin && Number.isFinite(origin.x) && Number.isFinite(origin.y)) {{
                    const ox = Number(origin.x);
                    const oy = Number(origin.y);
                    if (ox !== boardOrigin.x || oy !== boardOrigin.y) {{
                        boardOrigin.x = ox;
                        boardOrigin.y = oy;
                        changed = true;
                    }}
                }}

                if (changed) {{
                    resizeCanvas();
                }}
            }}

            function applyViewportTransform() {{
                const viewportWidth = container.clientWidth || window.innerWidth || boardSize.width;
                const viewportHeight = container.clientHeight || window.innerHeight || boardSize.height;
                const boardDisplayWidth = boardSize.width * (baseScale || 1);
                const boardDisplayHeight = boardSize.height * (baseScale || 1);
                const padding = 200;
                const minimumSurfaceWidth = viewportWidth / Math.max(zoomLevel || 1, 0.01);
                const minimumSurfaceHeight = viewportHeight / Math.max(zoomLevel || 1, 0.01);
                const surfaceWidth = Math.max(boardDisplayWidth + padding * 2, minimumSurfaceWidth);
                const surfaceHeight = Math.max(boardDisplayHeight + padding * 2, minimumSurfaceHeight);

                boardOffset = {{
                    x: (surfaceWidth - boardDisplayWidth) / 2,
                    y: (surfaceHeight - boardDisplayHeight) / 2,
                }};

                currentScale = (baseScale || 1) * (zoomLevel || 1);

                const scaledSurfaceWidth = surfaceWidth * (zoomLevel || 1);
                const scaledSurfaceHeight = surfaceHeight * (zoomLevel || 1);
                const effectiveZoom = Math.max(zoomLevel || 1, 0.01);
                const panLimitX = Math.max(
                    padding,
                    ((surfaceWidth - viewportWidth) / 2 + padding) / effectiveZoom,
                );
                const panLimitY = Math.max(
                    padding,
                    ((surfaceHeight - viewportHeight) / 2 + padding) / effectiveZoom,
                );
                pan.x = clamp(pan.x, -panLimitX, panLimitX);
                pan.y = clamp(pan.y, -panLimitY, panLimitY);

                canvas.width = boardDisplayWidth;
                canvas.height = boardDisplayHeight;
                surface.style.width = `${{surfaceWidth}}px`;
                surface.style.height = `${{surfaceHeight}}px`;
                canvas.style.width = `${{boardDisplayWidth}}px`;
                canvas.style.height = `${{boardDisplayHeight}}px`;
                canvas.style.left = `${{boardOffset.x}}px`;
                canvas.style.top = `${{boardOffset.y}}px`;
                previewImg.width = boardDisplayWidth;
                previewImg.height = boardDisplayHeight;
                previewImg.style.width = `${{boardDisplayWidth}}px`;
                previewImg.style.height = `${{boardDisplayHeight}}px`;
                previewImg.style.left = `${{boardOffset.x}}px`;
                previewImg.style.top = `${{boardOffset.y}}px`;
                surface.style.transform = `translate(${{pan.x}}px, ${{pan.y}}px) scale(${{zoomLevel}})`;
            }}

            function resizeCanvas() {{
                const viewportWidth = container.clientWidth || window.innerWidth || boardSize.width;
                const viewportHeight = container.clientHeight || window.innerHeight || boardSize.height;
                const buffer = 200;
                const widthScale = (viewportWidth + buffer) / boardSize.width;
                const heightScale = (viewportHeight + buffer) / boardSize.height;
                baseScale = Math.max(widthScale, heightScale) || 1;
                applyViewportTransform();
            }}

            function getBoardCoords(evt) {{
                return getBoardCoordsFromClient(evt.clientX, evt.clientY);
            }}

            function getBoardCoordsFromClient(clientX, clientY) {{
                const rect = surface.getBoundingClientRect();
                const scale = currentScale || 1;
                const offsetX = (boardOffset.x || 0) * (zoomLevel || 1);
                const offsetY = (boardOffset.y || 0) * (zoomLevel || 1);
                const x = (clientX - rect.left - offsetX) / scale + boardOrigin.x;
                const y = (clientY - rect.top - offsetY) / scale + boardOrigin.y;
                return [x, y];
            }}

            function addActivePointer(evt) {{
                activePointers.set(evt.pointerId, {{ x: evt.clientX, y: evt.clientY }});
            }}

            function updateActivePointer(evt) {{
                if (activePointers.has(evt.pointerId)) {{
                    activePointers.set(evt.pointerId, {{ x: evt.clientX, y: evt.clientY }});
                }}
            }}

            function removeActivePointer(evt) {{
                activePointers.delete(evt.pointerId);
            }}

            function getPinchData() {{
                const pointers = Array.from(activePointers.values());
                if (pointers.length < 2) return null;

                const [first, second] = pointers;
                const dx = second.x - first.x;
                const dy = second.y - first.y;
                const distance = Math.hypot(dx, dy) || 1;
                const midpoint = {{ x: (first.x + second.x) / 2, y: (first.y + second.y) / 2 }};
                return {{ distance, midpoint }};
            }}

            function startPinch() {{
                const pinch = getPinchData();
                if (!pinch) return;

                pinchState = {{
                    startDistance: pinch.distance,
                    startZoom: zoomLevel,
                    startPan: {{ ...pan }},
                    anchorClient: {{ ...pinch.midpoint }},
                    anchorBoard: getBoardCoordsFromClient(pinch.midpoint.x, pinch.midpoint.y),
                }};
                drawing = false;
                clearPreviewStroke();
            }}

            function updatePinch() {{
                if (!pinchState) return;
                const pinch = getPinchData();
                if (!pinch) return;

                const scaleFactor = pinch.distance / (pinchState.startDistance || 1);
                const newZoom = clamp(pinchState.startZoom * scaleFactor, 0.2, 3);
                zoomLevel = newZoom;

                const scale = (baseScale || 1) * newZoom;
                const anchor = pinchState.anchorBoard;
                const target = pinchState.anchorClient;
                pan.x = target.x - anchor[0] * scale;
                pan.y = target.y - anchor[1] * scale;

                applyViewportTransform();
            }}

            function endPinch() {{
                pinchState = null;
            }}

            function setStatus(message, isError=false) {{
                statusEl.textContent = message;
                statusEl.style.color = isError ? getComputedStyle(document.documentElement).getPropertyValue('--danger') : '#111827';
            }}

            function applyToken(newToken) {{
                currentToken = (newToken || '').trim();
                tokenInput.value = currentToken;
                if (currentToken) {{
                    localStorage.setItem('whiteboardToken', currentToken);
                }} else {{
                    localStorage.removeItem('whiteboardToken');
                }}
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

            function normalizeTextSize(value, fallback = allowedTextSizes[2]) {{
                const parsed = parseFloat(value);
                if (!Number.isFinite(parsed)) {{
                    return fallback;
                }}

                return allowedTextSizes.reduce((closest, size) => {{
                    const difference = Math.abs(size - parsed);
                    const closestDiff = Math.abs(closest - parsed);
                    return difference < closestDiff ? size : closest;
                }}, allowedTextSizes[0]);
            }}

            function setTextSize(value, {{ persist = true }} = {{}}) {{
                textSize = value;
                if (textSizeSelect) {{
                    textSizeSelect.value = String(Math.round(value));
                }}
                if (persist) {{
                    localStorage.setItem('whiteboardTextSize', String(value));
                }}
            }}

            function refreshPreview() {{
                if (useMjpeg) {{
                    if (previewImg.src !== '/stream.mjpg') {{
                        previewImg.src = '/stream.mjpg';
                    }}
                }} else {{
                    previewImg.src = `/board.png?ts=${{Date.now()}}`;
                    setTimeout(refreshPreview, refreshDelay);
                }}
            }}

            function clearPreviewStroke() {{
                ctx.clearRect(0, 0, canvas.width, canvas.height);
            }}

            function drawPreviewStroke() {{
                if (points.length < 2) return;
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                const scale = currentScale || 1;
                ctx.lineWidth = 4 * scale;
                ctx.lineCap = 'round';
                ctx.lineJoin = 'round';
                ctx.strokeStyle = sessionColor;
                ctx.beginPath();
                ctx.moveTo((points[0][0] - boardOrigin.x) * scale, (points[0][1] - boardOrigin.y) * scale);
                for (let i = 1; i < points.length; i++) {{
                    ctx.lineTo((points[i][0] - boardOrigin.x) * scale, (points[i][1] - boardOrigin.y) * scale);
                }}
                ctx.stroke();
            }}

            function sendStroke() {{
                if (!points.length) return;
                const strokePoints = points.slice();
                api('/api/strokes', {{ points: strokePoints, color: sessionColor, width: 4 }})
                    .then(result => {{
                        if (result.status >= 400) {{
                            setStatus(result.data.message || 'Unable to send stroke', true);
                        }} else {{
                            setStatus('Stroke sent');
                            if (!useMjpeg) {{
                                refreshPreview();
                            }}
                        }}
                        clearPreviewStroke();
                    }})
                    .catch(() => {{
                        setStatus('Network error', true);
                        clearPreviewStroke();
                    }});
                points = [];
            }}

            function isPanGesture(evt) {{
                const isTouch = evt.pointerType === 'touch';
                const touchPan = isTouch && (!drawingArmed || !editingEnabled);
                return (
                    touchPan ||
                    evt.button === 1 || evt.button === 2 ||
                    evt.ctrlKey || evt.metaKey || evt.altKey ||
                    !editingEnabled
                );
            }}

            function beginPan(evt) {{
                isPanning = true;
                panStart = {{ x: evt.clientX, y: evt.clientY }};
                container.classList.add('panning');
            }}

            function updatePan(evt) {{
                if (!isPanning) return;
                const deltaX = evt.clientX - panStart.x;
                const deltaY = evt.clientY - panStart.y;
                const speedScale = Math.max(zoomLevel || 1, 0.1);
                pan.x += deltaX * speedScale;
                pan.y += deltaY * speedScale;
                panStart = {{ x: evt.clientX, y: evt.clientY }};
                applyViewportTransform();
            }}

            function endPan() {{
                if (!isPanning) return;
                isPanning = false;
                container.classList.remove('panning');
            }}

            function handleWheel(evt) {{
                evt.preventDefault();
                const zoomChange = evt.deltaY < 0 ? 1.1 : 0.9;
                zoomLevel = clamp(zoomLevel * zoomChange, 0.2, 3);
                applyViewportTransform();
            }}

            function handlePointerDown(evt) {{
                addActivePointer(evt);

                if (activePointers.size === 2) {{
                    startPinch();
                    return;
                }}

                if (isPanGesture(evt)) {{
                    evt.preventDefault();
                    beginPan(evt);
                    return;
                }}
                if (!editingEnabled || !drawingArmed) return;
                clearPreviewStroke();
                drawing = true;
                points = [];
                points.push(getBoardCoords(evt));
            }}

            function handlePointerMove(evt) {{
                updateActivePointer(evt);

                if (pinchState) {{
                    evt.preventDefault();
                    updatePinch();
                    return;
                }}

                if (isPanning) {{
                    evt.preventDefault();
                    updatePan(evt);
                    return;
                }}
                if (!drawing || !editingEnabled || !drawingArmed) return;
                const pos = getBoardCoords(evt);
                points.push(pos);
                drawPreviewStroke();
            }}

            function handlePointerUp(evt) {{
                removeActivePointer(evt);

                if (pinchState && activePointers.size < 2) {{
                    endPinch();
                }}

                if (isPanning) {{
                    endPan();
                }}
                if (!drawing || !editingEnabled || !drawingArmed) return;
                drawing = false;
                points.push(getBoardCoords(evt));
                drawPreviewStroke();
                sendStroke();
            }}

            function showTextDialog() {{
                return new Promise(resolve => {{
                    const close = (value) => {{
                        textDialog.classList.remove('visible');
                        textDialog.setAttribute('aria-hidden', 'true');
                        const cleaned = (value || '').trim();
                        textInput.value = '';
                        cleanup();
                        resolve(cleaned || null);
                    }};

                    const onCancel = () => close(null);
                    const onSave = () => close(textInput.value);
                    const onKeyDown = (evt) => {{
                        if (evt.key === 'Escape') {{
                            evt.preventDefault();
                            onCancel();
                        }}
                        if ((evt.key === 'Enter' && (evt.ctrlKey || evt.metaKey))) {{
                            evt.preventDefault();
                            onSave();
                        }}
                    }};
                    const onBackdrop = (evt) => {{
                        if (evt.target === textDialog) {{
                            onCancel();
                        }}
                    }};
                    const cleanup = () => {{
                        textCancel.removeEventListener('click', onCancel);
                        textSave.removeEventListener('click', onSave);
                        textDialog.removeEventListener('keydown', onKeyDown);
                        textDialog.removeEventListener('click', onBackdrop);
                    }};

                    textDialog.classList.add('visible');
                    textDialog.removeAttribute('aria-hidden');
                    textCancel.addEventListener('click', onCancel);
                    textSave.addEventListener('click', onSave);
                    textDialog.addEventListener('keydown', onKeyDown);
                    textDialog.addEventListener('click', onBackdrop);
                    textInput.focus();
                }});
            }}

            function handleText() {{
                if (!editingEnabled) return;
                showTextDialog().then(text => {{
                    if (!text) return;
                    setStatus('Click on the board to place text');
                    const handler = (evt) => {{
                        canvas.removeEventListener('click', handler);
                        const [x, y] = getBoardCoords(evt);
                        api('/api/text', {{ text, position: [x, y], color: sessionColor, size: textSize }})
                            .then(result => {{
                                if (result.status >= 400) {{
                                    setStatus(result.data.message || 'Unable to place text', true);
                                }} else {{
                                    setStatus('Text placed');
                                }}
                            }})
                            .catch(() => setStatus('Network error', true));
                    }};
                    canvas.addEventListener('click', handler, {{ once: true }});
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

            function setDrawingArmed(value) {{
                drawingArmed = !!value && editingEnabled;
                drawBtn.textContent = drawingArmed ? 'Stop Drawing' : 'Start Drawing';
                drawBtn.classList.toggle('ghost', !drawingArmed);
                drawBtn.classList.toggle('secondary', drawingArmed);
            }}

            function applyStoredTextSize(serverSize) {{
                const normalizedServerSize = normalizeTextSize(serverSize, textSize);
                const stored = localStorage.getItem('whiteboardTextSize');
                const storedSize = stored ? normalizeTextSize(stored, NaN) : NaN;

                if (Number.isFinite(storedSize) && storedSize === normalizedServerSize) {{
                    setTextSize(normalizedServerSize, {{ persist: true }});
                    return;
                }}

                if (Number.isFinite(storedSize) && storedSize !== normalizedServerSize) {{
                    localStorage.removeItem('whiteboardTextSize');
                }}

                setTextSize(normalizedServerSize, {{ persist: false }});
            }}

            function handleTokenSubmit() {{
                applyToken(tokenInput.value);
                setStatus(currentToken ? 'Token saved' : 'Token cleared');
            }}

            function handleRefresh() {{
                refreshPreview();
                setStatus('Preview refreshed');
            }}

            function syncStatus() {{
                fetch('/api/status')
                    .then(resp => resp.json())
                    .then(data => {{
                        editingEnabled = !!data.editing_enabled;
                        textSize = parseFloat(data.text_size || textSize) || textSize;
                        updateBoardGeometry(
                            {{ width: (data.board_size || [])[0], height: (data.board_size || [])[1] }},
                            {{ x: (data.board_origin || [])[0], y: (data.board_origin || [])[1] }}
                        );
                        undoBtn.disabled = !editingEnabled;
                        textBtn.disabled = !editingEnabled;
                        drawBtn.disabled = !editingEnabled;
                        textSizeSelect.disabled = !editingEnabled;
                        applyStoredTextSize(textSize);
                        setDrawingArmed(editingEnabled && drawingArmed);
                        setStatus(editingEnabled ? 'Editing enabled' : 'Editing disabled');
                        if (!data.use_mjpeg) {{
                            setTimeout(refreshPreview, refreshDelay);
                        }}
                    }})
                    .catch(() => setStatus('Unable to fetch status', true));
            }}

            window.addEventListener('resize', resizeCanvas);
            canvas.addEventListener('pointerdown', handlePointerDown);
            canvas.addEventListener('pointermove', handlePointerMove);
            canvas.addEventListener('pointerup', handlePointerUp);
            canvas.addEventListener('pointercancel', (evt) => {{
                removeActivePointer(evt);
                endPan();
                endPinch();
                drawing = false;
                clearPreviewStroke();
            }});
            canvas.addEventListener('pointerleave', (evt) => {{
                removeActivePointer(evt);
                if (isPanning) {{
                    endPan();
                }}
                if (drawing) {{
                    handlePointerUp(evt);
                }}
            }});
            surface.addEventListener('wheel', handleWheel, {{ passive: false }});
            surface.addEventListener('contextmenu', (evt) => evt.preventDefault());
            textBtn.addEventListener('click', handleText);
            undoBtn.addEventListener('click', handleUndo);
            drawBtn.addEventListener('click', () => setDrawingArmed(!drawingArmed));
            refreshBtn.addEventListener('click', handleRefresh);
            tokenInput.addEventListener('change', handleTokenSubmit);
            tokenInput.addEventListener('keyup', (evt) => {{
                if (evt.key === 'Enter') {{
                    handleTokenSubmit();
                }}
            }});
            textSizeSelect.addEventListener('change', () => {{
                setTextSize(normalizeTextSize(textSizeSelect.value, textSize));
            }});

            resizeCanvas();
            sessionColor = createSessionColor();
            updateSessionColorDisplay();
            applyToken(new URLSearchParams(window.location.search).get('token') || localStorage.getItem('whiteboardToken') || '');
            syncStatus();
            refreshPreview();
        }})();
    </script>
    """


def build_player_page(
    board_size: tuple[int, int],
    board_origin: tuple[float, float],
    refresh_ms: int,
    use_mjpeg: bool,
    token: str | None = None,
) -> str:
    params = {}
    if token:
        params["token"] = token
    query = urlencode(params)
    query_suffix = f"?{query}" if query else ""
    width, height = board_size
    origin_x, origin_y = board_origin
    options_html = "\n".join(
        f'                    <option value="{size}"{' selected' if size == DEFAULT_TEXT_SIZE else ''}>{size}</option>'
        for size in TEXT_SIZES
    )
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset='utf-8'>
        <title>Player Whiteboard</title>
        {_style_block()}
    </head>
    <body>
        <div id="toolbar">
            <div class="field">
                <label for="tokenInput" style="font-weight:700;">Access Token</label>
                <input type="text" id="tokenInput" placeholder="Paste GM token" />
            </div>
            <div class="field" aria-label="Session color">
                <span style="font-weight:700;">Session Color</span>
                <span id="colorSwatch"></span>
                <span id="colorValue" style="font-weight:700;">--</span>
            </div>
            <div class="field">
                <label for="textSizeSelect" style="font-weight:700;">Text Size</label>
                <select id="textSizeSelect">
{options_html}
                </select>
            </div>
            <button id="drawBtn" class="ghost">Start Drawing</button>
            <button id="textBtn">Place Text</button>
            <button id="undoBtn">Undo</button>
            <button id="refreshBtn" class="ghost">Refresh Preview</button>
        </div>
        <div id="boardContainer">
            <div id="boardSurface">
                <img id="boardPreview" src="/board.png{query_suffix}" alt="Whiteboard preview" />
                <canvas id="boardCanvas" width="{width}" height="{height}"></canvas>
            </div>
        </div>
        <div id="status">Loading...</div>
        <div id="textDialog" class="modal" role="dialog" aria-modal="true" aria-hidden="true">
            <div class="modal-card">
                <h3>Place Text</h3>
                <p>Enter text to place on the board. Use Ctrl+Enter or Cmd+Enter to save.</p>
                <textarea id="textInput" placeholder="Type your text here..." aria-label="Text to place"></textarea>
                <div class="actions">
                    <button type="button" id="textCancel" class="cancel">Cancel</button>
                    <button type="button" id="textSave" class="save">Save</button>
                </div>
            </div>
        </div>
        {_script_block(width, height, origin_x, origin_y, refresh_ms, use_mjpeg, TEXT_SIZES, DEFAULT_TEXT_SIZE)}
    </body>
    </html>
    """

