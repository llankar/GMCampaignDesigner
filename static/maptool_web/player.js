(() => {
  const statusEl = document.getElementById('status');
  const mapImg = document.getElementById('mapImage');
  const tokenLayer = document.getElementById('tokenLayer');
  const drawLayer = document.getElementById('drawLayer');
  const authToken = window.MAP_REMOTE_TOKEN || '';
  const tokenMenu = document.getElementById('tokenMenu');

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

  function normalizeAngle(angle) {
    const value = Number(angle);
    return Number.isFinite(value) ? ((value % 360) + 360) % 360 : 0;
  }

  function hideTokenMenu() {
    if (!tokenMenu) return;
    tokenMenu.style.display = 'none';
    tokenMenu.setAttribute('aria-hidden', 'true');
    tokenMenu.innerHTML = '';
  }

  function showTokenMenu(ev, token) {
    if (!lastStatus?.editing_enabled || !tokenMenu) return;
    ev.preventDefault();
    ev.stopPropagation();
    const actions = [
      ['Set Angle…', () => promptTokenFacing(token)],
      ['Rotate Clockwise 45°', () => rotateTokenFacing(token, 45)],
      ['Rotate Counterclockwise 45°', () => rotateTokenFacing(token, -45)],
      ['Face Right (0°)', () => setTokenFacing(token, 0)],
      ['Face Down (90°)', () => setTokenFacing(token, 90)],
      ['Face Left (180°)', () => setTokenFacing(token, 180)],
      ['Face Up (270°)', () => setTokenFacing(token, 270)],
    ];
    tokenMenu.innerHTML = '';
    actions.forEach(([label, action]) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.textContent = label;
      button.addEventListener('click', () => {
        hideTokenMenu();
        action();
      });
      tokenMenu.appendChild(button);
    });
    tokenMenu.style.left = `${Math.min(ev.clientX, window.innerWidth - 190)}px`;
    tokenMenu.style.top = `${Math.min(ev.clientY, window.innerHeight - 240)}px`;
    tokenMenu.style.display = 'block';
    tokenMenu.setAttribute('aria-hidden', 'false');
  }

  function renderTokens(status) {
    if (!status || !Array.isArray(status.tokens)) return;
    const retained = new Set(status.tokens.map((token) => String(token.id)));
    tokenLayer.querySelectorAll('.token').forEach((node) => {
      if (!retained.has(node.dataset.tokenId || '')) node.remove();
    });
    const rect = mapImg.getBoundingClientRect();
    const scaleX = status.render_size[0] ? status.render_size[0] / rect.width : 1;
    const scaleY = status.render_size[1] ? status.render_size[1] / rect.height : 1;
    status.tokens.forEach((token) => {
      const tokenId = String(token.id);
      let el = Array.from(tokenLayer.querySelectorAll('.token'))
        .find((node) => node.dataset.tokenId === tokenId);
      if (!el) {
        el = document.createElement('div');
        el.className = 'token';
        el.dataset.tokenId = tokenId;
        const label = document.createElement('span');
        label.style.cssText = 'color:#0b1220;position:relative;z-index:2';
        el.appendChild(label);
        const arrow = document.createElement('div');
        arrow.className = 'facingArrow';
        el.appendChild(arrow);
        const handle = document.createElement('div');
        handle.className = 'facingHandle';
        el.appendChild(handle);
        el.draggable = false;
        tokenLayer.appendChild(el);
      }
      const mediaUrl = token.media_url
        ? token.media_url + (authToken ? `?token=${encodeURIComponent(authToken)}` : '')
        : '';
      const mediaKind = token.media_type === 'video' ? 'video' : 'img';
      let media = el.querySelector('video, img');
      if (mediaUrl && (!media || media.tagName.toLowerCase() !== mediaKind || el.dataset.mediaUrl !== mediaUrl)) {
        if (media) media.remove();
        media = document.createElement(mediaKind);
        media.src = mediaUrl;
        media.alt = token.label || 'Token';
        media.draggable = false;
        media.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;object-fit:cover;border-radius:10px;pointer-events:none';
        el.prepend(media);
        el.dataset.mediaUrl = mediaUrl;
        if (mediaKind === 'video') {
          media.muted = media.defaultMuted = media.loop = media.autoplay = media.playsInline = true;
          media.setAttribute('muted', '');
          media.setAttribute('playsinline', '');
          media.play().catch(() => {
            document.addEventListener('pointerdown', () => media.play().catch(() => {}), { once: true });
          });
        }
      }
      const label = el.querySelector('span');
      if (label) label.textContent = token.label || 'PC';
      const screenX = (token.screen_position?.[0] || 0) / scaleX;
      const screenY = (token.screen_position?.[1] || 0) / scaleY;
      const size = (token.screen_size || 48) / Math.max(scaleX, scaleY);
      el.style.transform = `translate(${screenX}px, ${screenY}px)`;
      el.style.width = `${size}px`;
      el.style.height = `${size}px`;
      el.style.borderColor = token.border_color || '#0ea5e9';
      el.style.color = token.border_color || '#0ea5e9';
      const facingAngle = normalizeAngle(token.facing_angle);
      const arrow = el.querySelector('.facingArrow');
      const handle = el.querySelector('.facingHandle');
      if (arrow) arrow.style.transform = `rotate(${facingAngle}deg)`;
      if (handle) {
        handle.style.transform = `rotate(${facingAngle}deg) translate(${size * 0.64}px, 0) rotate(${-facingAngle}deg)`;
        handle.onpointerdown = (ev) => startFacingDrag(ev, token, el);
      }
      el.oncontextmenu = (ev) => showTokenMenu(ev, token);
      el.onpointerdown = (ev) => {
        if (ev.target === handle) return;
        startDrag(ev, token);
      };
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

  function tokenCenterScreen(token) {
    const rect = mapImg.getBoundingClientRect();
    const scaleX = lastStatus.render_size[0] ? lastStatus.render_size[0] / rect.width : 1;
    const scaleY = lastStatus.render_size[1] ? lastStatus.render_size[1] / rect.height : 1;
    const screenX = (token.screen_position?.[0] || 0) / scaleX;
    const screenY = (token.screen_position?.[1] || 0) / scaleY;
    const size = (token.screen_size || 48) / Math.max(scaleX, scaleY);
    return { x: screenX + size / 2, y: screenY + size / 2 };
  }

  function angleFromScreenPoint(token, point) {
    const center = tokenCenterScreen(token);
    return normalizeAngle(Math.atan2(point.y - center.y, point.x - center.x) * 180 / Math.PI);
  }

  function startFacingDrag(ev, token) {
    if (!lastStatus?.editing_enabled) return;
    ev.preventDefault();
    ev.stopPropagation();
    hideTokenMenu();
    const rect = mapImg.getBoundingClientRect();
    const apply = (e) => {
      const point = { x: e.clientX - rect.left, y: e.clientY - rect.top };
      const angle = angleFromScreenPoint(token, point);
      token.facing_angle = angle;
      setTokenFacing(token, angle);
    };
    const upHandler = () => {
      window.removeEventListener('pointermove', apply);
      window.removeEventListener('pointerup', upHandler);
    };
    window.addEventListener('pointermove', apply);
    window.addEventListener('pointerup', upHandler);
    apply(ev);
  }

  function promptTokenFacing(token) {
    const current = Math.round(normalizeAngle(token.facing_angle));
    const value = prompt('Facing angle in degrees (0 right, 90 down, 180 left, 270 up)', `${current}`);
    if (value === null) return;
    const angle = Number(value);
    if (!Number.isFinite(angle)) return;
    setTokenFacing(token, angle);
  }

  function rotateTokenFacing(token, delta) {
    setTokenFacing(token, normalizeAngle(token.facing_angle + delta));
  }

  function setTokenFacing(token, angle) {
    const normalized = normalizeAngle(angle);
    token.facing_angle = normalized;
    fetch('/api/tokens/facing', {
      method: 'POST',
      headers: apiHeaders(),
      body: JSON.stringify({ token_id: token.id, facing_angle: normalized }),
    }).catch(() => {});
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
  window.addEventListener('click', hideTokenMenu);
  window.addEventListener('keydown', (ev) => { if (ev.key === 'Escape') hideTokenMenu(); });

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
