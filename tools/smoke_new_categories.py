#!/usr/bin/env python3
"""
One-shot smoke test for the 7 new asset categories.

Loads SDXL + LoRA stack + LCM scheduler once, then generates a single
sample from each remaining new category to prove the per-kind sizing,
prompt, and postprocess paths. Deletes itself-no, the user deletes it
after review.

Usage:
    HF_HOME=D:/hf-cache/main U2NET_HOME=D:/u2net \
    .asset-venv/Scripts/python.exe tools/smoke_new_categories.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import asset_pipeline as ap

SMOKE_TARGETS = [
    ("portraits", "human_fighter_male"),
    ("status_icons", "poisoned"),
    ("body_silhouettes", "humanoid_male"),
    ("combat_ui", "badge_action_available"),
    ("status_bars", "hp_frame_empty"),
    ("ui_banners", "banner_paused"),
]


def main() -> None:
    print(f"[smoke] will generate: {[k + ':' + n for k, n in SMOKE_TARGETS]}")
    ap.ensure_output_dirs()

    jobs = []
    for kind, name in SMOKE_TARGETS:
        kind_jobs = ap.build_jobs(kind, variants=1)
        matching = [j for j in kind_jobs if ap.slugify(j.name) == name]
        if not matching:
            print(f"[smoke][WARN] no job matches {kind}:{name}")
            continue
        jobs.append(matching[0])

    print(f"[smoke] {len(jobs)} jobs queued")
    ap.generate_jobs(
        jobs=jobs,
        backend="local_sdxl",
        force=True,
        model_id=ap.DEFAULT_LOCAL_MODEL_ID,
        style_ref_path=None,
        steps=30,
        guidance_scale=6.0,
        width=ap.RAW_SIZE[0],
        height=ap.RAW_SIZE[1],
        gc_every=1,
        pause_ms=250,
        lora_stack=ap.DEFAULT_LORA_STACK,
        single_lora_path=None,
        single_lora_scale=0.8,
        use_lcm=True,
    )
    print("[smoke] done")


if __name__ == "__main__":
    main()
