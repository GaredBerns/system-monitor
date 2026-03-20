/**
 * ui.js — UI utilities: notifications, command palette, keyboard shortcuts
 */

/* ──────────────────────── NOTIFICATIONS ──────────────────────── */
let _notifStack = 0;

function showNotification(msg, type = 'accent') {
  const themes = {
    accent: { bg: 'rgba(0,212,255,.1)',  border: 'rgba(0,212,255,.4)',  color: '#00d4ff' },
    green:  { bg: 'rgba(0,245,155,.1)', border: 'rgba(0,245,155,.4)', color: '#00f59b' },
    red:    { bg: 'rgba(255,61,90,.1)', border: 'rgba(255,61,90,.4)', color: '#ff3d5a' },
    yellow: { bg: 'rgba(255,210,0,.1)', border: 'rgba(255,210,0,.4)', color: '#ffd200' },
    purple: { bg: 'rgba(176,125,250,.1)', border: 'rgba(176,125,250,.4)', color: '#b07dfa' },
  };
  const t = themes[type] || themes.accent;
  const n = document.createElement('div');
  const offset = 20 + _notifStack * 62;
  Object.assign(n.style, {
    position: 'fixed',
    top: offset + 'px',
    right: '20px',
    background: t.bg,
    border: `1px solid ${t.border}`,
    color: t.color,
    padding: '12px 20px',
    borderRadius: '10px',
    fontSize: '13px',
    fontWeight: '500',
    zIndex: '9999',
    backdropFilter: 'blur(14px)',
    boxShadow: '0 8px 32px rgba(0,0,0,.4)',
    animation: 'fadeIn .25s ease-out',
    fontFamily: 'Inter, sans-serif',
    maxWidth: '360px',
    wordBreak: 'break-word',
    cursor: 'pointer',
    userSelect: 'none',
  });
  n.textContent = msg;
  n.addEventListener('click', () => {
    n.style.transition = 'all .2s ease-out';
    n.style.opacity = '0';
    n.style.transform = 'translateX(20px)';
    _notifStack = Math.max(0, _notifStack - 1);
    setTimeout(() => n.remove(), 200);
  });
  document.body.appendChild(n);
  _notifStack++;

  setTimeout(() => {
    n.style.transition = 'all .3s ease-out';
    n.style.opacity = '0';
    n.style.transform = 'translateX(20px)';
    _notifStack = Math.max(0, _notifStack - 1);
    setTimeout(() => n.remove(), 300);
  }, 4500);
}

/* ──────────────────────── KEYBOARD SHORTCUTS ──────────────────────── */
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    document.querySelectorAll('.modal-overlay.active').forEach(m => m.classList.remove('active'));
    const cp = document.getElementById('cmdPalette');
    if (cp) cp.style.display = 'none';
  }
  if (e.ctrlKey && e.key === 'k') {
    e.preventDefault();
    toggleCommandPalette();
  }
});

/* ──────────────────────── COMMAND PALETTE ──────────────────────── */
const PALETTE_COMMANDS = [
  { label: 'Dashboard',      icon: '⬛', url: '/' },
  { label: 'Devices',        icon: '💻', url: '/devices' },
  { label: 'Console',        icon: '⌨️',  url: '/console' },
  { label: 'Payloads',       icon: '📦', url: '/payloads' },
  { label: 'Scheduler',      icon: '⏱',  url: '/scheduler' },
  { label: 'Auto-Reg',       icon: '👤', url: '/autoreg' },
  { label: 'Laboratory',     icon: '🔬', url: '/laboratory' },
  { label: 'Temp Mail',      icon: '✉️',  url: '/tempmail' },
  { label: 'Logs',           icon: '📋', url: '/logs' },
  { label: 'Settings',       icon: '⚙️',  url: '/settings' },
  { label: 'Export Agents',  icon: '📁', url: '/api/export/agents', download: true },
  { label: 'Export Logs',    icon: '📁', url: '/api/export/logs', download: true },
  {
    label: 'Kill All Agents', icon: '💀',
    action: () => {
      if (!confirm('KILL ALL AGENTS? This cannot be undone.')) return;
      fetch('/api/task/broadcast', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ type: 'kill', payload: 'self-destruct', target: 'all' }),
      }).then(() => showNotification('Kill signal sent', 'red'));
    },
  },
  {
    label: 'Broadcast :start', icon: '🚀',
    action: () => {
      fetch('/api/task/broadcast', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ type: 'cmd', payload: ':start', target: 'all' }),
      }).then(r => r.json()).then(d => showNotification(`Dispatched to ${d.count} agents`, 'green'));
    },
  },
  { label: 'Refresh Page', icon: '🔄', action: () => location.reload() },
  { label: 'Logout',       icon: '🚪', url: '/logout' },
];

let _cpIdx = 0;

function _cpHighlight(items) {
  items.forEach((el, i) => {
    const active = i === _cpIdx;
    el.style.background = active ? 'var(--accent-glow)' : '';
    el.style.color       = active ? 'var(--accent)'     : 'var(--text)';
    el.style.borderLeft  = active ? '2px solid var(--accent)' : '2px solid transparent';
    if (active) el.scrollIntoView({ block: 'nearest' });
  });
}

