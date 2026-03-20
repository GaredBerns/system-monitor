/**
 * socket.js — SocketIO connection management
 * Initializes connection and updates UI status indicator.
 */

const socket = io({ transports: ['websocket', 'polling'] });

function _setConnStatus(ok) {
  const dot = document.getElementById('connDot');
  const lbl = document.getElementById('connLabel');
  if (!dot || !lbl) return;
  if (ok) {
    dot.className = 'conn-dot ok';
    lbl.textContent = 'connected';
  } else {
    dot.className = 'conn-dot err';
    lbl.textContent = 'offline';
  }
}

socket.on('connect',       () => _setConnStatus(true));
socket.on('disconnect',    () => _setConnStatus(false));
socket.on('connect_error', () => _setConnStatus(false));

socket.on('agent_update', data => {
  if (typeof showNotification !== 'function') return;
  if (data.action === 'register')
    showNotification(`New agent: ${data.hostname || data.id?.slice(0, 8)}`, 'green');
  else if (data.action === 'offline')
    showNotification(`Agent offline: ${data.hostname || data.id?.slice(0, 8)}`, 'red');
});
