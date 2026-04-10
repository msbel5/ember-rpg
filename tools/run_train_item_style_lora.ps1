param(
    [string]$NamesFile = "",
    [string]$DatasetDir = "",
    [string]$OutputDir = "",
    [string]$Token = "ember-style",
    [int]$Resolution = 512,
    [int]$TrainSteps = 800,
    [double]$LearningRate = 1e-4
)

$RepoRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $RepoRoot ".asset-venv\Scripts\python.exe"
$VendorDir = Join-Path $RepoRoot "tools\vendor"
$TrainerPath = Join-Path $VendorDir "train_text_to_image_lora_sdxl.py"
$DatasetPrep = Join-Path $RepoRoot "tools\prepare_style_lora_dataset.py"
if (-not $NamesFile) { $NamesFile = Join-Path $RepoRoot "tools\curation\selected_item_ids.txt" }
if (-not $DatasetDir) { $DatasetDir = Join-Path $RepoRoot "tools\curation\selected_item_lora_dataset" }
if (-not $OutputDir) { $OutputDir = Join-Path $RepoRoot "tools\curation\item_style_lora" }

New-Item -ItemType Directory -Force -Path $VendorDir | Out-Null
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

$Url = "https://raw.githubusercontent.com/huggingface/diffusers/v0.37.1/examples/text_to_image/train_text_to_image_lora_sdxl.py"
Invoke-WebRequest -Uri $Url -OutFile $TrainerPath

& $Python $DatasetPrep `
    --names-file $NamesFile `
    --input-dir (Join-Path $RepoRoot "godot-client\assets\generated\items") `
    --out-dir $DatasetDir

$Env:HF_HUB_DISABLE_TELEMETRY = "1"
$Env:PYTORCH_CUDA_ALLOC_CONF = "max_split_size_mb:128"
$CacheRoot = "D:\hf-cache\ember-rpg"
if (-not (Test-Path "D:\")) {
    $CacheRoot = Join-Path $RepoRoot ".hf-cache"
}
New-Item -ItemType Directory -Force -Path $CacheRoot | Out-Null
$Env:HF_HOME = $CacheRoot
$Env:HUGGINGFACE_HUB_CACHE = Join-Path $CacheRoot "hub"
$Env:TRANSFORMERS_CACHE = Join-Path $CacheRoot "transformers"
$Env:HF_DATASETS_CACHE = Join-Path $CacheRoot "datasets"
New-Item -ItemType Directory -Force -Path $Env:HUGGINGFACE_HUB_CACHE | Out-Null
New-Item -ItemType Directory -Force -Path $Env:TRANSFORMERS_CACHE | Out-Null
New-Item -ItemType Directory -Force -Path $Env:HF_DATASETS_CACHE | Out-Null

& $Python -m accelerate.commands.launch $TrainerPath `
    --pretrained_model_name_or_path stabilityai/stable-diffusion-xl-base-1.0 `
    --train_data_dir $DatasetDir `
    --caption_column text `
    --resolution $Resolution `
    --train_batch_size 1 `
    --gradient_accumulation_steps 4 `
    --learning_rate $LearningRate `
    --lr_scheduler constant `
    --lr_warmup_steps 0 `
    --max_train_steps $TrainSteps `
    --checkpointing_steps 200 `
    --rank 8 `
    --mixed_precision fp16 `
    --validation_prompt "$Token dark-fantasy crpg item icon, abyssal blade" `
    --output_dir $OutputDir
