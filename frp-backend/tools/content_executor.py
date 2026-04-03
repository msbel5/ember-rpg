"""Execute content generation via GitHub Copilot CLI (winget: GitHub.Copilot).

Uses `copilot -p <prompt> -s --output-format text --model <model> --allow-all-tools`
in non-interactive mode. Each family's creator prompt is fed to the CLI and the
JSON output is written to candidates/.

Prerequisites:
    winget install GitHub.Copilot   # installs `copilot` to PATH
    copilot login                   # authenticate once

Usage:
    python -m tools.content_orchestrator generate --model gpt-4o
    python -m tools.content_orchestrator review  --model gpt-4o
"""
from __future__ import annotations

import json
import logging
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gpt-4.1"
DEFAULT_TIMEOUT = 300  # 5 minutes per family — large JSON output


def _find_copilot_cli() -> str:
    """Locate the copilot CLI binary."""
    found = shutil.which("copilot")
    if found:
        return found
    # Winget default install location.
    winget_path = Path.home() / "AppData/Local/Microsoft/WinGet/Links/copilot.exe"
    if winget_path.exists():
        return str(winget_path)
    raise FileNotFoundError(
        "Copilot CLI not found. Install with: winget install GitHub.Copilot"
    )


def _call_copilot(prompt: str, model: str = DEFAULT_MODEL, timeout: int = DEFAULT_TIMEOUT,
                  json_mode: bool = True) -> str:
    """Call Copilot CLI via stdin pipe to avoid Windows command-line length limits."""
    cli = _find_copilot_cli()
    final_prompt = prompt
    if json_mode:
        final_prompt += "\n\nCRITICAL: Output ONLY the raw JSON object. No markdown, no code fences, no explanation. Do NOT reuse any ID from the EXISTING IDs list."
    # Pipe prompt via stdin (no -p flag) — avoids Windows 32K arg limit.
    result = subprocess.run(
        [
            cli,
            "-s",
            "--model", model,
            "--output-format", "text",
            "--no-custom-instructions",
            "--allow-all-tools",
        ],
        input=final_prompt,
        capture_output=True,
        text=True,
        timeout=timeout,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        stderr = result.stderr.strip()
        raise RuntimeError(f"Copilot CLI failed (exit {result.returncode}): {stderr or result.stdout[:200]}")
    output = result.stdout.strip()
    if not output:
        raise RuntimeError("Copilot CLI returned empty output")
    return output


def _extract_json(raw: str) -> str:
    """Extract JSON from model output, stripping markdown fences if present."""
    text = raw.strip()
    # Strip markdown code fences.
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]  # Remove opening fence line
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    # Find the first { or [ and last } or ] for robustness.
    start = -1
    for i, ch in enumerate(text):
        if ch in "{[":
            start = i
            break
    if start == -1:
        return text
    end = -1
    closer = "}" if text[start] == "{" else "]"
    for i in range(len(text) - 1, start - 1, -1):
        if text[i] == closer:
            end = i
            break
    if end == -1:
        return text
    return text[start:end + 1]


def _dedup_against_source(parsed: Any, prompt: str) -> tuple[Any, int]:
    """Remove generated entries whose IDs already exist in the source data.

    Extracts the existing_ids list from the prompt text and filters the output.
    """
    import re
    # Extract existing IDs from the prompt.
    match = re.search(r'EXISTING IDs[^\[]*(\[.*?\])', prompt, re.DOTALL)
    if not match:
        return parsed, 0
    try:
        existing = set(json.loads(match.group(1)))
    except (json.JSONDecodeError, TypeError):
        return parsed, 0
    if not existing:
        return parsed, 0
    # Filter entries from the parsed output.
    removed = 0
    if isinstance(parsed, dict):
        for key, value in parsed.items():
            if isinstance(value, list):
                original_len = len(value)
                filtered = []
                for entry in value:
                    if isinstance(entry, dict):
                        entry_id = entry.get("id") or entry.get("dialog_id") or entry.get("name", "")
                        if str(entry_id) in existing:
                            removed += 1
                            continue
                    filtered.append(entry)
                parsed[key] = filtered
    return parsed, removed


