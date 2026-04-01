#!/usr/bin/env python3
"""Campaign-first top-down terminal client for Ember RPG."""
from __future__ import annotations

import os
import sys
import time
from typing import Any

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

import readchar

from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.prompt import Prompt
from rich.rule import Rule
from rich.table import Table

from engine.core.character_creation import ABILITY_ORDER, assign_stats_to_class
from engine.core.creation_catalog import get_creation_catalog
from tools.campaign_client import CampaignClient
from tools.play_topdown_saves import (
    append_history as _append_history,
    browse_campaign_saves as _browse_campaign_saves,
    campaign_compatible_saves as _campaign_compatible_saves,
    current_player_id as _current_player_id,
)
from tools.play_topdown_view import (
    CampaignScreenState,
    MapState,
    build_character_sheet,
    render_character_sheet,
    render_full,
    render_header,
    render_map,
)

console = Console(force_terminal=True)

ARROW_COMMANDS = {
    readchar.key.UP: "move north",
    readchar.key.DOWN: "move south",
    readchar.key.LEFT: "move west",
    readchar.key.RIGHT: "move east",
}

CREATION_CATALOG = get_creation_catalog()


def _indexed_options(entries: list[dict[str, Any]]) -> dict[str, tuple[str, str]]:
    return {
        str(index + 1): (str(entry.get("id", "")), str(entry.get("label", entry.get("id", ""))))
        for index, entry in enumerate(entries)
    }


def _default_option_key(options: dict[str, tuple[str, str]], default_id: str) -> str:
    for key, (option_id, _label) in options.items():
        if option_id == default_id:
            return key
    return next(iter(options.keys()), "")


CLASS_OPTIONS = _indexed_options(list(CREATION_CATALOG.get("class_catalog", [])))
ADAPTER_OPTIONS = _indexed_options(list(CREATION_CATALOG.get("adapter_catalog", [])))

ABILITY_LABELS = {
    "MIG": "Might",
    "END": "Endurance",
    "AGI": "Agility",
    "MND": "Mind",
    "INS": "Insight",
    "PRE": "Presence",
}


def _ask_choice(prompt: str, options: list[str], default: str) -> str:
    if len(options) == 1:
        return options[0]
    return Prompt.ask(prompt, choices=options, default=default)


def _ask_yes_no(prompt: str, default: str = "yes") -> str:
    return Prompt.ask(prompt, choices=["yes", "no"], default=default)


def _parse_optional_int(value: str) -> int | None:
    cleaned = value.strip()
    if not cleaned:
        return None
    return int(cleaned)


def _print_creation_snapshot(state: dict[str, Any]) -> None:
    sheet = build_character_sheet(state)
    summary = Table(title="Creation Summary", show_header=False, expand=True)
    summary.add_column("Field")
    summary.add_column("Value")
    summary.add_row("Recommended class", str(state.get("recommended_class", "")))
    summary.add_row("Recommended alignment", str(state.get("recommended_alignment", "")))
    summary.add_row("Recommended skills", ", ".join(state.get("recommended_skills") or []))
    summary.add_row("Current roll", ", ".join(str(v) for v in state.get("current_roll") or []))
    summary.add_row("Saved roll", ", ".join(str(v) for v in state.get("saved_roll") or []))
    summary.add_row("Final class", f"{sheet['class']} / {sheet['alignment']}")
    console.print(summary)


def browse_campaign_saves(client: CampaignClient, default_player_id: str = "") -> dict[str, Any] | None:
    return _browse_campaign_saves(
        client,
        default_player_id,
        prompt_cls=Prompt,
        console=console,
        panel_cls=Panel,
        table_cls=Table,
        ask_choice=_ask_choice,
        character_creation_fn=character_creation,
    )


