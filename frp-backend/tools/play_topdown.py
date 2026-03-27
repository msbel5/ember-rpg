#!/usr/bin/env python3
"""Campaign-first top-down terminal client for Ember RPG."""
from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass
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
from rich.layout import Layout
from rich.markup import escape
from rich.panel import Panel
from rich.prompt import Prompt
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from engine.map import TileType
from tools.campaign_client import CampaignClient

MAP_WIDTH = 40
MAP_HEIGHT = 20
VISIBLE_NARRATIVES = 14

console = Console(force_terminal=True)

ARROW_COMMANDS = {
    readchar.key.UP: "move north",
    readchar.key.DOWN: "move south",
    readchar.key.LEFT: "move west",
    readchar.key.RIGHT: "move east",
}

CLASS_OPTIONS = {
    "1": ("warrior", {"MIG": 16, "END": 14, "AGI": 10, "MND": 8, "INS": 8, "PRE": 10}),
    "2": ("rogue", {"MIG": 10, "END": 10, "AGI": 16, "MND": 8, "INS": 14, "PRE": 10}),
    "3": ("mage", {"MIG": 8, "END": 8, "AGI": 10, "MND": 16, "INS": 14, "PRE": 10}),
    "4": ("priest", {"MIG": 10, "END": 12, "AGI": 8, "MND": 14, "INS": 16, "PRE": 10}),
}

ADAPTER_OPTIONS = {
    "1": ("fantasy_ember", "Fantasy Ember"),
    "2": ("scifi_frontier", "Sci-Fi Frontier"),
}

TERRAIN_GLYPHS = {
    "road": ("=", "yellow"),
    "cobble": ("=", "yellow"),
    "cobblestone": ("=", "yellow"),
    "wall": ("#", "grey35"),
    "door": ("+", "yellow"),
    "floor": (".", "grey55"),
    "wood_floor": (".", "grey60"),
    "stone_floor": (".", "grey50"),
    "grass": (",", "green"),
    "water": ("~", "blue"),
    "tree": ("T", "green"),
    "well": ("O", "bright_cyan"),
    "fountain": ("O", "bright_cyan"),
}

LEGACY_TILE_GLYPHS = {
    TileType.FLOOR: (".", "grey55"),
    TileType.WALL: ("#", "grey35"),
    TileType.DOOR: ("+", "yellow"),
    TileType.CORRIDOR: (".", "grey45"),
    TileType.STAIRS_DOWN: (">", "bright_cyan"),
    TileType.STAIRS_UP: ("<", "bright_cyan"),
    TileType.WATER: ("~", "blue"),
    TileType.TREE: ("T", "green"),
    TileType.ROAD: ("=", "yellow"),
    TileType.EMPTY: (" ", "black"),
}


@dataclass
class CampaignScreenState:
    snapshot: dict[str, Any]
    narrative_history: list[str]

    @property
    def campaign_id(self) -> str:
        return str(self.snapshot.get("campaign_id", ""))

    @property
    def campaign(self) -> dict[str, Any]:
        return dict(self.snapshot.get("campaign") or {})


