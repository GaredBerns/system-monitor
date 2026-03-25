/**
 * socket.js — SocketIO connection management v2.2
 * Initializes connection, updates UI status, global event bus.
 */

const socket = io({ transports: ['websocket', 'polling'], reconnectionDelay: 1000, reconnectionAttempts: Infinity });

// ── Connection status ──
function _setConnStatus(ok) {
  const dot = document.getElementById('connDot');
  const lbl = document.getElementById('connLabel');
  if (dot) dot.className = 'conn-dot ' + (ok ? 'ok' : 'err');
  if (lbl) lbl.textContent = ok ? 'connected' : 'offline';
  // Topbar WS status (dashboard)
  const wsDot = document.getElementById('wsDot');
  const wsText = document.getElementById('wsText');
  if (wsDot) wsDot.className = 'conn-dot ' + (ok ? 'ok' : 'err');
  if (wsText) wsText.textContent = ok ? 'Connected' : 'Disconnected';
  // Sidebar hint color
  const hint = document.querySelector('.sidebar-hint');
  if (hint) hint.style.color = ok ? '' : 'var(--red)';
}

let _reconnectTimer = null;
socket.on('connect', () => {
  _setConnStatus(true);
  if (_reconnectTimer) { clearTimeout(_reconnectTimer); _reconnectTimer = null; }
  const banner = document.getElementById('offlineBanner');
  if (banner) banner.classList.remove('visible');
});
socket.on('disconnect', () => {
  _setConnStatus(false);
  _reconnectTimer = setTimeout(() => {
    const banner = document.getElementById('offlineBanner');
    if (banner) banner.classList.add('visible');
    if (typeof showNotification === 'function') showNotification('Connection lost — reconnecting…', 'yellow', 3000);
  }, 3000);
});
socket.on('connect_error', () => _setConnStatus(false));

// ── Global agent_update handler ──
socket.on('agent_update', data => {
  if (typeof showNotification !== 'function') return;
  if (data.action === 'register') {
    showNotification(`✨ New agent: ${data.hostname || data.id?.slice(0, 8)}`, 'green');
    // Update nav agent count badge
    const badge = document.getElementById('navAgentCount');
    if (badge) badge.textContent = (parseInt(badge.textContent) || 0) + 1;
  } else if (data.action === 'offline') {
    showNotification(`⚠ Agent offline: ${data.hostname || data.id?.slice(0, 8)}`, 'red');
  }
});

// ── Global task_result handler ──
socket.on('task_result', data => {
  // Update task counter in page title badge if present
  const badge = document.getElementById('taskCountLabel');
  if (badge) {
    const cur = parseInt(badge.textContent) || 0;
    badge.textContent = (cur + 1) + ' tasks';
  }
});

// ── Ping/pong keepalive ──
setInterval(() => { if (socket.connected) socket.emit('ping'); }, 25000);

// ── Page visibility: reconnect on tab focus ──
document.addEventListener('visibilitychange', () => {
  if (!document.hidden && !socket.connected) socket.connect();
});
