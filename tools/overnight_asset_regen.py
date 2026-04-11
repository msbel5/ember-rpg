#!/usr/bin/env python3
"""
Overnight full asset catalog regeneration.

Runs every non-items kind first (cheap + fixes EntitySpriteCatalog failures),
then the full 894-item catalog. Single SDXL process so the model loads ONCE.
Writes a status JSON every minute to tools/overnight_status.json for out-of-band
monitoring by the user / hourly cron check.

Checkpoint / resume:
- Uses the existing asset_cache.json to skip completed jobs.
- --force bypasses the cache if the user wants a clean slate.
- Kills itself cleanly on SIGINT/SIGTERM, status file will show last phase.

Error handling:
- Any SDXL crash, out-of-memory, or per-job exception is logged to
  overnight_status.json and the loop continues with the next job (so a
  bad seed on one item does not stall the whole 894-catalog overnight).
- After 10 consecutive job failures, the script stops and sets status
  to "error:too_many_failures" so the hourly monitor can alert.

Usage:
    HF_HOME=D:/hf-cache/main U2NET_HOME=D:/u2net \\
    .asset-venv/Scripts/python.exe tools/overnight_asset_regen.py

    # Resume after interrupt:
    HF_HOME=D:/hf-cache/main U2NET_HOME=D:/u2net \\
    .asset-venv/Scripts/python.exe tools/overnight_asset_regen.py
    # (automatically skips cached jobs)

    # Force full regen (ignore cache):
    HF_HOME=D:/hf-cache/main U2NET_HOME=D:/u2net \\
    .asset-venv/Scripts/python.exe tools/overnight_asset_regen.py --force
"""
from __future__ import annotations

import argparse
import json
import signal
import sys
import time
import traceback
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
import asset_pipeline as ap  # noqa: E402

STATUS_FILE = Path(__file__).parent / "overnight_status.json"
LOG_FILE = Path(__file__).parent / "overnight_log.txt"

# Order: cheap families first (sprites + tiles fix EntitySpriteCatalog tests),
# then the new 132-asset catalog additions, then the big 894-item run last.
PHASE_ORDER: list[str] = [
    "sprites",
    "tiles",
    "spells",
    "portraits",
    "status_icons",
    "body_silhouettes",
    "combat_ui",
    "status_bars",
    "ui_banners",
    "items",
]

MAX_CONSECUTIVE_FAILURES = 10
STATUS_INTERVAL_SEC = 60.0


_shutdown_requested = False


def _signal_handler(signum: int, _frame: Any) -> None:
    global _shutdown_requested
    _shutdown_requested = True
    print(f"[overnight] shutdown signal {signum} received, finishing current job then stopping")


signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)


