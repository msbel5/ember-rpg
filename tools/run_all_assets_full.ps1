param(
    [int]$ItemSteps = 16,
    [int]$SpriteSteps = 1,
    [int]$TileSteps = 1,
    [double]$Guidance = 5.0,
    [switch]$Force
)

$RepoRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $RepoRoot ".asset-venv\Scripts\python.exe"
$Script = Join-Path $RepoRoot "tools\asset_pipeline.py"
$Common = @("--variants", "1", "--gc-every", "1", "--pause-ms", "150")
if ($Force) { $Common += "--force" }

& $Python $Script --generate sprites --backend deterministic_pack --steps $SpriteSteps --guidance $Guidance --width 512 --height 512 @Common
& $Python $Script --generate tiles --backend deterministic_pack --steps $TileSteps --guidance $Guidance --width 512 --height 512 @Common
& $Python $Script --generate items --backend deterministic_pack --views topdown three_quarter side --steps $ItemSteps --guidance $Guidance --width 512 --height 512 @Common
