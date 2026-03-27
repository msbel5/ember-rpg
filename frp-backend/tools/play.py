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
from tools.play_topdown import browse_campaign_saves, render_character_sheet, render_header, start_or_load_campaign

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
    console.print(render_character_sheet(snapshot))
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


def _current_player_id(snapshot: dict[str, object]) -> str:
    campaign = snapshot.get("campaign", {}) if isinstance(snapshot, dict) else {}
    if isinstance(campaign, dict):
        player = campaign.get("player", {})
        if isinstance(player, dict):
            return str(player.get("name", "player"))
    return "player"


def _handle_meta_command(client: CampaignClient, snapshot: dict, history: list[str], command: str) -> tuple[bool, dict]:
    lower = command.lower().strip()
    if lower == "save" or lower.startswith("save "):
        slot_name = command[4:].strip() or "quicksave"
        metadata = client.save_campaign(str(snapshot.get("campaign_id", "")), slot_name, _current_player_id(snapshot))
        _append(history, "Saved to %s." % metadata.get("slot_name", slot_name))
        return True, snapshot
    if lower == "load" or lower.startswith("load "):
        save_id = command[5:].strip()
        if not save_id:
            loaded = browse_campaign_saves(client, _current_player_id(snapshot))
            if loaded is None:
                return True, snapshot
            history.clear()
            _append(history, loaded.get("narrative", "Loaded."))
            return True, loaded
        try:
            loaded = client.load_campaign(save_id)
            history.clear()
            _append(history, loaded.get("narrative", "Loaded."))
            return True, loaded
        except Exception as exc:
            _append(history, "Load failed: %s" % exc)
            return True, snapshot
    if lower == "saves":
        try:
            saves = client.list_saves_for_player(_current_player_id(snapshot))
        except Exception as exc:
            _append(history, "Save listing failed: %s" % exc)
            return True, snapshot
        if not saves:
            _append(history, "No save slots found.")
            return True, snapshot
        for entry in saves[:5]:
            _append(
                history,
                "%s | %s | %s"
                % (
                    entry.get("slot_name", entry.get("save_id", "save")),
                    entry.get("location", "Unknown"),
                    entry.get("timestamp", ""),
                ),
            )
        return True, snapshot
    return False, snapshot


def main() -> None:
    console.print(Rule("[bold bright_yellow]EMBER RPG[/bold bright_yellow]", style="bright_yellow"))
    client = CampaignClient()
    snapshot = start_or_load_campaign(client)
    if snapshot is None:
        return
    history: list[str] = [snapshot.get("narrative", "")]

    while True:
        _print_scene(snapshot, history)
        command = Prompt.ask("[bold green]>[/bold green]", default="look around").strip()
        if not command:
            command = "look around"
        lower = command.lower()
        if lower in {"quit", "exit"}:
            break
        handled, snapshot = _handle_meta_command(client, snapshot, history, command)
        if handled:
            continue
        response = client.submit_command(snapshot["campaign_id"], command)
        snapshot = response
        _append(history, response.get("narrative", ""))


if __name__ == "__main__":
    main()
