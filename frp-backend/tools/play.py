#!/usr/bin/env python3
"""Campaign-first narrative terminal client for Ember RPG."""
from __future__ import annotations

import os
import sys

if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.rule import Rule

from tools.campaign_client import CampaignClient
from tools.play_topdown import character_creation, render_header

console = Console(force_terminal=True)


def _append(history: list[str], text: str) -> None:
    cleaned = text.strip()
    if not cleaned:
        return
    history.append(cleaned)
    del history[:-40]


def _print_scene(snapshot: dict, history: list[str]) -> None:
    console.clear()
    console.print(render_header(snapshot))
    console.print()
    console.print(Panel("\n\n".join(history[-12:]), title="Narrative", border_style="bright_blue"))
    settlement = snapshot.get("campaign", {}).get("settlement", {})
    if settlement:
        console.print(
            Panel(
                "Settlement: %s\nDefense: %s\nResidents: %d\nJobs: %d\nAlerts: %d"
                % (
                    settlement.get("name", "Settlement"),
                    settlement.get("defense_posture", "normal"),
                    len(settlement.get("residents", [])),
                    len(settlement.get("jobs", [])),
                    len(settlement.get("alerts", [])),
                ),
                title="Settlement",
                border_style="bright_blue",
            )
        )
    console.print("[dim]Commands: look around, talk <npc>, assign <name> to <job>, build <kind>, defend, travel <place>, save <slot>, load <slot>, quit[/dim]")


def main() -> None:
    console.print(Rule("[bold bright_yellow]EMBER RPG[/bold bright_yellow]", style="bright_yellow"))
    creation = character_creation()
    client = CampaignClient()
    snapshot = client.create_campaign(
        player_name=creation["name"],
        player_class=creation["player_class"],
        adapter_id=creation["adapter_id"],
    )
    history: list[str] = [snapshot.get("narrative", "")]

    while True:
        _print_scene(snapshot, history)
        command = Prompt.ask("[bold green]>[/bold green]", default="look around").strip()
        if not command:
            command = "look around"
        lower = command.lower()
        if lower in {"quit", "exit"}:
            break
        if lower.startswith("save"):
            slot_name = command[4:].strip() or "quicksave"
            metadata = client.save_campaign(snapshot["campaign_id"], slot_name, creation["name"])
            _append(history, "Saved to %s." % metadata.get("slot_name", slot_name))
            continue
        if lower.startswith("load "):
            save_id = command[5:].strip()
            snapshot = client.load_campaign(save_id)
            _append(history, snapshot.get("narrative", "Loaded."))
            continue
        response = client.submit_command(snapshot["campaign_id"], command)
        snapshot = response
        _append(history, response.get("narrative", ""))


if __name__ == "__main__":
    main()
