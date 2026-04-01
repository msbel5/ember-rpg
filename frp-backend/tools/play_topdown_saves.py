"""Save browser helpers for the top-down terminal client."""
from __future__ import annotations

from typing import Any, Callable


def append_history(history: list[str], line: str) -> None:
    cleaned = line.strip()
    if not cleaned:
        return
    history.append(cleaned)
    del history[:-60]


def current_player_id(snapshot: dict[str, Any]) -> str:
    campaign = snapshot.get("campaign", {}) if isinstance(snapshot, dict) else {}
    if isinstance(campaign, dict):
        player = campaign.get("player", {})
        if isinstance(player, dict):
            return str(player.get("name", "player"))
    return "player"


def campaign_compatible_saves(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    compatible: list[dict[str, Any]] = []
    for entry in entries:
        if isinstance(entry, dict) and bool(entry.get("campaign_compatible", True)):
            compatible.append(entry)
    return compatible


def resolve_save_choice(choice: str, saves: list[dict[str, Any]]) -> str:
    cleaned = choice.strip()
    if not cleaned:
        return ""
    if cleaned.isdigit():
        index = int(cleaned) - 1
        if 0 <= index < len(saves):
            return str(saves[index].get("save_id") or saves[index].get("slot_name", ""))
    for entry in saves:
        save_id = str(entry.get("save_id", "")).strip()
        slot_name = str(entry.get("slot_name", "")).strip()
        if cleaned == save_id or cleaned == slot_name:
            return save_id or slot_name
    return ""


def _print_save_browser(console: Any, table_cls: Any, player_id: str, saves: list[dict[str, Any]]) -> None:
    table = table_cls(title=f"Recent Saves for {player_id}", show_header=True, expand=True)
    table.add_column("#", justify="center", width=4)
    table.add_column("Slot")
    table.add_column("Save ID")
    table.add_column("Location")
    table.add_column("Updated")
    for index, entry in enumerate(saves, start=1):
        table.add_row(
            str(index),
            str(entry.get("slot_name", entry.get("save_id", "save"))),
            str(entry.get("save_id", "")),
            str(entry.get("location", "Unknown")),
            str(entry.get("timestamp", "")),
        )
    console.print(table)


def browse_campaign_saves(
    client: Any,
    default_player_id: str = "",
    *,
    prompt_cls: Any,
    console: Any,
    panel_cls: Any,
    table_cls: Any,
    ask_choice: Callable[[str, list[str], str], str],
    character_creation_fn: Callable[[Any], dict[str, Any]],
) -> dict[str, Any] | None:
    player_id = default_player_id.strip() or "player"
    while True:
        try:
            typed_player_id = prompt_cls.ask("[bold green]Player[/bold green]", default=player_id).strip()
        except (EOFError, KeyboardInterrupt):
            return None
        player_id = typed_player_id or player_id or "player"
        try:
            discovered_saves = list(client.list_saves_for_player(player_id))
        except Exception as exc:
            console.print(panel_cls(str(exc), title="Load Failed", border_style="red"))
            action = ask_choice("Retry, New, or Quit?", ["retry", "new", "quit"], "retry")
            if action == "retry":
                continue
            if action == "new":
                return character_creation_fn(client)
            return None
        saves = campaign_compatible_saves(discovered_saves)
        if not saves:
            message = (
                f"No campaign saves found for {player_id}."
                if not discovered_saves
                else f"Only legacy or incompatible saves were found for {player_id}."
            )
            console.print(panel_cls(message, title="Load", border_style="yellow"))
            action = ask_choice("Retry, New, or Quit?", ["retry", "new", "quit"], "retry")
            if action == "retry":
                continue
            if action == "new":
                return character_creation_fn(client)
            return None

        _print_save_browser(console, table_cls, player_id, saves)
        while True:
            try:
                choice = prompt_cls.ask("[bold green]Select save number or id[/bold green]", default="1").strip()
            except (EOFError, KeyboardInterrupt):
                return None
            if choice.lower() in {"new", "quit", "back"}:
                if choice.lower() == "new":
                    return character_creation_fn(client)
                return None
            save_id = resolve_save_choice(choice, saves)
            if not save_id:
                console.print(panel_cls("Unknown save selection. Enter a number or save id.", title="Load", border_style="yellow"))
                continue
            try:
                return client.load_campaign(save_id)
            except Exception as exc:
                console.print(panel_cls(str(exc), title="Load Failed", border_style="red"))
                action = ask_choice("Retry, New, or Quit?", ["retry", "new", "quit"], "retry")
                if action == "retry":
                    break
                if action == "new":
                    return character_creation_fn(client)
                return None