def _prompt_questionnaire(client: CampaignClient, creation_state: dict[str, Any]) -> dict[str, Any]:
    for question in creation_state.get("questions", []):
        answers = list(question.get("answers") or [])
        if not answers:
            continue
        answer_choices = [str(answer.get("id")) for answer in answers if answer.get("id")]
        answer_default = answer_choices[0]
        question_panel = Table(title=str(question.get("text", question.get("id", "Question"))), show_header=True, expand=True)
        question_panel.add_column("Choice")
        question_panel.add_column("Text")
        for answer in answers:
            question_panel.add_row(str(answer.get("id", "")), str(answer.get("text", "")))
        console.print(question_panel)
        choice = _ask_choice(f"Answer for {question.get('id', 'question')}", answer_choices, answer_default)
        creation_state = client.answer_creation(str(creation_state["creation_id"]), str(question["id"]), choice)
        _print_creation_snapshot(creation_state)
    return creation_state


def _prompt_roll_controls(client: CampaignClient, creation_state: dict[str, Any]) -> dict[str, Any]:
    while True:
        roll = ", ".join(str(v) for v in creation_state.get("current_roll") or [])
        saved = ", ".join(str(v) for v in creation_state.get("saved_roll") or [])
        console.print(Panel(f"Current roll: {roll}\nSaved roll: {saved}", title="Dice", border_style="bright_blue"))
        action = _ask_choice("Roll action", ["keep", "reroll", "save", "swap"], "keep")
        try:
            if action == "reroll":
                creation_state = client.reroll_creation(str(creation_state["creation_id"]))
                continue
            if action == "save":
                creation_state = client.save_creation_roll(str(creation_state["creation_id"]))
                continue
            if action == "swap":
                creation_state = client.swap_creation_roll(str(creation_state["creation_id"]))
                continue
        except ValueError as exc:
            console.print(Panel(str(exc), title="Creation Warning", border_style="yellow"))
            time.sleep(0.4)
        return creation_state


def _prompt_stat_assignment(creation_state: dict[str, Any], auto_assign: bool) -> dict[str, int]:
    rolled = [int(value) for value in creation_state.get("current_roll") or []]
    if not rolled:
        return {ability: 10 for ability in ABILITY_ORDER}
    if auto_assign:
        return assign_stats_to_class(rolled, str(creation_state.get("recommended_class", "warrior")))

    ordered = sorted(rolled, reverse=True)
    assigned: dict[str, int] = {}
    for index, ability in enumerate(ABILITY_ORDER):
        default_value = ordered[index] if index < len(ordered) else 10
        value = Prompt.ask(f"Assign {ability}", default=str(default_value)).strip()
        try:
            assigned[ability] = int(value or default_value)
        except ValueError:
            assigned[ability] = int(default_value)
    return assigned


def _finalize_creation(
    client: CampaignClient,
    creation_state: dict[str, Any],
    name: str,
    adapter_id: str,
    profile_id: str,
    seed: int | None,
) -> dict[str, Any]:
    recommended_class = str(creation_state.get("recommended_class", CREATION_CATALOG.get("default_class_id", "")))
    recommended_alignment = str(creation_state.get("recommended_alignment", "NN"))
    recommended_skills = list(creation_state.get("recommended_skills") or [])

    class_choices = [recommended_class] + [value for value, _label in CLASS_OPTIONS.values() if value != recommended_class]
    chosen_class = _ask_choice("Class", class_choices, recommended_class)
    chosen_alignment = Prompt.ask("[bold green]Alignment[/bold green]", default=recommended_alignment).strip() or recommended_alignment
    skills_text = Prompt.ask("[bold green]Skills[/bold green] (comma-separated)", default=", ".join(recommended_skills)).strip()
    chosen_skills = [skill.strip() for skill in skills_text.split(",") if skill.strip()] or recommended_skills
    auto_assign = _ask_yes_no("Auto assign rolled stats?", "yes") == "yes"
    assigned_stats = _prompt_stat_assignment(creation_state, auto_assign)

    final_snapshot = client.finalize_creation(
        str(creation_state["creation_id"]),
        player_name=name,
        player_class=chosen_class,
        alignment=chosen_alignment,
        skill_proficiencies=chosen_skills,
        assigned_stats=assigned_stats,
        adapter_id=adapter_id,
        profile_id=profile_id,
        seed=seed,
    )
    final_snapshot["creation_state"] = dict(creation_state)
    final_snapshot["creation_state"]["final_class"] = chosen_class
    final_snapshot["creation_state"]["final_alignment"] = chosen_alignment
    final_snapshot["creation_state"]["final_skills"] = chosen_skills
    final_snapshot["creation_state"]["assigned_stats"] = dict(assigned_stats)
    final_snapshot["character_sheet"] = client.build_character_sheet(final_snapshot, creation_state=final_snapshot["creation_state"])
    final_snapshot["name"] = name
    final_snapshot["player_class"] = chosen_class
    final_snapshot["adapter_id"] = adapter_id
    final_snapshot["profile_id"] = profile_id
    final_snapshot["stats"] = dict(assigned_stats)
    final_snapshot["map_type"] = (
        str(final_snapshot.get("map_type", final_snapshot.get("campaign", {}).get("map_data", {}).get("metadata", {}).get("map_type", "")))
        or "campaign_region"
    )
    return final_snapshot


