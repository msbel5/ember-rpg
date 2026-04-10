param(
    [string]$NamesFile = "",
    [string]$StyleRef = "",
    [int]$Steps = 16,
    [double]$Guidance = 5.5,
    [switch]$Force
)

$RepoRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $RepoRoot ".asset-venv\Scripts\python.exe"
$Script = Join-Path $RepoRoot "tools\asset_pipeline.py"
if (-not $NamesFile) { $NamesFile = Join-Path $RepoRoot "tools\curation\selected_item_ids.txt" }
if (-not $StyleRef) { $StyleRef = Join-Path $RepoRoot "tools\style_refs\ember_style_anchor_selected.png" }

$Args = @(
    $Script,
    "--generate", "items",
    "--backend", "deterministic_pack",
    "--names-file", $NamesFile,
    "--views", "three_quarter", "side",
    "--variants", "1",
    "--steps", "$Steps",
    "--guidance", "$Guidance",
    "--width", "512",
    "--height", "512",
    "--gc-every", "1",
    "--pause-ms", "500"
)

if ($Force) {
    $Args += "--force"
}

& $Python @Args
