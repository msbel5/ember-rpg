[CmdletBinding()]
param(
    [string]$GodotExe = "C:\Tools\Scoop\shims\godot.exe",
    [string]$ProjectPath = "C:\Users\msbel\projects\ember-rpg\godot-client",
    [string]$BackendPython = "C:\Users\msbel\projects\ember-rpg\.venv\Scripts\python.exe",
    [string]$BackendScript = "C:\Users\msbel\projects\ember-rpg\frp-backend\dev_server.py",
    [string]$BackendHealthUrl = "http://127.0.0.1:8741/game/health/campaign-client",
    [int]$BackendPort = 8741,
    [switch]$NoBackend,
    [switch]$WaitForBackend
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Test-BackendHealth {
    param([string]$Url)
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 2
        if ($response.StatusCode -ne 200) {
            return $false
        }
        $payload = $response.Content | ConvertFrom-Json
        return ($payload.ok -eq $true) -and ($payload.campaign_creation -eq $true) -and ($payload.campaign_runtime -eq $true) -and ($payload.campaign_save_load -eq $true) -and ($payload.websocket_transport -eq $true)
    }
    catch {
        return $false
    }
}

if (-not (Test-Path -LiteralPath $GodotExe)) {
    throw "Godot executable not found: $GodotExe"
}

if (-not (Test-Path -LiteralPath $ProjectPath)) {
    throw "Godot project path not found: $ProjectPath"
}

if (-not $NoBackend) {
    if (-not (Test-Path -LiteralPath $BackendPython)) {
        throw "Backend Python not found: $BackendPython"
    }
    if (-not (Test-Path -LiteralPath $BackendScript)) {
        throw "Backend script not found: $BackendScript"
    }
    if (-not (Test-BackendHealth -Url $BackendHealthUrl)) {
        Start-Process -FilePath $BackendPython -ArgumentList @($BackendScript, "--host", "127.0.0.1", "--port", "$BackendPort") -WorkingDirectory (Split-Path -Parent $BackendScript) -WindowStyle Hidden | Out-Null
        if ($WaitForBackend) {
            $deadline = (Get-Date).AddSeconds(20)
            while ((Get-Date) -lt $deadline) {
                if (Test-BackendHealth -Url $BackendHealthUrl) {
                    break
                }
                Start-Sleep -Milliseconds 400
            }
            if (-not (Test-BackendHealth -Url $BackendHealthUrl)) {
                try {
                    $payload = (Invoke-WebRequest -UseBasicParsing -Uri $BackendHealthUrl -TimeoutSec 2).Content | ConvertFrom-Json
                    if ($payload.websocket_transport -ne $true) {
                        throw "Backend health is up but WebSocket runtime support is missing. Install backend websocket requirements and relaunch."
                    }
                }
                catch {
                    if ($_.Exception.Message -like "*WebSocket runtime support is missing*") {
                        throw
                    }
                }
                throw "Backend failed to become healthy at $BackendHealthUrl"
            }
        }
    }
}

Start-Process -FilePath $GodotExe -ArgumentList @("--path", $ProjectPath, "--windowed") -WorkingDirectory $ProjectPath | Out-Null
