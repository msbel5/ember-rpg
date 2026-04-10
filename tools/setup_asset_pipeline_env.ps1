param(
    [string]$PythonVersion = "3.10",
    [string]$EnvPath = "C:\Users\msbel\projects\ember-rpg\.asset-venv"
)

$ErrorActionPreference = "Stop"

py -$PythonVersion -m venv $EnvPath

$python = Join-Path $EnvPath "Scripts\python.exe"

& $python -m pip install --upgrade pip
& $python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
& $python -m pip install -r "C:\Users\msbel\projects\ember-rpg\tools\requirements-asset-pipeline.txt"

& $python -c "import torch; print('torch', torch.__version__); print('cuda', torch.cuda.is_available()); print('device', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'none')"

