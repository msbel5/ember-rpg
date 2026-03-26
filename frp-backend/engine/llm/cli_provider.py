"""Copilot CLI-backed provider for live narration."""
from __future__ import annotations

import subprocess
from typing import List


class CopilotCLIError(RuntimeError):
    """Raised when the Copilot CLI provider cannot fulfill a request."""


def _render_prompt(messages: List[dict]) -> str:
    rendered = []
    for message in messages:
        role = str(message.get("role", "user")).upper()
        content = str(message.get("content", "")).strip()
        if content:
            rendered.append(f"{role}:\n{content}")
    rendered.append("Respond with only the final in-world text.")
    return "\n\n".join(rendered)


def complete_with_copilot_cli(messages: List[dict], model: str, cli_command: str) -> str:
    prompt = _render_prompt(messages)
    try:
        result = subprocess.run(
            [
                cli_command,
                "-p",
                prompt,
                "--model",
                model,
                "-s",
                "--no-custom-instructions",
                "--output-format",
                "text",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=90,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired) as exc:
        raise CopilotCLIError(f"Copilot CLI unavailable: {exc}") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip() or f"exit code {result.returncode}"
        raise CopilotCLIError(f"Copilot CLI request failed: {detail}")
    text = result.stdout.strip()
    if not text:
        raise CopilotCLIError("Copilot CLI returned an empty response.")
    return text
