param(
    [switch]$Background,
    [int]$Limit = 0,
    [string]$StyleRef = "none",
    [int]$Steps = 16,
    [double]$Guidance = 5.0,
    [int]$PauseMs = 500
)

$RepoRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $RepoRoot ".asset-venv\Scripts\python.exe"
$Script = Join-Path $RepoRoot "tools\asset_pipeline.py"
$LogDir = Join-Path $RepoRoot "tools\logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$LogPath = Join-Path $LogDir "items_topdown_v1_$Stamp.log"

$Args = @(
    $Script,
    "--generate", "items",
    "--backend", "template_32rogues",
    "--style-ref", $StyleRef,
    "--views", "topdown",
    "--variants", "1",
    "--steps", "$Steps",
    "--guidance", "$Guidance",
    "--width", "512",
    "--height", "512",
    "--gc-every", "1",
    "--pause-ms", "$PauseMs"
)

if ($Limit -gt 0) {
    $Args += @("--limit", "$Limit")
}

if ($Background) {
    $Quoted = $Args | ForEach-Object {
        if ($_ -match "\s") { '"{0}"' -f $_ } else { $_ }
    }
    $Command = "& `"$Python`" $($Quoted -join ' ') *>> `"$LogPath`""
    $Proc = Start-Process powershell -ArgumentList "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $Command -PassThru -WindowStyle Minimized
    try { $Proc.PriorityClass = "BelowNormal" } catch {}
    Write-Host "Started items topdown v1 batch"
    Write-Host "PID : $($Proc.Id)"
    Write-Host "Log : $LogPath"
    exit 0
}

& $Python @Args
