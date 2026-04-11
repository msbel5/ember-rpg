from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = REPO_ROOT / "tools" / "asset_jobs" / "adapter_prompts.json"
REQUIRED_ADAPTERS = [
    "fantasy_ember",
    "scifi_frontier",
    "post_apocalypse",
    "weird_fiction",
]
REQUIRED_KEYS = {
    "prompt_prefix",
    "negative_prompt",
    "seed_offset",
    "lora_weight_overrides",
}


def _load_payload() -> dict:
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


def test_adapter_prompt_data_file_exists() -> None:
    assert DATA_PATH.exists(), f"Missing adapter prompt data file: {DATA_PATH}"


def test_adapter_prompt_data_contains_required_adapters() -> None:
    payload = _load_payload()
    for adapter_id in REQUIRED_ADAPTERS:
        assert adapter_id in payload, f"Missing adapter prompt entry: {adapter_id}"


def test_adapter_prompt_entries_expose_required_fields() -> None:
    payload = _load_payload()
    for adapter_id in REQUIRED_ADAPTERS:
        entry = payload[adapter_id]
        missing = REQUIRED_KEYS.difference(entry.keys())
        assert not missing, f"{adapter_id} is missing required keys: {sorted(missing)}"
        assert isinstance(entry["seed_offset"], int), f"{adapter_id} seed_offset must be an int"
        assert isinstance(entry["lora_weight_overrides"], dict), (
            f"{adapter_id} lora_weight_overrides must be a dict"
        )


def test_adapter_prompt_prefixes_are_non_empty() -> None:
    payload = _load_payload()
    for adapter_id in REQUIRED_ADAPTERS:
        prompt_prefix = str(payload[adapter_id].get("prompt_prefix", "")).strip()
        negative_prompt = str(payload[adapter_id].get("negative_prompt", "")).strip()
        assert prompt_prefix, f"{adapter_id} prompt_prefix must not be empty"
        assert negative_prompt, f"{adapter_id} negative_prompt must not be empty"
