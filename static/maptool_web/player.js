(() => {
  const statusEl = document.getElementById('status');
  const mapImg = document.getElementById('mapImage');
  const tokenLayer = document.getElementById('tokenLayer');
  const drawLayer = document.getElementById('drawLayer');
  const authToken = window.MAP_REMOTE_TOKEN || '';

  let lastStatus = null;
  let drawCtx = null;
  let drawing = false;
  let strokePoints = [];
  let strokeScreenPoints = [];

  function setStatus(text) {
    if (statusEl) statusEl.textContent = text;
  }

  function apiHeaders() {
    return authToken ? { 'Content-Type': 'application/json', 'X-Map-Token': authToken } : { 'Content-Type': 'application/json' };
  }

  function fetchStatus() {
    fetch('/api/status' + (authToken ? `?token=${encodeURIComponent(authToken)}` : ''))
      .then((resp) => resp.json())
      .then((data) => {
        lastStatus = data;
        updateView(data);
        scheduleNextStatus(data.refresh_ms || 500);
      })
      .catch(() => scheduleNextStatus(1000));
  }

  function scheduleNextStatus(delay) {
    setTimeout(fetchStatus, Math.max(200, delay || 500));
  }

  function ensureCanvasSize() {
    if (!lastStatus || !drawLayer) return;
    const rect = mapImg.getBoundingClientRect();
    drawLayer.width = rect.width;
    drawLayer.height = rect.height;
    drawCtx = drawLayer.getContext('2d');
    drawCtx.lineCap = 'round';
    drawCtx.lineJoin = 'round';
  }

  function renderTokens(status) {
    tokenLayer.innerHTML = '';
    if (!status || !Array.isArray(status.tokens)) return;
    const rect = mapImg.getBoundingClientRect();
    const scaleX = status.render_size[0] ? status.render_size[0] / rect.width : 1;
    const scaleY = status.render_size[1] ? status.render_size[1] / rect.height : 1;
    status.tokens.forEach((token) => {
      const el = document.createElement('div');
      el.className = 'token';
      el.textContent = token.label || 'PC';
      el.draggable = false;
      const screenX = (token.screen_position?.[0] || 0) / scaleX;
      const screenY = (token.screen_position?.[1] || 0) / scaleY;
      const size = (token.screen_size || 48) / Math.max(scaleX, scaleY);
      el.style.transform = `translate(${screenX}px, ${screenY}px)`;
      el.style.width = `${size}px`;
      el.style.height = `${size}px`;
      if (token.border_color) {
        el.style.borderColor = token.border_color;
      }
      el.addEventListener('pointerdown', (ev) => startDrag(ev, token));
      tokenLayer.appendChild(el);
    });
  }

  function updateView(status) {
    setStatus(status.editing_enabled ? 'Tap or drag to move PCs and draw.' : 'Remote editing disabled');
    ensureCanvasSize();
    renderTokens(status);
    if (status.use_mjpeg) {
      mapImg.src = '/stream.mjpg';
    } else {
      mapImg.src = `/map.png?ts=${Date.now()}`;
      mapImg.onload = () => setTimeout(() => (mapImg.src = `/map.png?ts=${Date.now()}`), status.refresh_ms || 500);
    }
  }

  function screenToWorld(point) {
    if (!lastStatus) return { x: 0, y: 0 };
    const rect = mapImg.getBoundingClientRect();
    const renderX = point.x * (lastStatus.render_size[0] / rect.width);
    const renderY = point.y * (lastStatus.render_size[1] / rect.height);
    const minX = lastStatus.render_offset?.[0] || 0;
    const minY = lastStatus.render_offset?.[1] || 0;
    const panX = lastStatus.pan?.[0] || 0;
    const panY = lastStatus.pan?.[1] || 0;
    const zoom = lastStatus.zoom || 1;
    return {
      x: (renderX + minX - panX) / zoom,
      y: (renderY + minY - panY) / zoom,
    };
  }

  function startDrag(ev, token) {
    if (!lastStatus?.editing_enabled) return;
    ev.preventDefault();
    const rect = mapImg.getBoundingClientRect();
    const start = { x: ev.clientX - rect.left, y: ev.clientY - rect.top };
    const moveHandler = (e) => {
      const pos = { x: e.clientX - rect.left, y: e.clientY - rect.top };
      moveToken(token, pos);
    };
    const upHandler = () => {
      window.removeEventListener('pointermove', moveHandler);
      window.removeEventListener('pointerup', upHandler);
    };
    window.addEventListener('pointermove', moveHandler);
    window.addEventListener('pointerup', upHandler);
    moveToken(token, start);
  }

  function moveToken(token, screenPoint) {
    const world = screenToWorld(screenPoint);
    fetch('/api/tokens/move', {
      method: 'POST',
      headers: apiHeaders(),
      body: JSON.stringify({ token_id: token.id, position: [world.x, world.y] }),
    }).catch(() => {});
  }

  function startDrawing(ev) {
    if (!lastStatus?.editing_enabled) return;
    drawing = true;
    strokePoints = [];
    strokeScreenPoints = [];
    addStrokePoint(ev);
  }

  function addStrokePoint(ev) {
    const rect = mapImg.getBoundingClientRect();
    const pt = { x: ev.clientX - rect.left, y: ev.clientY - rect.top };
    const world = screenToWorld(pt);
    strokePoints.push([world.x, world.y]);
    strokeScreenPoints.push(pt);
    if (strokeScreenPoints.length > 1 && drawCtx) {
      const last = strokeScreenPoints[strokeScreenPoints.length - 2];
      drawCtx.strokeStyle = '#e11d48';
      drawCtx.lineWidth = 6;
      drawCtx.beginPath();
      drawCtx.moveTo(last.x, last.y);
      drawCtx.lineTo(pt.x, pt.y);
      drawCtx.stroke();
    }
  }

  function stopDrawing() {
    if (!drawing) return;
    drawing = false;
    if (strokePoints.length < 2) return;
    fetch('/api/strokes', {
      method: 'POST',
      headers: apiHeaders(),
      body: JSON.stringify({ points: strokePoints, color: '#e11d48', width: 6 }),
    }).catch(() => {});
    if (drawCtx) {
      drawCtx.clearRect(0, 0, drawLayer.width, drawLayer.height);
    }
  }

  function addText(ev) {
    if (!lastStatus?.editing_enabled) return;
    const text = prompt('Enter annotation text');
    if (!text) return;
    const rect = mapImg.getBoundingClientRect();
    const pt = { x: ev.clientX - rect.left, y: ev.clientY - rect.top };
    const world = screenToWorld(pt);
    fetch('/api/text', {
      method: 'POST',
      headers: apiHeaders(),
      body: JSON.stringify({ text, position: [world.x, world.y], color: '#e2e8f0', size: 28 }),
    }).catch(() => {});
  }

  mapImg.addEventListener('load', ensureCanvasSize);
  window.addEventListener('resize', ensureCanvasSize);
  mapImg.addEventListener('dragstart', (ev) => ev.preventDefault());
  tokenLayer.addEventListener('dragstart', (ev) => ev.preventDefault());

  drawLayer.addEventListener('pointerdown', (ev) => {
    if (ev.pointerType === 'pen' || ev.pointerType === 'touch') {
      startDrawing(ev);
    }
  });
  drawLayer.addEventListener('pointermove', (ev) => {
    if (drawing) addStrokePoint(ev);
  });
  drawLayer.addEventListener('pointerup', stopDrawing);
  drawLayer.addEventListener('pointerleave', stopDrawing);
  drawLayer.addEventListener('dblclick', addText);

  fetchStatus();
})();
