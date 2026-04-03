#!/usr/bin/env python
"""
Ember RPG — Content Generation Pipeline
========================================
Runs: prepare → generate → validate → merge

Usage:
    python tools/generate_content.py
    python tools/generate_content.py --model gpt-5-mini
    python tools/generate_content.py --dry-run
    python tools/generate_content.py --rounds 3
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

# -- Colors --------------------------------------------------------------

# Ensure frp-backend is on sys.path for `tools.*` imports.
_SCRIPT_DIR = Path(__file__).resolve().parent
_BACKEND_DIR = _SCRIPT_DIR.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
DIM = "\033[2m"
MAGENTA = "\033[95m"


def header(text: str) -> None:
    print(f"\n{BOLD}{CYAN}{'=' * 60}{RESET}")
    print(f"{BOLD}{CYAN}  {text}{RESET}")
    print(f"{BOLD}{CYAN}{'=' * 60}{RESET}\n")


def step(num: int, total: int, text: str) -> None:
    print(f"{BOLD}{MAGENTA}[{num}/{total}]{RESET} {BOLD}{text}{RESET}")


def ok(text: str) -> None:
    print(f"  {GREEN}OK{RESET} {text}")


def fail(text: str) -> None:
    print(f"  {RED}FAIL{RESET} {text}")


def warn(text: str) -> None:
    print(f"  {YELLOW}WARN{RESET} {text}")


def info(text: str) -> None:
    print(f"  {DIM}{text}{RESET}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Ember RPG content generation pipeline")
    parser.add_argument("--model", default="gpt-4.1", help="Copilot model (default: gpt-4.1)")
    parser.add_argument("--timeout", type=int, default=180, help="Timeout per family in seconds")
    parser.add_argument("--dry-run", action="store_true", help="Don't merge, just show what would happen")
    parser.add_argument("--rounds", type=int, default=1, help="Run multiple generate+merge rounds")
    parser.add_argument("--skip-generate", action="store_true", help="Skip generation, just merge existing candidates")
    args = parser.parse_args()

    # Ensure we're in frp-backend.
    if not Path("data/items.json").exists():
        if Path("frp-backend/data/items.json").exists():
            import os
            os.chdir("frp-backend")
        else:
            print(f"{RED}ERROR: Run this from the ember-rpg or frp-backend directory.{RESET}")
            return 1

    total_added_all = 0
    total_rounds = args.rounds

    for round_num in range(1, total_rounds + 1):
        if total_rounds > 1:
            header(f"ROUND {round_num}/{total_rounds}")

        # -- Step 1: Prepare ------------------------------------------
        step(1, 4, "PREPARE — generating packets & prompts")
        t0 = time.time()
        from tools.content_orchestrator import prepare_packets
        manifest = prepare_packets()
        families = manifest["families"]
        elapsed = time.time() - t0
        ok(f"{len(families)} families prepared in {elapsed:.1f}s")
        for f in families:
            info(f"{f['name']}")

        # -- Step 2: Generate -----------------------------------------
        if not args.skip_generate:
            step(2, 4, f"GENERATE — model={CYAN}{args.model}{RESET}")
            from tools.content_executor import generate_family
            packets_dir = Path("..") / "tmp" / "content_packets"
            if not packets_dir.exists():
                packets_dir = Path("tmp") / "content_packets"

            gen_ok = gen_fail = 0
            t0 = time.time()
            for i, family in enumerate(families):
                name = family["name"]
                prompt_path = str(packets_dir / f"{name}_creator_prompt.txt")
                candidate_path = family["candidate"]
                sys.stdout.write(f"  {DIM}[{i+1}/{len(families)}]{RESET} {name}... ")
                sys.stdout.flush()
                success, msg = generate_family(prompt_path, candidate_path,
                                               model=args.model, timeout=args.timeout)
                if success:
                    # Count entries.
                    try:
                        d = json.loads(Path(candidate_path).read_text(encoding="utf-8"))
                        count = sum(len(v) for v in d.values() if isinstance(v, (list, dict)))
                        print(f"{GREEN}OK{RESET} {count} entries, {msg}")
                    except Exception:
                        print(f"{GREEN}OK{RESET} {msg}")
                    gen_ok += 1
                else:
                    print(f"{RED}FAIL{RESET} {msg}")
                    gen_fail += 1

            elapsed = time.time() - t0
            print()
            if gen_fail == 0:
                ok(f"All {gen_ok} families generated in {elapsed:.0f}s")
            else:
                warn(f"{gen_ok} OK, {gen_fail} FAIL in {elapsed:.0f}s")
        else:
            step(2, 4, "GENERATE — skipped (--skip-generate)")

        # -- Step 3: Validate -----------------------------------------
        step(3, 4, "VALIDATE — schema & duplicate check")
        try:
            from tools.content_orchestrator import validate_batches
            result = validate_batches(strict_missing=False)
            status = result.get("overall_status", "unknown")
            if status in ("pass", "pass_with_warnings"):
                ok(f"Validation: {status}")
            else:
                warn(f"Validation: {status}")
                for fname, finfo in result.get("families", {}).items():
                    for e in finfo.get("errors", [])[:2]:
                        info(f"  {fname}: {e}")
        except Exception as exc:
            warn(f"Validation skipped: {exc}")

        # -- Step 4: Merge --------------------------------------------
        mode = "DRY-RUN" if args.dry_run else "MERGE"
        step(4, 4, f"{mode} — writing to data/ files")
        from tools.content_merger import merge_all
        manifest_path = Path("..") / "tmp" / "content_packets" / "manifest.json"
        if not manifest_path.exists():
            manifest_path = Path("tmp") / "content_packets" / "manifest.json"

        results = merge_all(str(manifest_path), dry_run=args.dry_run)
        total_added = sum(r["added"] for r in results.values())
        total_skipped = sum(r["skipped"] for r in results.values())
        total_errors = sum(len([e for e in r["errors"] if "Candidate not found" not in e]) for r in results.values())

        for name, r in results.items():
            if r["added"] > 0:
                ok(f"{name}: +{r['added']} new entries")
            elif r["skipped"] > 0:
                info(f"{name}: {r['skipped']} duplicates skipped")
            elif r["errors"]:
                # Don't show "candidate not found" as errors — just means nothing to merge.
                real_errors = [e for e in r["errors"] if "Candidate not found" not in e]
                if real_errors:
                    for e in real_errors:
                        fail(f"{name}: {e}")
                else:
                    info(f"{name}: no candidates yet")

        total_added_all += total_added

        # -- Summary --------------------------------------------------
        print()
        print(f"{BOLD}{'-' * 60}{RESET}")
        if args.dry_run:
            print(f"{YELLOW}DRY-RUN{RESET}: {BOLD}{total_added}{RESET} entries would be added, {total_skipped} duplicates skipped")
        else:
            print(f"{GREEN}MERGED{RESET}: {BOLD}{total_added}{RESET} new entries added to data/")

        if total_errors > 0:
            print(f"{RED}{total_errors} errors{RESET}")
        print(f"{BOLD}{'-' * 60}{RESET}")

        # Clear LRU caches between rounds so new data is picked up.
        if round_num < total_rounds:
            try:
                from engine.data._shared import _load_json
                _load_json.cache_clear()
            except Exception:
                pass

    if total_rounds > 1:
        header(f"COMPLETE — {total_rounds} rounds, {total_added_all} total entries added")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