function toggleCommandPalette() {
  let cp = document.getElementById('cmdPalette');
  if (!cp) {
    cp = document.createElement('div');
    cp.id = 'cmdPalette';
    cp.style.cssText = 'display:none;position:fixed;inset:0;background:rgba(0,0,0,.7);z-index:10000;backdrop-filter:blur(8px);align-items:flex-start;justify-content:center;padding-top:18vh';

    cp.innerHTML = `
      <div style="background:var(--bg-card);border:1px solid var(--border-light);border-radius:16px;width:540px;max-width:92vw;box-shadow:var(--shadow-lg);overflow:hidden;animation:modalIn .2s ease-out">
        <div style="position:relative;padding:4px 16px 4px 48px;border-bottom:1px solid var(--border)">
          <span style="position:absolute;left:16px;top:50%;transform:translateY(-50%);font-size:16px;color:var(--text-dim)">⌕</span>
          <input id="cpInput" type="text" placeholder="Search commands…"
            style="width:100%;background:transparent;border:none;padding:14px 0;font-size:14px;color:var(--text-bright);font-family:var(--font-mono);outline:none">
        </div>
        <div id="cpResults" style="max-height:320px;overflow-y:auto;padding:6px 0"></div>
        <div style="padding:8px 16px;border-top:1px solid var(--border);display:flex;gap:16px;font-size:10px;color:var(--text-muted);font-family:var(--font-mono)">
          <span><kbd style="background:var(--bg-input);padding:1px 5px;border-radius:3px;border:1px solid var(--border)">↑↓</kbd> navigate</span>
          <span><kbd style="background:var(--bg-input);padding:1px 5px;border-radius:3px;border:1px solid var(--border)">↵</kbd> open</span>
          <span><kbd style="background:var(--bg-input);padding:1px 5px;border-radius:3px;border:1px solid var(--border)">Esc</kbd> close</span>
        </div>
      </div>`;

    cp.addEventListener('click', e => { if (e.target === cp) cp.style.display = 'none'; });
    document.body.appendChild(cp);

    const input = cp.querySelector('#cpInput');
    input.addEventListener('input', () => { _cpIdx = 0; _renderPalette(input.value); });
    input.addEventListener('keydown', e => {
      const items = cp.querySelectorAll('.cp-item');
      if      (e.key === 'ArrowDown') { e.preventDefault(); _cpIdx = Math.min(_cpIdx + 1, items.length - 1); _cpHighlight(items); }
      else if (e.key === 'ArrowUp')   { e.preventDefault(); _cpIdx = Math.max(_cpIdx - 1, 0); _cpHighlight(items); }
      else if (e.key === 'Enter')     { e.preventDefault(); if (items[_cpIdx]) items[_cpIdx].click(); }
    });
  }

  if (cp.style.display !== 'flex') {
    cp.style.display = 'flex';
    const input = cp.querySelector('#cpInput');
    input.value = '';
    input.focus();
    _renderPalette('');
  } else {
    cp.style.display = 'none';
  }
}

function _runCommand(cmd) {
  document.getElementById('cmdPalette').style.display = 'none';
  if (cmd.action) { cmd.action(); return; }
  if (cmd.download) { window.location.href = cmd.url; return; }
  location.href = cmd.url;
}

function _renderPalette(query) {
  const container = document.getElementById('cpResults');
  const q = query.toLowerCase().trim();
  const filtered = q
    ? PALETTE_COMMANDS.filter(c => c.label.toLowerCase().includes(q))
    : PALETTE_COMMANDS;

  container.innerHTML = filtered.map((cmd, i) => `
    <div class="cp-item" style="padding:9px 16px 9px 18px;cursor:pointer;display:flex;align-items:center;gap:12px;transition:all .12s;font-size:13.5px;color:var(--text);border-left:2px solid transparent"
      onmouseenter="this.style.background='var(--accent-glow)';this.style.color='var(--accent)';this.style.borderLeft='2px solid var(--accent)'"
      onmouseleave="this.style.background='';this.style.color='var(--text)';this.style.borderLeft='2px solid transparent'"
      onclick="_runCmdByIndex(${i}, ${JSON.stringify(q)})">
      <span style="font-size:15px;min-width:22px;text-align:center">${cmd.icon}</span>
      <span style="font-weight:500">${cmd.label}</span>
      ${cmd.url ? `<span style="margin-left:auto;font-size:10px;color:var(--text-muted);font-family:var(--font-mono)">${cmd.url}</span>` : ''}
    </div>`).join('');

  setTimeout(() => _cpHighlight(container.querySelectorAll('.cp-item')), 0);
}

// Helper: run by index within filtered results
function _runCmdByIndex(idx, query) {
  const q = query.toLowerCase().trim();
  const filtered = q
    ? PALETTE_COMMANDS.filter(c => c.label.toLowerCase().includes(q))
    : PALETTE_COMMANDS;
  if (filtered[idx]) _runCommand(filtered[idx]);
}