def start_or_load_campaign(client: CampaignClient | None = None) -> dict[str, Any] | None:
    client = client or CampaignClient()
    console.print(Rule("[bold bright_yellow]EMBER RPG[/bold bright_yellow]", style="bright_yellow"))
    mode = _ask_choice("Start mode", ["new", "load", "quit"], "new")
    if mode == "quit":
        return None
    if mode == "load":
        return browse_campaign_saves(client)
    return character_creation(client)


def character_creation(client: CampaignClient | None = None) -> dict[str, Any]:
    client = client or CampaignClient()
    console.print()
    name = Prompt.ask("[bold green]Name[/bold green]", default="Stranger").strip() or "Stranger"

    adapter_table = Table(title="Adapter", show_header=True, expand=True)
    adapter_table.add_column("#", justify="center", width=3)
    adapter_table.add_column("World")
    for key, (_adapter_id, adapter_label) in ADAPTER_OPTIONS.items():
        adapter_table.add_row(key, adapter_label)
    console.print(adapter_table)

    adapter_choice = Prompt.ask(
        "[bold green]Select adapter[/bold green]",
        choices=list(ADAPTER_OPTIONS.keys()),
        default=_default_option_key(ADAPTER_OPTIONS, str(CREATION_CATALOG.get("default_adapter_id", ""))),
    )
    profile_id = Prompt.ask("[bold green]Profile[/bold green]", default=str(CREATION_CATALOG.get("default_profile_id", ""))).strip()
    profile_id = profile_id or str(CREATION_CATALOG.get("default_profile_id", ""))
    seed_text = Prompt.ask("[bold green]Seed[/bold green]", default="").strip()
    try:
        seed = _parse_optional_int(seed_text)
    except ValueError:
        console.print(Panel("Invalid seed. Starting with random seed.", title="Seed Warning", border_style="yellow"))
        seed = None
    adapter_id, _adapter_name = ADAPTER_OPTIONS[adapter_choice]

    creation_state = client.start_creation(name, location="", adapter_id=adapter_id, profile_id=profile_id, seed=seed)
    _print_creation_snapshot(creation_state)
    creation_state = _prompt_questionnaire(client, creation_state)
    creation_state = _prompt_roll_controls(client, creation_state)
    final_snapshot = _finalize_creation(client, creation_state, name, adapter_id, profile_id, seed)
    final_snapshot["recommended_class"] = str(creation_state.get("recommended_class", "warrior"))
    final_snapshot["recommended_alignment"] = str(creation_state.get("recommended_alignment", "NN"))
    final_snapshot["recommended_skills"] = list(creation_state.get("recommended_skills") or [])
    final_snapshot["questionnaire"] = list(creation_state.get("answers") or [])
    return final_snapshot