def write_status(payload: dict[str, Any]) -> None:
    payload["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    STATUS_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def append_log(line: str) -> None:
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {line}\n")
    print(f"[overnight] {line}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Overnight ember-rpg full asset regen")
    parser.add_argument("--force", action="store_true", help="Ignore asset_cache.json and regenerate everything")
    parser.add_argument("--phases", nargs="+", choices=PHASE_ORDER, help="Restrict to specific phases")
    parser.add_argument("--dry-run", action="store_true", help="Print the plan but do not generate")
    args = parser.parse_args()

    phases = args.phases or PHASE_ORDER

    ap.ensure_output_dirs()
    cache = ap.load_cache()

    # Build the full job list across all requested phases. Skip jobs that are
    # already cached + have the output file on disk (unless --force).
    all_jobs: list[ap.Job] = []
    phase_counts: dict[str, int] = {}
    for phase in phases:
        phase_jobs = ap.build_jobs(phase, variants=1)
        if not args.force:
            phase_jobs = [
                j for j in phase_jobs
                if not (cache.get(j.key) and (ap.GENERATED_DIR / j.output_relative_path).exists())
            ]
        phase_counts[phase] = len(phase_jobs)
        all_jobs.extend(phase_jobs)

    total = len(all_jobs)
    append_log(f"overnight start: {total} jobs across {len(phases)} phases")
    for phase, count in phase_counts.items():
        append_log(f"  {phase}: {count} jobs")

    if args.dry_run:
        append_log("dry run, exiting")
        return 0

    if total == 0:
        append_log("nothing to do, all cached")
        write_status({"status": "complete", "reason": "all_cached", "phases": phase_counts})
        return 0

    write_status({
        "status": "loading_sdxl",
        "total": total,
        "completed": 0,
        "failed": 0,
        "phases": phase_counts,
        "current_phase": None,
        "current_job": None,
    })

    # Warm-load SDXL + LoRA stack + LCM scheduler ONCE. Reused across all jobs.
    try:
        backend = ap.LocalSDXLGenerator(
            model_id=ap.DEFAULT_LOCAL_MODEL_ID,
            style_ref=None,
            lora_stack=ap.DEFAULT_LORA_STACK,
            single_lora_path=None,
            single_lora_scale=0.8,
            use_lcm=True,
            cpu_offload=True,
        )
    except Exception as exc:
        append_log(f"FATAL: SDXL load failed: {exc}")
        write_status({"status": "error", "reason": f"sdxl_load_failed: {exc}"})
        return 2

    append_log("SDXL loaded, starting generation loop")

    completed = 0
    failed = 0
    consecutive_failures = 0
    last_status_write = time.time()
    start_time = time.time()

    from PIL import Image  # noqa: E402

    for index, job in enumerate(all_jobs, 1):
        if _shutdown_requested:
            append_log(f"shutdown requested, stopping after {completed} completed jobs")
            write_status({
                "status": "interrupted",
                "completed": completed,
                "failed": failed,
                "total": total,
                "current_phase": job.kind,
                "current_job": job.key,
            })
            break

        now = time.time()
        if now - last_status_write >= STATUS_INTERVAL_SEC:
            elapsed = now - start_time
            rate = completed / elapsed if elapsed > 0 else 0
            eta_seconds = (total - completed) / rate if rate > 0 else -1
            write_status({
                "status": "running",
                "completed": completed,
                "failed": failed,
                "total": total,
                "phases": phase_counts,
                "current_phase": job.kind,
                "current_job": job.key,
                "index": index,
                "elapsed_seconds": int(elapsed),
                "rate_per_minute": round(rate * 60, 2),
                "eta_seconds": int(eta_seconds),
            })
            last_status_write = now

        try:
            raw_path, output_path = ap.output_paths_for_job(job)
            legacy_path = ap.legacy_output_path_for_job(job)

            job_width, job_height = ap.size_for_kind(job.kind)
            raw_img = backend.generate(
                prompt=job.prompt,
                seed=job.seed,
                negative_prompt=ap.negative_prompt_for_kind(job.kind),
                width=job_width,
                height=job_height,
                steps=30,
                guidance_scale=6.0,
                lora_scale=ap.lora_scale_for_kind(job.kind),
            )

            raw_img.save(str(raw_path))

            if job.kind == "sprites":
                final_img = ap.postprocess_sprite(raw_img, ap.SPRITE_SIZE)
                generated_img = ap.postprocess_sprite(raw_img, ap.GENERATED_SIZE)
            elif job.kind == "tiles":
                final_img = ap.postprocess_tile(raw_img, ap.SPRITE_SIZE)
                generated_img = ap.postprocess_tile(raw_img, ap.GENERATED_SIZE)
            elif job.kind == "items":
                final_img = ap.postprocess_item(raw_img, ap.ITEM_SIZE)
                generated_img = final_img
            else:
                final_img = ap.postprocess_for_kind(raw_img, job.kind, ap.size_for_kind(job.kind))
                generated_img = final_img

            if job.kind in {"sprites", "items"} and not ap.has_visible_pixels(generated_img):
                append_log(f"  [FAIL] {job.key} empty transparent image")
                if raw_path.exists():
                    raw_path.unlink(missing_ok=True)
                if output_path.exists():
                    output_path.unlink(missing_ok=True)
                failed += 1
                consecutive_failures += 1
                continue

            generated_img.save(str(output_path))
            if legacy_path is not None:
                legacy_path.parent.mkdir(parents=True, exist_ok=True)
                final_img.save(str(legacy_path))

            cache[job.key] = {
                "cached_at": time.strftime("%Y-%m-%d %H:%M"),
                "prompt": job.prompt[:240],
                "seed": job.seed,
                "raw": str(raw_path),
                "final": str(legacy_path) if legacy_path is not None else "",
                "generated_path": str(output_path),
                "metadata": job.metadata,
                "backend": "local_sdxl",
                "model_id": ap.DEFAULT_LOCAL_MODEL_ID,
            }
            ap.save_cache(cache)

            completed += 1
            consecutive_failures = 0

            if index % 10 == 0 or job.kind in {"spells", "portraits", "status_icons", "body_silhouettes", "combat_ui", "status_bars", "ui_banners"}:
                append_log(f"  [{index}/{total}] {job.kind}:{job.name} done")

            del raw_img
            del final_img
            del generated_img

            if index % 20 == 0:
                import gc as _gc
                _gc.collect()
                backend.cleanup()
        except KeyboardInterrupt:
            append_log("keyboard interrupt")
            break
        except Exception as exc:
            failed += 1
            consecutive_failures += 1
            append_log(f"  [FAIL] {job.key}: {exc}")
            tb = traceback.format_exc(limit=3)
            for line in tb.splitlines():
                append_log(f"    {line}")

            if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                append_log(f"FATAL: {consecutive_failures} consecutive failures, aborting")
                write_status({
                    "status": "error",
                    "reason": f"too_many_failures:{consecutive_failures}",
                    "completed": completed,
                    "failed": failed,
                    "total": total,
                    "current_phase": job.kind,
                    "current_job": job.key,
                })
                backend.cleanup()
                ap.write_manifest(cache)
                return 3

    # Loop finished (naturally or via shutdown_requested).
    ap.write_manifest(cache)
    backend.cleanup()

    elapsed = time.time() - start_time
    if _shutdown_requested:
        status = "interrupted"
    elif completed == total:
        status = "complete"
    else:
        status = "partial"

    write_status({
        "status": status,
        "completed": completed,
        "failed": failed,
        "total": total,
        "elapsed_seconds": int(elapsed),
        "rate_per_minute": round(completed / elapsed * 60, 2) if elapsed > 0 else 0,
    })

    append_log(f"overnight done: status={status} completed={completed}/{total} failed={failed} elapsed={int(elapsed)}s")
    return 0 if status == "complete" else (1 if status == "partial" else 4)


if __name__ == "__main__":
    sys.exit(main())