class MapState:
    """Compatibility wrapper that accepts either a legacy GameSession or a campaign snapshot."""

    def __init__(self, source: Any):
        self.source = source
        self.player_pos = (0, 0)
        self.width = 0
        self.height = 0
        self.tiles: list[list[Any]] = []
        self.entities: list[dict[str, Any]] = []
        self.player_name = "Player"
        self.location = "Unknown"
        self._from_source(source)

    def _from_source(self, source: Any) -> None:
        if hasattr(source, "map_data") and hasattr(source, "player"):
            self._from_legacy_session(source)
            return
        campaign = source.get("campaign", source) if isinstance(source, dict) else {}
        self._from_campaign(campaign)

    def _from_legacy_session(self, session: Any) -> None:
        self.width = int(getattr(session.map_data, "width", 0))
        self.height = int(getattr(session.map_data, "height", 0))
        self.tiles = []
        for y in range(self.height):
            row = []
            for x in range(self.width):
                row.append(session.map_data.get_tile(x, y))
            self.tiles.append(row)
        self.player_pos = tuple(getattr(session.player_entity, "position", tuple(session.position)))
        self.player_name = session.player.name
        self.location = session.dm_context.location
        if getattr(session, "spatial_index", None) is not None:
            for entity in session.spatial_index.all_entities():
                if entity.id == "player":
                    continue
                self.entities.append(
                    {
                        "id": entity.id,
                        "name": entity.name,
                        "position": [entity.position[0], entity.position[1]],
                        "glyph": entity.glyph,
                        "color": entity.color,
                        "bucket": "enemy" if getattr(entity, "disposition", "") == "hostile" else "npc",
                    }
                )

    def _from_campaign(self, campaign: dict[str, Any]) -> None:
        player = dict(campaign.get("player") or {})
        map_payload = dict(campaign.get("map_data") or {})
        self.width = int(map_payload.get("width", 0))
        self.height = int(map_payload.get("height", 0))
        self.tiles = list(map_payload.get("tiles") or [])
        self.player_pos = tuple(player.get("position", map_payload.get("spawn_point", [0, 0])))
        self.player_name = str(player.get("name", "Player"))
        self.location = str(campaign.get("location", "Unknown"))
        self.entities = list(campaign.get("world_entities") or [])

    def bounds(self) -> tuple[int, int, int, int]:
        px, py = self.player_pos
        half_w = MAP_WIDTH // 2
        half_h = MAP_HEIGHT // 2
        min_x = max(0, px - half_w)
        min_y = max(0, py - half_h)
        max_x = min(self.width, min_x + MAP_WIDTH)
        max_y = min(self.height, min_y + MAP_HEIGHT)
        min_x = max(0, max_x - MAP_WIDTH)
        min_y = max(0, max_y - MAP_HEIGHT)
        return min_x, min_y, max_x, max_y

    def entity_at(self, x: int, y: int) -> dict[str, Any] | None:
        for entity in self.entities:
            position = entity.get("position", [None, None])
            if len(position) >= 2 and int(position[0]) == x and int(position[1]) == y:
                return entity
        return None


def hp_bar(current: int, maximum: int, width: int = 16) -> str:
    filled = int(width * current / max(maximum, 1))
    filled = min(width, max(0, filled))
    return "[%s%s] %d/%d" % ("#" * filled, "-" * (width - filled), current, maximum)


def render_header(session_or_campaign: Any) -> Panel:
    if hasattr(session_or_campaign, "to_dict"):
        snapshot = session_or_campaign.to_dict()
        player = snapshot["player"]
        location = snapshot.get("location", getattr(session_or_campaign.dm_context, "location", "Unknown"))
        world_line = "Legacy Session"
    else:
        campaign = session_or_campaign.get("campaign", session_or_campaign)
        player = campaign.get("player", {})
        world = campaign.get("world", {})
        location = campaign.get("location", "Unknown")
        world_line = "%s | %s" % (str(world.get("adapter_id", "campaign")), str(world.get("active_region_id", "")))

    classes = player.get("classes", {})
    class_name = "Adventurer"
    if isinstance(classes, dict) and classes:
        class_name = str(next(iter(classes.keys()))).capitalize()
    elif player.get("player_class"):
        class_name = str(player["player_class"]).capitalize()

    ap_payload = player.get("ap") or {
        "current": int(player.get("action_points", player.get("ap", 0))),
        "max": int(player.get("max_action_points", player.get("max_ap", 0))),
    }
    header = (
        f"{player.get('name', 'Unknown')}  Lv.{player.get('level', 1)} {class_name}\n"
        f"HP: {hp_bar(int(player.get('hp', 0)), int(player.get('max_hp', 1)))}  "
        f"AP: {ap_payload.get('current', 0)}/{ap_payload.get('max', 0)}  "
        f"Gold: {player.get('gold', 0)}\n"
        f"{location}  |  {world_line}"
    )
    return Panel(header, title="[bold bright_white]Status[/bold bright_white]", border_style="bright_blue")


