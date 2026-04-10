param(
    [string]$NamesFile = "",
    [int]$Steps = 8,
    [double]$Guidance = 5.0,
    [switch]$Force
)

$RepoRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $RepoRoot ".asset-venv\Scripts\python.exe"
$Script = Join-Path $RepoRoot "tools\asset_pipeline.py"
if (-not $NamesFile) { $NamesFile = Join-Path $RepoRoot "tools\curation\selected_item_ids.txt" }

$Args = @(
    $Script,
    "--generate", "items",
    "--backend", "deterministic_pack",
    "--names-file", $NamesFile,
    "--views", "topdown",
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
