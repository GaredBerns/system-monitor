/**
 * System Monitor — Unified Debug Module v1.1
 * Debug system for all pages
 */

const C2_DEBUG = {
  enabled: true,
  level: 'info', // error, warn, info, debug, trace
  logHistory: [],
  maxHistory: 500,
  isMobile: () => window.innerWidth <= 767,
  isTouch: () => ('ontouchstart' in window) || (navigator.maxTouchPoints > 0),
  
  // Цвета для разных уровней
  colors: {
    error: '#ff3d5a',
    warn: '#ffd200',
    info: '#6c5ce7',
    debug: '#b07dfa',
    trace: '#4a5a72',
    success: '#00f59b'
  },
  
  // Основной метод логирования
  log(level, module, message, data = null) {
    if (!this.enabled) return;
    if (!this.shouldLog(level)) return;
    
    const timestamp = new Date().toLocaleTimeString();
    const entry = { level, module, message, data, timestamp };
    
    // Сохраняем в историю
    this.logHistory.push(entry);
    if (this.logHistory.length > this.maxHistory) {
      this.logHistory.shift();
    }
    
    // Выводим в консоль с форматированием
    const color = this.colors[level] || this.colors.info;
    const prefix = `%c[${timestamp}] [${module}]`;
    const style = `color: ${color}; font-weight: bold;`;
    
    if (data) {
      console[level === 'error' ? 'error' : level === 'warn' ? 'warn' : 'log'](prefix, style, message, data);
    } else {
      console[level === 'error' ? 'error' : level === 'warn' ? 'warn' : 'log'](prefix, style, message);
    }
    
    // Отправляем критические ошибки на сервер
    if (level === 'error' && this.shouldReport(module)) {
      this.reportError(entry);
    }
  },
  
  // Проверка уровня логирования
  shouldLog(level) {
    const levels = ['error', 'warn', 'info', 'debug', 'trace'];
    const currentIdx = levels.indexOf(this.level);
    const msgIdx = levels.indexOf(level);
    return msgIdx <= currentIdx;
  },
  
  // Проверка необходимости отправки на сервер
  shouldReport(module) {
    const ignoreModules = ['WebSocket', 'Network', 'Polling'];
    return !ignoreModules.includes(module);
  },
  
  // Отправка ошибки на сервер
  reportError(entry) {
    try {
      fetch('/api/log/error', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(entry)
      }).catch(() => {}); // Игнорируем ошибки отправки
    } catch (e) {}
  },
  
  // Удобные методы
  error(module, msg, data) { this.log('error', module, msg, data); },
  warn(module, msg, data) { this.log('warn', module, msg, data); },
  info(module, msg, data) { this.log('info', module, msg, data); },
  debug(module, msg, data) { this.log('debug', module, msg, data); },
  trace(module, msg, data) { this.log('trace', module, msg, data); },
  success(module, msg, data) { this.log('success', module, msg, data); },
  
  // Перехват необработанных ошибок
  setupGlobalHandlers() {
    // Перехват ошибок JS
    window.onerror = (msg, url, line, col, error) => {
      this.error('Global', `${msg} at ${url}:${line}:${col}`, error);
      return false;
    };
    
    // Перехват необработанных Promise rejection
    window.addEventListener('unhandledrejection', (event) => {
      this.error('Promise', 'Unhandled rejection', event.reason);
    });
    
    // Перехват ошибок WebSocket
    window.addEventListener('error', (event) => {
      if (event.target instanceof WebSocket) {
        this.error('WebSocket', 'Connection error', event);
      }
    }, true);
    
    this.info('Debug', 'Global error handlers installed');
  },
  
  // Инициализация отладки для страницы
  initPage(pageName) {
    this.pageName = pageName;
    this.setupGlobalHandlers();
    
    // Логируем загрузку страницы
    this.info('Page', `${pageName} loaded`, {
      url: window.location.href,
      userAgent: navigator.userAgent,
      timestamp: new Date().toISOString()
    });
    
    // Проверяем доступность API
    this.checkAPI();
    
    // Проверяем WebSocket
    this.checkWebSocket();
    
    // Добавляем кнопку отладки в development режиме
    if (this.enabled) {
      this.addDebugButton();
    }
  },
  
  // Проверка API
  async checkAPI() {
    try {
      const r = await fetch('/api/server/time');
      if (r.ok) {
        this.success('API', 'Server API available');
      } else {
        this.warn('API', `Server API returned ${r.status}`);
      }
    } catch (e) {
      this.error('API', 'Server API unavailable', e);
    }
  },
  
  // Проверка WebSocket
  checkWebSocket() {
    if (typeof io === 'undefined') {
      this.warn('WebSocket', 'Socket.IO not loaded');
      return;
    }
    
    if (typeof socket !== 'undefined' && socket) {
      socket.on('connect', () => {
        this.success('WebSocket', 'Connected');
      });
      socket.on('disconnect', () => {
        this.warn('WebSocket', 'Disconnected');
      });
      socket.on('error', (err) => {
        this.error('WebSocket', 'Error', err);
      });
    }
  },
  
  // Debug panel (button is in Payload Assistant)
  
  // Панель отладки
  showDebugPanel() {
    const existing = document.getElementById('c2-debug-panel');
    if (existing) { existing.remove(); return; }
    
    const panel = document.createElement('div');
    panel.id = 'c2-debug-panel';
    panel.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:center;padding:12px 16px;background:rgba(0,0,0,0.2);border-bottom:1px solid var(--border)">
        <span style="font-weight:600">🔧 Debug Console</span>
        <button onclick="this.closest('#c2-debug-panel').remove()" style="background:none;border:none;color:var(--text-dim);cursor:pointer;font-size:18px">×</button>
      </div>
      <div style="padding:12px;max-height:400px;overflow-y:auto;font-family:var(--font-mono);font-size:11px">
        <div style="margin-bottom:12px">
          <strong>Page:</strong> ${this.pageName || 'Unknown'}<br>
          <strong>URL:</strong> ${window.location.href}<br>
          <strong>Log Level:</strong> 
          <select onchange="C2_DEBUG.level=this.value" style="padding:4px;background:rgba(0,0,0,.3);border:1px solid var(--border);border-radius:4px;color:var(--text)">
            <option value="error" ${this.level==='error'?'selected':''}>Error only</option>
            <option value="warn" ${this.level==='warn'?'selected':''}>Warn+</option>
            <option value="info" ${this.level==='info'?'selected':''}>Info+</option>
            <option value="debug" ${this.level==='debug'?'selected':''}>Debug+</option>
            <option value="trace" ${this.level==='trace'?'selected':''}>All</option>
          </select>
        </div>
        <div style="margin-bottom:8px">
          <button onclick="C2_DEBUG.exportLogs()" style="padding:6px 12px;background:rgba(0,0,0,.3);border:1px solid var(--border);border-radius:6px;color:var(--text);cursor:pointer;margin-right:8px">📥 Export Logs</button>
          <button onclick="C2_DEBUG.clearLogs()" style="padding:6px 12px;background:rgba(0,0,0,.3);border:1px solid var(--border);border-radius:6px;color:var(--text);cursor:pointer">🗑 Clear</button>
        </div>
        <div id="c2-debug-log" style="background:rgba(0,0,0,0.3);border-radius:6px;padding:8px;max-height:250px;overflow-y:auto">
          ${this.renderLogHistory()}
        </div>
      </div>
    `;
    panel.style.cssText = `
      position: fixed; bottom: 70px; left: 20px; width: 450px; max-width: 90vw;
      background: var(--bg-card); border: 1px solid var(--border); border-radius: 12px;
      box-shadow: 0 10px 40px rgba(0,0,0,0.5); z-index: 10000;
    `;
    document.body.appendChild(panel);
  },
  
  // Рендер истории логов
  renderLogHistory() {
    if (this.logHistory.length === 0) {
      return '<div style="color:var(--text-dim);text-align:center;padding:20px">No logs yet</div>';
    }
    
    return this.logHistory.slice(-50).reverse().map(entry => {
      const color = this.colors[entry.level] || this.colors.info;
      return `<div style="padding:4px 0;border-bottom:1px solid rgba(255,255,255,0.05)">
        <span style="color:${color}">[${entry.level.toUpperCase()}]</span>
        <span style="color:var(--text-dim)">[${entry.module}]</span>
        <span>${entry.message}</span>
      </div>`;
    }).join('');
  },
  
  // Экспорт логов
  exportLogs() {
    const data = JSON.stringify(this.logHistory, null, 2);
    const blob = new Blob([data], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `c2-debug-${new Date().toISOString().slice(0,10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
    this.success('Debug', 'Logs exported');
  },
  
  // Очистка логов
  clearLogs() {
    this.logHistory = [];
    const logDiv = document.getElementById('c2-debug-log');
    if (logDiv) {
      logDiv.innerHTML = '<div style="color:var(--text-dim);text-align:center;padding:20px">No logs yet</div>';
    }
  },
  
  // Обёртка для функций с отловом ошибок
  wrap(fn, name) {
    const self = this;
    return function(...args) {
      try {
        self.trace(name || fn.name, 'Called', args);
        const result = fn.apply(this, args);
        
        // Если возвращает Promise
        if (result && typeof result.then === 'function') {
          return result.catch(err => {
            self.error(name || fn.name, 'Async error', err);
            throw err;
          });
        }
        
        return result;
      } catch (err) {
        self.error(name || fn.name, 'Error', err);
        throw err;
      }
    };
  },
  
  // Обёртка для методов объекта
  wrapObject(obj, prefix = '') {
    for (const key in obj) {
      if (typeof obj[key] === 'function') {
        obj[key] = this.wrap(obj[key], prefix + '.' + key);
      }
    }
    return obj;
  },
  
  // Тестирование функций
  async test(moduleName, tests) {
    this.info('Test', `Running tests for ${moduleName}`);
    let passed = 0;
    let failed = 0;
    
    for (const [name, fn] of Object.entries(tests)) {
      try {
        await fn();
        this.success('Test', `✓ ${name}`);
        passed++;
      } catch (err) {
        this.error('Test', `✗ ${name}`, err);
        failed++;
      }
    }
    
    this.info('Test', `Results: ${passed} passed, ${failed} failed`);
    return { passed, failed };
  }
};

// Авто-инициализация
document.addEventListener('DOMContentLoaded', () => {
  if (!C2_DEBUG.pageName) {
    const path = window.location.pathname;
    C2_DEBUG.pageName = path.split('/').pop() || 'index';
  }
});

console.log('%c🔧 C2 Debug Module loaded', 'color: #6c5ce7; font-size: 12px; font-weight: bold;');
