param(
    [string]$BackendUrl = "http://127.0.0.1:8741",
    [string]$GodotBinary = "",
    [string]$PythonBinary = "",
    [int]$TimeoutSeconds = 45,
    [switch]$NoGodot
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = $PSScriptRoot
$BackendDir = Join-Path $RepoRoot "frp-backend"
$GodotProjectDir = Join-Path $RepoRoot "godot-client"
$DevServer = Join-Path $BackendDir "dev_server.py"
$TmpDir = Join-Path $RepoRoot "tmp"
$BackendOutLog = Join-Path $TmpDir "dev_backend.out.log"
$BackendErrLog = Join-Path $TmpDir "dev_backend.err.log"

function Write-Step([string]$Message) {
    Write-Host "[ember-dev] $Message"
}

function Resolve-BackendPort([string]$Url) {
    $uri = [Uri]$Url
    if ($uri.Port -gt 0) {
        return $uri.Port
    }
    if ($uri.Scheme -eq "https") {
        return 443
    }
    return 80
}

function Test-BackendReady([string]$Url) {
    $healthUrl = "$($Url.TrimEnd('/'))/game/health/campaign-client"
    try {
        $payload = Invoke-RestMethod -Uri $healthUrl -Method Get -TimeoutSec 2
    } catch {
        return $false
    }

    return [bool]$payload.ok `
        -and [bool]$payload.campaign_creation `
        -and [bool]$payload.campaign_runtime `
        -and [bool]$payload.campaign_save_load `
        -and [bool]$payload.websocket_transport
}

function Wait-BackendReady([string]$Url, [int]$Timeout) {
    $deadline = (Get-Date).AddSeconds($Timeout)
    while ((Get-Date) -lt $deadline) {
        if (Test-BackendReady $Url) {
            return $true
        }
        Start-Sleep -Milliseconds 400
    }
    return $false
}

function Resolve-PythonLaunch() {
    if ($PythonBinary.Trim().Length -gt 0) {
        return @{ File = $PythonBinary; Args = @() }
    }
    if ($env:EMBER_RPG_PYTHON -and $env:EMBER_RPG_PYTHON.Trim().Length -gt 0) {
        return @{ File = $env:EMBER_RPG_PYTHON; Args = @() }
    }

    $repoPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
    if (Test-Path -LiteralPath $repoPython) {
        return @{ File = $repoPython; Args = @() }
    }

    $pyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($null -ne $pyLauncher) {
        return @{ File = $pyLauncher.Source; Args = @("-3") }
    }

    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($null -ne $python) {
        return @{ File = $python.Source; Args = @() }
    }

    throw "Python bulunamadı. -PythonBinary veya EMBER_RPG_PYTHON ver."
}

function Resolve-GodotBinary() {
    if ($GodotBinary.Trim().Length -gt 0) {
        return $GodotBinary
    }
    if ($env:GODOT_BIN -and $env:GODOT_BIN.Trim().Length -gt 0) {
        return $env:GODOT_BIN
    }

    $godotCommand = Get-Command godot -ErrorAction SilentlyContinue
    if ($null -ne $godotCommand) {
        return $godotCommand.Source
    }

    $knownShim = "C:\Tools\Scoop\shims\godot.exe"
    if (Test-Path -LiteralPath $knownShim) {
        return $knownShim
    }

    $knownLocal = "C:\Tools\Godot\Godot_v4.6.1-stable_win64.exe"
    if (Test-Path -LiteralPath $knownLocal) {
        return $knownLocal
    }

    throw "Godot bulunamadı. -GodotBinary veya GODOT_BIN ver."
}

function Start-Backend([string]$Url) {
    if (-not (Test-Path -LiteralPath $DevServer)) {
        throw "Backend dev server bulunamadı: $DevServer"
    }
    New-Item -ItemType Directory -Force -Path $TmpDir | Out-Null

    $backendPort = Resolve-BackendPort $Url
    $python = Resolve-PythonLaunch
    $arguments = @()
    $arguments += $python.Args
    $arguments += @($DevServer, "--host", "127.0.0.1", "--port", [string]$backendPort, "--log-level", "info")

    Write-Step "backend başlatılıyor: $($python.File) $($arguments -join ' ')"
    Write-Step "backend log: $BackendOutLog"
    Write-Step "backend error log: $BackendErrLog"

    return Start-Process `
        -FilePath $python.File `
        -ArgumentList $arguments `
        -WorkingDirectory $BackendDir `
        -RedirectStandardOutput $BackendOutLog `
        -RedirectStandardError $BackendErrLog `
        -PassThru
}

Write-Step "repo: $RepoRoot"
Write-Step "backend URL: $BackendUrl"

if (Test-BackendReady $BackendUrl) {
    Write-Step "backend zaten hazır."
} else {
    $backendProcess = Start-Backend $BackendUrl
    Write-Step "backend pid: $($backendProcess.Id)"
    if (-not (Wait-BackendReady $BackendUrl $TimeoutSeconds)) {
        Write-Host ""
        Write-Host "Backend belirtilen sürede hazır olmadı." -ForegroundColor Red
        try {
            $healthPayload = Invoke-RestMethod -Uri "$($BackendUrl.TrimEnd('/'))/game/health/campaign-client" -Method Get -TimeoutSec 2
            if ($null -ne $healthPayload -and -not [bool]$healthPayload.websocket_transport) {
                Write-Host "Backend ayağa kalktı ama WebSocket runtime desteği yok. 'websockets' bağımlılığını kurup yeniden başlat." -ForegroundColor Yellow
            }
        } catch {}
        if (Test-Path -LiteralPath $BackendErrLog) {
            Write-Host ""
            Write-Host "Son backend error log satırları:" -ForegroundColor Yellow
            Get-Content -LiteralPath $BackendErrLog -Tail 80
        }
        throw "Backend health başarısız: $BackendUrl/game/health/campaign-client"
    }
    Write-Step "backend hazır."
}

$env:EMBER_RPG_BACKEND_URL = $BackendUrl

if ($NoGodot) {
    Write-Step "NoGodot verildi; Godot açılmadı."
    exit 0
}

$godot = Resolve-GodotBinary
$godotArgs = @("--path", $GodotProjectDir, "--windowed")
Write-Step "Godot açılıyor: $godot $($godotArgs -join ' ')"
Start-Process -FilePath $godot -ArgumentList $godotArgs -WorkingDirectory $GodotProjectDir

Write-Step "hazır. Başlık ekranında New Chronicle / Continue kullanabilirsin."