def read_input() -> str:
    console.print()
    sys.stdout.write("\033[32m> \033[0m")
    sys.stdout.flush()
    buf: list[str] = []
    while True:
        key = readchar.readkey()
        if key in ARROW_COMMANDS:
            sys.stdout.write("\r\033[K")
            cmd = ARROW_COMMANDS[key]
            sys.stdout.write(f"\033[32m> \033[0m{cmd}\n")
            sys.stdout.flush()
            return cmd
        if key in ("\r", "\n", readchar.key.ENTER):
            sys.stdout.write("\n")
            sys.stdout.flush()
            return "".join(buf).strip()
        if key in ("\x7f", "\x08", readchar.key.BACKSPACE):
            if buf:
                buf.pop()
                sys.stdout.write("\b \b")
                sys.stdout.flush()
            continue
        if key == readchar.key.CTRL_C:
            raise KeyboardInterrupt
        if len(key) == 1 and key.isprintable():
            buf.append(key)
            sys.stdout.write(key)
            sys.stdout.flush()


def _handle_meta_command(client: CampaignClient, screen_state: CampaignScreenState, command: str) -> bool:
    lower = command.lower().strip()
    if lower in {"quit", "exit"}:
        raise SystemExit(0)
    if lower in {"help", "?"}:
        _append_history(screen_state.narrative_history, "[system] Use freeform RPG commands or settlement orders like 'assign Smith to hauling'.")
        return True
    if lower == "save" or lower.startswith("save "):
        slot_name = command[4:].strip() or "quicksave"
        try:
            metadata = client.save_campaign(screen_state.campaign_id, slot_name, _current_player_id(screen_state.snapshot))
            _append_history(screen_state.narrative_history, "[system] Saved to %s." % metadata.get("slot_name", slot_name))
        except Exception as exc:
            _append_history(screen_state.narrative_history, "[system] Save failed: %s" % exc)
        return True
    if lower == "saves":
        saves = client.list_saves_for_player(_current_player_id(screen_state.snapshot))
        saves = _campaign_compatible_saves(list(saves))
        if not saves:
            _append_history(screen_state.narrative_history, "[system] No save slots found.")
        else:
            for entry in saves[:5]:
                _append_history(
                    screen_state.narrative_history,
                    "[system] %s | %s | %s"
                    % (
                        entry.get("slot_name", entry.get("save_id", "save")),
                        entry.get("location", "Unknown"),
                        entry.get("timestamp", ""),
                    ),
                )
        return True
    if lower == "load" or lower.startswith("load "):
        save_id = command[5:].strip()
        if not save_id:
            loaded = browse_campaign_saves(client, _current_player_id(screen_state.snapshot))
            if loaded is None:
                return True
            screen_state.snapshot = loaded
            screen_state.narrative_history = []
            _append_history(screen_state.narrative_history, screen_state.snapshot.get("narrative", "Loaded."))
            return True
        try:
            screen_state.snapshot = client.load_campaign(save_id)
            screen_state.narrative_history = []
            _append_history(screen_state.narrative_history, screen_state.snapshot.get("narrative", "Loaded."))
        except Exception as exc:
            _append_history(screen_state.narrative_history, "[system] Load failed: %s" % exc)
        return True
    return False


def main() -> None:
    client = CampaignClient()
    snapshot = start_or_load_campaign(client)
    if snapshot is None:
        return
    history = [snapshot.get("narrative", "")]
    screen_state = CampaignScreenState(snapshot=snapshot, narrative_history=history)

    while True:
        console.clear()
        console.print(render_full(screen_state))
        try:
            command = read_input()
        except KeyboardInterrupt:
            console.print("\n[bold yellow]Exiting Ember RPG.[/bold yellow]")
            break
        if not command:
            command = "look around"
        _append_history(screen_state.narrative_history, "> %s" % escape(command))
        if _handle_meta_command(client, screen_state, command):
            continue
        response = client.submit_command(screen_state.campaign_id, command)
        screen_state.snapshot = response
        _append_history(screen_state.narrative_history, response.get("narrative", ""))


if __name__ == "__main__":
    main()