def render_map(map_state: MapState) -> Panel:
    text = Text()
    min_x, min_y, max_x, max_y = map_state.bounds()
    for y in range(min_y, max_y):
        for x in range(min_x, max_x):
            if (x, y) == tuple(map_state.player_pos):
                text.append("@", style="bold bright_white")
                continue
            entity = map_state.entity_at(x, y)
            if entity is not None:
                glyph = str(entity.get("glyph", str(entity.get("name", "?"))[:1].upper() or "?"))
                color = "red" if str(entity.get("disposition", "")).lower() == "hostile" else "cyan"
                text.append(glyph[:1], style="bold %s" % color)
                continue
            tile = map_state.tiles[y][x] if y < len(map_state.tiles) and x < len(map_state.tiles[y]) else "grass"
            glyph, color = _tile_style(tile)
            text.append(glyph, style=color)
        if y < max_y - 1:
            text.append("\n")
    return Panel(text, title="[bold bright_white]Region[/bold bright_white]", border_style="bright_blue")


def render_narrative(history: list[str]) -> Panel:
    visible = history[-VISIBLE_NARRATIVES:]
    text = Text()
    for line in visible:
        style = "white"
        lower = line.lower()
        if line.startswith(">"):
            style = "green"
        elif "attack" in lower or "damage" in lower or "combat" in lower:
            style = "bold red"
        elif line.startswith("["):
            style = "yellow"
        text.append(line + "\n", style=style)
    return Panel(text, title="[bold bright_white]Narrative[/bold bright_white]", border_style="bright_blue")


def render_settlement(campaign: dict[str, Any]) -> Panel:
    settlement = dict(campaign.get("settlement") or {})
    text = Text()
    if not settlement:
        text.append("No settlement data.", style="dim")
        return Panel(text, title="[bold bright_white]Settlement[/bold bright_white]", border_style="bright_blue")
    text.append(
        "%s | Pop %s | %s\n\n"
        % (
            settlement.get("name", "Settlement"),
            settlement.get("population", len(settlement.get("residents", []))),
            str(settlement.get("defense_posture", "normal")).capitalize(),
        )
    )
    text.append("Residents\n", style="bold")
    for resident in settlement.get("residents", [])[:4]:
        text.append("- %s: %s\n" % (resident.get("name", "Resident"), resident.get("assignment", resident.get("role", "idle"))))
    text.append("\nJobs\n", style="bold")
    for job in settlement.get("jobs", [])[:4]:
        text.append("- %s [%s]\n" % (str(job.get("kind", "job")).capitalize(), job.get("status", "queued")))
    text.append("\nAlerts\n", style="bold")
    alerts = settlement.get("alerts", [])
    if alerts:
        for alert in alerts[:4]:
            text.append("- %s\n" % alert, style="yellow")
    else:
        text.append("- None\n", style="dim")
    return Panel(text, title="[bold bright_white]Settlement[/bold bright_white]", border_style="bright_blue")


def render_commands() -> Panel:
    commands = "move/look/talk/attack/travel/assign/build/defend/harvest/save/load/quit"
    return Panel(commands, title="[bold]Commands[/bold]", border_style="bright_blue", height=3)


def render_full(screen_state: CampaignScreenState) -> Layout:
    map_state = MapState(screen_state.snapshot)
    layout = Layout()
    layout.split_column(Layout(name="header", size=5), Layout(name="main"), Layout(name="footer", size=3))
    layout["header"].update(render_header(screen_state.snapshot))
    layout["footer"].update(render_commands())
    layout["main"].split_row(Layout(name="map", ratio=2), Layout(name="sidebar", ratio=1))
    layout["map"].update(render_map(map_state))
    layout["sidebar"].split_column(Layout(name="narrative", ratio=3), Layout(name="settlement", ratio=2))
    layout["narrative"].update(render_narrative(screen_state.narrative_history))
    layout["settlement"].update(render_settlement(screen_state.campaign))
    return layout