def generate_family(
    prompt_path: str,
    output_path: str,
    model: str = DEFAULT_MODEL,
    timeout: int = DEFAULT_TIMEOUT,
) -> tuple[bool, str]:
    """Generate content for a single family using the creator prompt."""
    prompt_file = Path(prompt_path)
    if not prompt_file.exists():
        return False, f"Prompt file not found: {prompt_path}"
    prompt = prompt_file.read_text(encoding="utf-8")
    family_name = Path(output_path).stem
    logger.info("Generating %s with model=%s...", family_name, model)
    start = time.time()
    try:
        raw_output = _call_copilot(prompt, model=model, timeout=timeout)
        json_text = _extract_json(raw_output)
        parsed = json.loads(json_text)
        # Post-generation dedup: remove entries with IDs that exist in the source.
        parsed, removed = _dedup_against_source(parsed, prompt)
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(
            json.dumps(parsed, indent=2, ensure_ascii=False), encoding="utf-8",
        )
        elapsed = time.time() - start
        dedup_note = f", {removed} duplicates removed" if removed else ""
        logger.info("Generated %s in %.1fs (%d chars%s)", output_file.name, elapsed, len(json_text), dedup_note)
        return True, f"generated in {elapsed:.1f}s{dedup_note}"
    except json.JSONDecodeError as exc:
        return False, f"Invalid JSON in model output: {exc}"
    except Exception as exc:
        return False, str(exc)


def generate_all(
    manifest_path: str,
    model: str = DEFAULT_MODEL,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """Generate candidates for all families in the manifest."""
    manifest_file = Path(manifest_path)
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    packets_dir = manifest_file.parent
    results: dict[str, Any] = {}
    for family in manifest.get("families", []):
        name = family["name"]
        prompt_path = str(packets_dir / f"{name}_creator_prompt.txt")
        candidate_path = family.get("candidate", "")
        if not candidate_path:
            results[name] = {"ok": False, "message": "missing candidate path in manifest"}
            continue
        ok, msg = generate_family(prompt_path, candidate_path, model=model, timeout=timeout)
        results[name] = {"ok": ok, "message": msg}
    return results


def review_family(
    reviewer_prompt_path: str,
    candidate_path: str,
    review_output_path: str,
    model: str = DEFAULT_MODEL,
    timeout: int = DEFAULT_TIMEOUT,
) -> tuple[bool, str]:
    """Run a reviewer prompt on a candidate file."""
    prompt_file = Path(reviewer_prompt_path)
    candidate_file = Path(candidate_path)
    if not prompt_file.exists():
        return False, f"Reviewer prompt not found: {reviewer_prompt_path}"
    if not candidate_file.exists():
        return False, f"Candidate not found: {candidate_path}"
    prompt = prompt_file.read_text(encoding="utf-8")
    candidate_content = candidate_file.read_text(encoding="utf-8")
    full_prompt = f"{prompt}\n\n--- CANDIDATE CONTENT ---\n{candidate_content}"
    logger.info("Reviewing %s with model=%s...", candidate_file.stem, model)
    start = time.time()
    try:
        review_text = _call_copilot(full_prompt, model=model, timeout=timeout, json_mode=False)
        output_file = Path(review_output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(review_text, encoding="utf-8")
        elapsed = time.time() - start
        logger.info("Reviewed %s in %.1fs", candidate_file.stem, elapsed)
        return True, f"reviewed in {elapsed:.1f}s"
    except Exception as exc:
        return False, str(exc)


def review_all(
    manifest_path: str,
    model: str = DEFAULT_MODEL,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """Run reviewer prompts on all generated candidates."""
    manifest_file = Path(manifest_path)
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    packets_dir = manifest_file.parent
    results: dict[str, Any] = {}
    for family in manifest.get("families", []):
        name = family["name"]
        reviewer_prompt = str(packets_dir / f"{name}_reviewer_prompt.txt")
        candidate_path = family.get("candidate", "")
        review_path = family.get("review", "")
        if not candidate_path or not review_path:
            results[name] = {"ok": False, "message": "missing paths"}
            continue
        ok, msg = review_family(
            reviewer_prompt, candidate_path, review_path, model=model, timeout=timeout,
        )
        results[name] = {"ok": ok, "message": msg}
    return results
