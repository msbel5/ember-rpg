param(
    [switch]$Background,
    [switch]$Force,
    [int]$PauseMs = 150,
    [int]$SelectionTarget = 28
)

$RepoRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $RepoRoot ".asset-venv\Scripts\python.exe"
$AssetScript = Join-Path $RepoRoot "tools\asset_pipeline.py"
$ScoreScript = Join-Path $RepoRoot "tools\score_generated_items.py"
$SelectScript = Join-Path $RepoRoot "tools\select_item_style_candidates.py"
$BoardScript = Join-Path $RepoRoot "tools\build_style_anchor_from_selection.py"
$SheetScript = Join-Path $RepoRoot "tools\render_asset_contact_sheet.py"
$LogDir = Join-Path $RepoRoot "tools\logs"
$CurationDir = Join-Path $RepoRoot "tools\curation"
$ProbeDir = Join-Path $RepoRoot "tmp\asset_probe"
New-Item -ItemType Directory -Force -Path $LogDir, $CurationDir, $ProbeDir | Out-Null

$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$LogPath = Join-Path $LogDir "assets_overnight_$Stamp.log"

if ($Background) {
    $Command = "& `"$PSCommandPath`" " + ($(if ($Force) { "-Force " } else { "" })) + "-PauseMs $PauseMs -SelectionTarget $SelectionTarget *>> `"$LogPath`""
    $Proc = Start-Process powershell -ArgumentList "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $Command -PassThru -WindowStyle Minimized
    try { $Proc.PriorityClass = "BelowNormal" } catch {}
    Write-Host "Started overnight asset pipeline"
    Write-Host "PID : $($Proc.Id)"
    Write-Host "Log : $LogPath"
    exit 0
}

function Write-Stage([string]$Message) {
    $line = "[{0}] {1}" -f (Get-Date -Format "HH:mm:ss"), $Message
    Write-Host $line
}

function Invoke-Step([string]$Label, [string[]]$CommandArgs) {
    Write-Stage $Label
    & $Python @CommandArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Step failed: $Label"
    }
    Start-Sleep -Seconds 1
}

$ItemsDir = Join-Path $RepoRoot "godot-client\assets\generated\items"
$SpritesDir = Join-Path $RepoRoot "godot-client\assets\generated\sprites"
$TilesDir = Join-Path $RepoRoot "godot-client\assets\generated\tiles"
$ScoresJson = Join-Path $ProbeDir "items_scores.json"
$SelectedIds = Join-Path $CurationDir "selected_item_ids.txt"
$SelectedBoard = Join-Path $RepoRoot "tools\style_refs\ember_style_anchor_selected.png"
$SelectedSheet = Join-Path $ProbeDir "selected_items_sheet.png"
$ItemsSheet = Join-Path $ProbeDir "items_contact_sheet_current.png"
$SpritesSheet = Join-Path $ProbeDir "sprites_contact_sheet.png"
$TilesSheet = Join-Path $ProbeDir "tiles_contact_sheet.png"
$ItemsJson = Join-Path $RepoRoot "frp-backend\data\items.json"

if (-not (Test-Path $Python)) {
    throw ".asset-venv python not found at $Python"
}

$TopdownArgs = @(
    $AssetScript, "--generate", "items",
    "--backend", "deterministic_pack",
    "--views", "topdown",
    "--variants", "1",
    "--steps", "8",
    "--guidance", "5.0",
    "--width", "512",
    "--height", "512",
    "--gc-every", "1",
    "--pause-ms", "$PauseMs"
)
if ($Force) { $TopdownArgs += "--force" }
Invoke-Step "Generate item topdown set" $TopdownArgs

Invoke-Step "Score generated items" @(
    $ScoreScript,
    "--folder", $ItemsDir,
    "--out-json", $ScoresJson,
    "--out-names", $SelectedIds,
    "--top", "$SelectionTarget"
)

Invoke-Step "Select diverse style candidates" @(
    $SelectScript,
    "--scores-json", $ScoresJson,
    "--items-json", $ItemsJson,
    "--out-names", $SelectedIds,
    "--target", "$SelectionTarget"
)

Invoke-Step "Build selected style board" @(
    $BoardScript,
    "--folder", $ItemsDir,
    "--names-file", $SelectedIds,
    "--out", $SelectedBoard,
    "--cols", "5",
    "--tile", "192"
)

Invoke-Step "Render selected item sheet" @(
    $SheetScript,
    "--folder", $ItemsDir,
    "--names-file", $SelectedIds,
    "--out", $SelectedSheet,
    "--cols", "4",
    "--thumb", "128"
)

$ViewsArgs = @(
    $AssetScript, "--generate", "items",
    "--backend", "deterministic_pack",
    "--views", "three_quarter", "side",
    "--variants", "1",
    "--steps", "8",
    "--guidance", "5.0",
    "--width", "512",
    "--height", "512",
    "--gc-every", "1",
    "--pause-ms", "$PauseMs"
)
if ($Force) { $ViewsArgs += "--force" }
Invoke-Step "Generate item side and three-quarter views" $ViewsArgs

$SpritesArgs = @(
    $AssetScript, "--generate", "sprites",
    "--backend", "deterministic_pack",
    "--variants", "1",
    "--steps", "1",
    "--guidance", "5.0",
    "--width", "512",
    "--height", "512",
    "--gc-every", "1",
    "--pause-ms", "$PauseMs"
)
if ($Force) { $SpritesArgs += "--force" }
Invoke-Step "Generate sprite set" $SpritesArgs

$TilesArgs = @(
    $AssetScript, "--generate", "tiles",
    "--backend", "deterministic_pack",
    "--variants", "1",
    "--steps", "1",
    "--guidance", "5.0",
    "--width", "512",
    "--height", "512",
    "--gc-every", "1",
    "--pause-ms", "$PauseMs"
)
if ($Force) { $TilesArgs += "--force" }
Invoke-Step "Generate tile set" $TilesArgs

Invoke-Step "Render full item sheet" @(
    $SheetScript,
    "--folder", $ItemsDir,
    "--out", $ItemsSheet,
    "--cols", "8",
    "--thumb", "96",
    "--limit", "128"
)

Invoke-Step "Render sprite sheet" @(
    $SheetScript,
    "--folder", $SpritesDir,
    "--out", $SpritesSheet,
    "--cols", "6",
    "--thumb", "96"
)

Invoke-Step "Render tile sheet" @(
    $SheetScript,
    "--folder", $TilesDir,
    "--out", $TilesSheet,
    "--cols", "6",
    "--thumb", "96"
)

Write-Stage "Overnight asset pipeline complete"
