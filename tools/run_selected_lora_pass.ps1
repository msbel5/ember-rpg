param(
    [string]$NamesFile = "",
    [string]$LoraPath = "",
    [int]$Steps = 16,
    [double]$Guidance = 5.4,
    [double]$LoraScale = 0.85,
    [switch]$Force
)

$RepoRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $RepoRoot ".asset-venv\Scripts\python.exe"
$Script = Join-Path $RepoRoot "tools\asset_pipeline.py"
if (-not $NamesFile) { $NamesFile = Join-Path $RepoRoot "tools\curation\selected_item_ids.txt" }
if (-not $LoraPath) { $LoraPath = Join-Path $RepoRoot "tools\curation\item_style_lora" }

$Args = @(
    $Script,
    "--generate", "items",
    "--backend", "local_sdxl",
    "--names-file", $NamesFile,
    "--style-ref", "none",
    "--lora-path", $LoraPath,
    "--lora-scale", "$LoraScale",
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