def character_creation() -> dict[str, Any]:
    console.print()
    console.print(Rule("[bold bright_yellow]EMBER RPG[/bold bright_yellow]", style="bright_yellow"))
    name = Prompt.ask("[bold green]Name[/bold green]", default="Stranger").strip() or "Stranger"

    class_table = Table(title="Class", show_header=True, expand=True)
    class_table.add_column("#", justify="center", width=3)
    class_table.add_column("Class")
    class_table.add_column("Notes")
    class_table.add_row("1", "Warrior", "Frontline commander")
    class_table.add_row("2", "Rogue", "Scout and infiltrator")
    class_table.add_row("3", "Mage", "Arcane specialist")
    class_table.add_row("4", "Priest", "Support and healing")
    console.print(class_table)

    adapter_table = Table(title="Adapter", show_header=True, expand=True)
    adapter_table.add_column("#", justify="center", width=3)
    adapter_table.add_column("World")
    adapter_table.add_row("1", "Fantasy Ember")
    adapter_table.add_row("2", "Sci-Fi Frontier")
    console.print(adapter_table)

    class_choice = Prompt.ask("[bold green]Select class[/bold green]", choices=list(CLASS_OPTIONS.keys()), default="1")
    adapter_choice = Prompt.ask("[bold green]Select adapter[/bold green]", choices=list(ADAPTER_OPTIONS.keys()), default="1")
    player_class, stats = CLASS_OPTIONS[class_choice]
    adapter_id, _adapter_name = ADAPTER_OPTIONS[adapter_choice]
    map_type = "town" if adapter_id == "fantasy_ember" else "wilderness"
    return {
        "name": name,
        "player_class": player_class,
        "adapter_id": adapter_id,
        "map_type": map_type,
        "stats": stats,
    }


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


def _tile_style(tile: Any) -> tuple[str, str]:
    if tile in LEGACY_TILE_GLYPHS:
        return LEGACY_TILE_GLYPHS[tile]
    return TERRAIN_GLYPHS.get(str(tile).lower(), ("?", "white"))


def _append_history(history: list[str], line: str) -> None:
    cleaned = line.strip()
    if not cleaned:
        return
    history.append(cleaned)
    del history[:-60]


def _handle_meta_command(client: CampaignClient, screen_state: CampaignScreenState, command: str) -> bool:
    lower = command.lower().strip()
    if lower in {"quit", "exit"}:
        raise SystemExit(0)
    if lower in {"help", "?"}:
        _append_history(screen_state.narrative_history, "[system] Use freeform RPG commands or settlement orders like 'assign Smith to hauling'.")
        return True
    if lower.startswith("save"):
        slot_name = command[4:].strip() or "quicksave"
        metadata = client.save_campaign(screen_state.campaign_id, slot_name, str(screen_state.campaign.get("player", {}).get("name", "player")))
        _append_history(screen_state.narrative_history, "[system] Saved to %s." % metadata.get("slot_name", slot_name))
        return True
    if lower == "saves":
        saves = client.list_saves(screen_state.campaign_id)
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
    if lower.startswith("load "):
        save_id = command[5:].strip()
        if save_id:
            screen_state.snapshot = client.load_campaign(save_id)
            _append_history(screen_state.narrative_history, screen_state.snapshot.get("narrative", "Loaded."))
        return True
    return False


def main() -> None:
    client = CampaignClient()
    creation = character_creation()
    snapshot = client.create_campaign(
        player_name=creation["name"],
        player_class=creation["player_class"],
        adapter_id=creation["adapter_id"],
    )
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
