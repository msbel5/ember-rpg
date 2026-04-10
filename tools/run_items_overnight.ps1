param(
    [switch]$Background,
    [int]$PauseMs = 250,
    [int]$TopCount = 32
)

$RepoRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $RepoRoot ".asset-venv\Scripts\python.exe"
$Pipeline = Join-Path $RepoRoot "tools\asset_pipeline.py"
$Scorer = Join-Path $RepoRoot "tools\score_generated_items.py"
$Sheet = Join-Path $RepoRoot "tools\render_asset_contact_sheet.py"
$Anchor = Join-Path $RepoRoot "tools\build_style_anchor_from_selection.py"
$LogDir = Join-Path $RepoRoot "tools\logs"
$CurationDir = Join-Path $RepoRoot "tools\curation"
$GeneratedItems = Join-Path $RepoRoot "godot-client\assets\generated\items"
$SelectedNames = Join-Path $CurationDir "selected_item_ids.txt"
$SelectedSheet = Join-Path $RepoRoot "tmp\asset_probe\selected_items_sheet.png"
$ScoreJson = Join-Path $RepoRoot "tmp\asset_probe\items_scores.json"
$SelectedAnchor = Join-Path $RepoRoot "tools\style_refs\ember_style_anchor_selected.png"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$LogPath = Join-Path $LogDir "items_overnight_$Stamp.log"

$ScriptBlock = @"
& "$Python" "$Pipeline" --generate items --backend template_32rogues --views topdown --variants 1 --gc-every 1 --pause-ms $PauseMs
& "$Python" "$Scorer" --folder "$GeneratedItems" --out-json "$ScoreJson" --out-names "$SelectedNames" --top $TopCount
& "$Python" "$Sheet" --folder "$GeneratedItems" --names-file "$SelectedNames" --out "$SelectedSheet" --cols 4 --thumb 112
& "$Python" "$Anchor" --folder "$GeneratedItems" --names-file "$SelectedNames" --out "$SelectedAnchor"
& "$Python" "$Pipeline" --generate items --backend template_32rogues --views three_quarter --variants 1 --gc-every 1 --pause-ms $PauseMs
& "$Python" "$Pipeline" --generate items --backend template_32rogues --views side --variants 1 --gc-every 1 --pause-ms $PauseMs
"@

if ($Background) {
    $Command = $ScriptBlock + " *>> `"$LogPath`""
    $Proc = Start-Process powershell -ArgumentList "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $Command -PassThru -WindowStyle Minimized
    try { $Proc.PriorityClass = "BelowNormal" } catch {}
    Write-Host "Started overnight item pipeline"
    Write-Host "PID : $($Proc.Id)"
    Write-Host "Log : $LogPath"
    exit 0
}

Invoke-Expression $ScriptBlock
