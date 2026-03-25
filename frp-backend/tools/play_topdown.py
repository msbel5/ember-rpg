#!/usr/bin/env python3
"""
Ember RPG - Top-Down ASCII RPG Terminal Client
A split-panel Rich terminal client with map viewport, narrative, and nearby panels.
Run: python -m tools.play_topdown   (from frp-backend/)
"""
import sys
import os

# Force UTF-8 output on Windows
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Ensure project root is on path
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

import time
import readchar

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.layout import Layout
from rich.prompt import Prompt
from rich.rule import Rule
from rich.markup import escape

from engine.api.game_engine import GameEngine, ActionResult
from engine.api.game_session import GameSession
from engine.core.dm_agent import SceneType
from engine.map import TileType
from engine.world.viewport import Viewport

# ── Constants ────────────────────────────────────────────────────────
MAP_WIDTH = 40
MAP_HEIGHT = 20
FOV_RADIUS = 8
NARRATIVE_WIDTH = 30
MAX_NARRATIVES = 50
VISIBLE_NARRATIVES = 15

# ── Tile rendering ───────────────────────────────────────────────────
TILE_COLORS = {
    TileType.FLOOR:       (".", "grey50"),
    TileType.WALL:        ("#", "grey30"),
    TileType.DOOR:        ("+", "yellow"),
    TileType.CORRIDOR:    (".", "grey42"),
    TileType.STAIRS_DOWN: (">", "bright_cyan"),
    TileType.STAIRS_UP:   ("<", "bright_cyan"),
    TileType.WATER:       ("~", "blue"),
    TileType.TREE:        ("T", "green"),
    TileType.ROAD:        ("=", "yellow"),
    TileType.EMPTY:       (" ", "black"),
}

# ── Styles ───────────────────────────────────────────────────────────
STYLE_NARRATIVE = "white"
STYLE_COMBAT    = "bold red"
STYLE_NPC       = "cyan"
STYLE_SYSTEM    = "yellow"
STYLE_CMD       = "green"
STYLE_MUTED     = "dim"

console = Console(force_terminal=True)

# ── Direction keys ───────────────────────────────────────────────────
ARROW_COMMANDS = {
    readchar.key.UP:    "north",
    readchar.key.DOWN:  "south",
    readchar.key.LEFT:  "west",
    readchar.key.RIGHT: "east",
}

DIRECTION_DELTAS = {
    "north": (0, -1), "south": (0, 1),
    "east": (1, 0),   "west": (-1, 0),
}


# ── Map State (attached to session at runtime) ───────────────────────
class MapState:
    """Holds map, spatial index, viewport, and player entity for the top-down view."""

    def __init__(self, session: GameSession, map_type: str = "town"):
        self.session = session
        self.sync_from_session()

    def sync_from_session(self) -> None:
        self.map_data = self.session.map_data
        self.spatial_index = self.session.spatial_index
        self.player_entity = self.session.player_entity
        self.viewport = self.session.viewport or Viewport(width=MAP_WIDTH, height=MAP_HEIGHT)
        self.session.viewport = self.viewport
        if self.player_entity is not None:
            # Respect zoom-level dimensions instead of forcing defaults
            zoom_config = Viewport.ZOOM_LEVELS.get(self.viewport.zoom_level, Viewport.ZOOM_LEVELS[1])
            self.viewport.width = zoom_config["width"]
            self.viewport.height = zoom_config["height"]
            self.viewport.center_on(self.player_entity.position[0], self.player_entity.position[1])
            self._recompute_fov()

    def _recompute_fov(self) -> None:
        """Recompute field of view from player position."""
        px, py = self.player_entity.position

        def is_blocking(x: int, y: int) -> bool:
            tile = self.map_data.get_tile(x, y)
            return tile == TileType.WALL

        self.viewport.compute_fov(is_blocking, px, py, radius=FOV_RADIUS)

    def get_visible_entities(self) -> list:
        """Return all visible entities (excluding player) within FOV."""
        result = []
        for entity in self.spatial_index.all_entities():
            if entity.id == "player":
                continue
            ex, ey = entity.position
            if self.viewport.is_visible(ex, ey):
                result.append(entity)
        return result


# ── HP bar ───────────────────────────────────────────────────────────
def hp_style(current: int, maximum: int) -> str:
    ratio = current / max(maximum, 1)
    if ratio > 0.5:
        return "bold green"
    elif ratio > 0.25:
        return "bold yellow"
    return "bold red"


def hp_bar(current: int, maximum: int, width: int = 20) -> str:
    filled = int(width * current / max(maximum, 1))
    filled = min(filled, width)
    bar = "#" * filled + "-" * (width - filled)
    return f"[{bar}] {current}/{maximum}"


# ── Game time formatting ─────────────────────────────────────────────
def format_game_time(session: GameSession) -> str:
    gt = session.game_time
    if gt is None:
        return "??:??"
    period = gt.period.value.capitalize()
    return f"Day {gt.day} {gt.hour:02d}:{gt.minute:02d} ({period})"


# ── Render: Header ───────────────────────────────────────────────────
def render_header(session: GameSession) -> Panel:
    p = session.player
    snapshot = session.to_dict()
    player_ap = snapshot.get("player", {}).get("ap") or {
        "current": getattr(p, "ap", 4),
        "max": getattr(p, "max_ap", 4),
    }
    char_class = list(p.classes.keys())[0].capitalize() if p.classes else "Unknown"
    loc = session.dm_context.location

    style = hp_style(p.hp, p.max_hp)
    bar = hp_bar(p.hp, p.max_hp, width=16)

    # Equipment summary
    weapon = (session.equipment.get("weapon") or {}).get("name", "Fists") if getattr(session, "equipment", None) else "Fists"
    armor = (session.equipment.get("armor") or {}).get("name", "None") if getattr(session, "equipment", None) else "None"

    sp_text = f"SP: {p.spell_points}/{p.max_spell_points}" if p.max_spell_points > 0 else ""
    ap_text = f"AP: {player_ap.get('current', 0)}/{player_ap.get('max', 0)}"

    # Weight display
    weight_text = ""
    if getattr(session, "physical_inventory", None):
        pi = session.physical_inventory
        str_mod = session._get_strength_modifier()
        weight_text = f"  Wt: {pi.total_carried_weight():.1f}/{pi.max_carry_weight(str_mod):.1f} kg"

    line1 = (
        f"[bold bright_white]{p.name}[/bold bright_white]  "
        f"[bright_cyan]{char_class} Lv{p.level}[/bright_cyan]  "
        f"[{style}]{bar}[/{style}]"
    )
    line2 = (
        f"[dim]XP: {p.xp}[/dim]  "
        f"[bright_yellow]Gold: {p.gold}[/bright_yellow]  "
        f"[bright_magenta]{sp_text}[/bright_magenta]  "
        f"[dim]{ap_text}  AC: {p.ac}  Wpn: {weapon}  Arm: {armor}{weight_text}[/dim]  "
        f"[bright_yellow]{format_game_time(session)}[/bright_yellow]"
    )

    return Panel(f"{line1}\n{line2}", style="on dark_blue", padding=(0, 1), height=4)


# ── Render: Map viewport ────────────────────────────────────────────
def render_map(ms: MapState) -> Panel:
    """Render the map viewport as a Rich Panel with FOV and entities."""
    vp = ms.viewport
    text = Text()

    for sy in range(vp.height):
        for sx in range(vp.width):
            wx, wy = vp.screen_to_world(sx, sy)

            if vp.is_visible(wx, wy):
                # Check for player
                px, py = ms.player_entity.position
                if wx == px and wy == py:
                    text.append("@", style="bold bright_white")
                    continue

                # Check for entities
                entities = ms.spatial_index.at(wx, wy)
                entities = [e for e in entities if e.id != "player"]
                if entities:
                    e = entities[0]
                    text.append(e.glyph, style=f"bold {e.color}")
                    continue

                # Render tile
                tile = ms.map_data.get_tile(wx, wy)
                glyph, color = TILE_COLORS.get(tile, ("?", "white"))
                text.append(glyph, style=color)

            elif vp.is_explored(wx, wy):
                # Fog of war: dim rendering
                tile = ms.map_data.get_tile(wx, wy)
                glyph, _ = TILE_COLORS.get(tile, ("?", "white"))
                text.append(glyph, style="dim grey23")

            else:
                # Unexplored: dark
                text.append(" ")

        if sy < vp.height - 1:
            text.append("\n")

    # Add mini-legend at bottom
    legend = Text()
    legend.append("\n")
    legend.append("@ ", style="bold bright_white")
    legend.append("You  ", style="dim")
    legend.append("# ", style="grey30")
    legend.append("Wall  ", style="dim")
    legend.append(". ", style="grey50")
    legend.append("Floor  ", style="dim")
    legend.append("+ ", style="yellow")
    legend.append("Door  ", style="dim")
    legend.append("~ ", style="blue")
    legend.append("Water  ", style="dim")
    legend.append("T ", style="green")
    legend.append("Tree", style="dim")
    text.append_text(legend)

    border = "red" if ms.session.in_combat() else "bright_blue"
    return Panel(text, title="[bold bright_white]Map[/bold bright_white]", border_style=border)


# ── Render: Narrative panel ──────────────────────────────────────────
def render_narrative(history: list) -> Panel:
    """Render the narrative panel with the last N lines."""
    text = Text()
    visible = history[-VISIBLE_NARRATIVES:]
    for i, entry in enumerate(visible):
        line = entry.strip()
        if not line:
            continue
        # Color coding
        if line.startswith('"') or line.startswith('\u201c'):
            style = STYLE_NPC
        elif any(w in line.lower() for w in ["attack", "damage", "hit", "miss", "dead", "combat"]):
            style = STYLE_COMBAT
        elif line.startswith(">>>") or line.startswith("["):
            style = STYLE_SYSTEM
        else:
            style = STYLE_NARRATIVE

        text.append(line + "\n", style=style)

    return Panel(
        text,
        title="[bold bright_white]Narrative[/bold bright_white]",
        border_style="bright_blue",
    )


# ── Render: Nearby panel ────────────────────────────────────────────
def render_nearby(ms: MapState) -> Panel:
    """Render visible entities as a list."""
    text = Text()
    entities = ms.get_visible_entities()

    if not entities:
        text.append("No one nearby.", style="dim")
    else:
        for e in entities[:10]:
            text.append(f"{e.glyph} ", style=f"bold {e.color}")
            disp = f"({e.disposition})" if e.disposition != "neutral" else ""
            text.append(f"{e.name} ", style="bright_white")
            if disp:
                text.append(disp, style="dim")
            text.append("\n")

    return Panel(
        text,
        title="[bold bright_white]Nearby[/bold bright_white]",
        border_style="bright_blue",
    )


# ── Render: Command area ────────────────────────────────────────────
def render_commands() -> Panel:
    cmd_text = "[green]move/look/talk/attack/examine/rest/trade/inventory/cast/help/quit[/green]"
    return Panel(cmd_text, title="[bold]Commands[/bold]", border_style="bright_blue", height=3)


# ── Full layout ──────────────────────────────────────────────────────
def render_full(session: GameSession, ms: MapState, narrative_history: list) -> Layout:
    """Build the complete split-panel layout."""
    layout = Layout()

    layout.split_column(
        Layout(name="header", size=4),
        Layout(name="main"),
        Layout(name="footer", size=3),
    )

    layout["header"].update(render_header(session))
    layout["footer"].update(render_commands())

    layout["main"].split_row(
        Layout(name="map", ratio=2),
        Layout(name="sidebar", ratio=1),
    )

    layout["map"].update(render_map(ms))

    layout["sidebar"].split_column(
        Layout(name="narrative", ratio=3),
        Layout(name="nearby", ratio=1),
    )

    layout["narrative"].update(render_narrative(narrative_history))
    layout["nearby"].update(render_nearby(ms))

    return layout


# ── Input ────────────────────────────────────────────────────────────
def read_input() -> str:
    """Read input with arrow key support for instant movement."""
    sys.stdout.write("\033[32m> \033[0m")
    sys.stdout.flush()

    buf = []
    while True:
        key = readchar.readkey()

        # Arrow keys -> instant direction
        if key in ARROW_COMMANDS:
            sys.stdout.write("\r\033[K")
            direction = ARROW_COMMANDS[key]
            sys.stdout.write(f"\033[32m> \033[0mmove {direction}\n")
            sys.stdout.flush()
            return f"__arrow__{direction}"

        # Zoom keys: +/- or =/_ to cycle zoom
        if key in ("+", "="):
            return "__zoom_in__"
        if key in ("-", "_"):
            return "__zoom_out__"

        # Enter
        if key in ("\r", "\n", readchar.key.ENTER):
            sys.stdout.write("\n")
            sys.stdout.flush()
            return "".join(buf)

        # Backspace
        if key in ("\x7f", "\x08", readchar.key.BACKSPACE):
            if buf:
                buf.pop()
                sys.stdout.write("\b \b")
                sys.stdout.flush()
            continue

        # Ctrl+C
        if key == readchar.key.CTRL_C:
            raise KeyboardInterrupt

        # Ctrl+D
        if key == "\x04":
            raise EOFError

        # Skip multi-byte special keys
        if len(key) > 1:
            continue

        # Printable character
        if key.isprintable():
            buf.append(key)
            sys.stdout.write(key)
            sys.stdout.flush()


# ── Character creation ───────────────────────────────────────────────
def character_creation() -> tuple:
    """Interactive character creation. Returns (name, class, map_type)."""
    console.print()
    console.print(Rule("[bold bright_yellow]EMBER RPG[/bold bright_yellow]", style="bright_yellow"))
    console.print()
    console.print(Panel(
        "[bold bright_yellow]"
        "  _____ __  __ ____  _____ ____      ____  ____   ____ \n"
        " | ____|  \\/  | __ )| ____|  _ \\    |  _ \\|  _ \\ / ___|\n"
        " |  _| | |\\/| |  _ \\|  _| | |_) |   | |_) | |_) | |  _ \n"
        " | |___| |  | | |_) | |___|  _ <    |  _ <|  __/| |_| |\n"
        " |_____|_|  |_|____/|_____|_| \\_\\   |_| \\_\\_|    \\____|"
        "[/bold bright_yellow]",
        subtitle="[dim]Top-Down Explorer[/dim]",
        border_style="bright_yellow",
    ))
    console.print()
    console.print(Panel(
        "[bright_white]Welcome, traveler. A world of danger and wonder awaits.\n"
        "Choose your path wisely...[/bright_white]",
        border_style="bright_yellow",
        title="[bold]Character Creation[/bold]",
    ))
    console.print()

    # Name
    name = Prompt.ask("[bold green]What is your name, adventurer?[/bold green]").strip()
    if not name:
        name = "Stranger"

    # Class selection
    console.print()
    classes_table = Table(title="Choose Your Class", show_header=True, expand=True)
    classes_table.add_column("#", style="bold", justify="center", width=3)
    classes_table.add_column("Class", style="bold bright_cyan")
    classes_table.add_column("HP", justify="center", style="green")
    classes_table.add_column("SP", justify="center", style="magenta")
    classes_table.add_column("Starting Gear", style="bright_white")

    class_info = [
        ("1", "Warrior", "20", "0",  "Iron Sword, Chain Mail, Wooden Shield"),
        ("2", "Rogue",   "16", "0",  "Twin Daggers, Leather Armor, Lockpick Set"),
        ("3", "Mage",    "12", "16", "Oak Staff, Cloth Robes, Spellbook"),
        ("4", "Priest",  "16", "12", "Iron Mace, Chain Mail, Holy Symbol"),
    ]
    for row in class_info:
        classes_table.add_row(*row)
    console.print(classes_table)
    console.print()

    class_map = {"1": "warrior", "2": "rogue", "3": "mage", "4": "priest"}
    choice = Prompt.ask(
        "[bold green]Select class[/bold green]",
        choices=["1", "2", "3", "4"],
        default="1",
    )
    char_class = class_map[choice]

    # Map type
    console.print()
    console.print("[bold green]Where do you begin?[/bold green]")
    console.print("  [bright_cyan]1[/bright_cyan] Town (streets, buildings, merchants)")
    console.print("  [bright_cyan]2[/bright_cyan] Dungeon (corridors, rooms, danger)")
    console.print("  [bright_cyan]3[/bright_cyan] Wilderness (forests, roads, water)")
    map_choice = Prompt.ask("[bold green]Select starting area[/bold green]",
                            choices=["1", "2", "3"], default="1")
    map_types = {"1": "town", "2": "dungeon", "3": "wilderness"}
    map_type = map_types[map_choice]

    console.print()
    console.print(f"[bold bright_yellow]{name} the {char_class.capitalize()} "
                  f"steps into the {map_type}...[/bold bright_yellow]")
    time.sleep(0.5)

    return name, char_class, map_type


# ── Help ─────────────────────────────────────────────────────────────
def show_help(narrative_history: list) -> None:
    """Append help text to narrative."""
    help_lines = [
        "--- COMMANDS ---",
        "Arrow keys: Move instantly",
        "move <dir>: Move north/south/east/west",
        "look around: Observe surroundings",
        "talk <npc>: Talk to an NPC",
        "attack <target>: Attack a creature",
        "examine <object>: Examine closely",
        "rest: Rest and recover HP",
        "trade with <npc>: Open trade",
        "inventory: Check your items",
        "cast <spell>: Cast a spell",
        "help: Show this help",
        "quit: Exit the game",
    ]
    for line in help_lines:
        narrative_history.append(line)


# ── Game loop ────────────────────────────────────────────────────────
def game_loop(engine: GameEngine, session: GameSession, ms: MapState,
              opening_narrative: str) -> None:
    """Main game loop with Rich layout rendering."""
    narrative_history = []

    # Split opening narrative into lines
    for line in opening_narrative.strip().split("\n"):
        line = line.strip()
        if line:
            narrative_history.append(line)

    narrative_history.append("Type 'help' for commands. Use arrow keys to move.")

    while True:
        # Clear and render
        console.clear()
        layout = render_full(session, ms, narrative_history)
        console.print(layout)

        # Get input
        try:
            cmd = read_input()
        except (KeyboardInterrupt, EOFError):
            narrative_history.append("Farewell, adventurer. Until next time.")
            console.clear()
            console.print(render_full(session, ms, narrative_history))
            break

        cmd = cmd.strip()
        if not cmd:
            continue

        # Arrow key movement
        if cmd.startswith("__arrow__"):
            direction = cmd.replace("__arrow__", "")
            try:
                result = engine.process_action(session, f"move {direction}")
                if result.narrative:
                    for line in result.narrative.strip().split("\n"):
                        line = line.strip()
                        if line:
                            narrative_history.append(line)
                _process_result_extras(result, narrative_history)
                ms.sync_from_session()
            except Exception as e:
                narrative_history.append(f"Engine error: {e}")
            # Trim
            narrative_history = narrative_history[-MAX_NARRATIVES:]
            continue

        # Zoom commands
        if cmd in ("__zoom_in__", "__zoom_out__"):
            if session.viewport:
                direction = 1 if cmd == "__zoom_in__" else -1
                new_level = session.viewport.cycle_zoom(direction)
                narrative_history.append(f"[Zoom level {new_level}]")
                ms.sync_from_session()
            narrative_history = narrative_history[-MAX_NARRATIVES:]
            continue

        # Local commands
        if cmd.lower() in ("quit", "exit", "q"):
            narrative_history.append("Farewell, adventurer. Until next time.")
            console.clear()
            console.print(render_full(session, ms, narrative_history))
            break

        if cmd.lower() in ("help", "?", "h"):
            show_help(narrative_history)
            continue

        # Handle cardinal move commands with map collision
        lower = cmd.lower()
        move_prefix = None
        for direction in DIRECTION_DELTAS:
            if lower == f"move {direction}" or lower == direction:
                move_prefix = direction
                break

        if move_prefix:
            try:
                result = engine.process_action(session, f"move {move_prefix}")
                if result.narrative:
                    for line in result.narrative.strip().split("\n"):
                        line = line.strip()
                        if line:
                            narrative_history.append(line)
                _process_result_extras(result, narrative_history)
                ms.sync_from_session()
            except Exception as e:
                narrative_history.append(f"Engine error: {e}")
            narrative_history = narrative_history[-MAX_NARRATIVES:]
            continue

        # All other commands go through the engine
        try:
            result = engine.process_action(session, cmd)
        except Exception as e:
            narrative_history.append(f"Engine error: {e}")
            continue

        # Append narrative
        if result.narrative:
            for line in result.narrative.strip().split("\n"):
                line = line.strip()
                if line:
                    narrative_history.append(line)

        _process_result_extras(result, narrative_history)
        ms.sync_from_session()

        # Trim history
        narrative_history = narrative_history[-MAX_NARRATIVES:]


def _process_result_extras(result: ActionResult, narrative_history: list) -> None:
    """Process combat state, state changes, loot, level up from ActionResult."""
    # State changes
    changes = result.state_changes or {}
    parts = []
    if "hp_change" in changes:
        delta = changes["hp_change"]
        sign = "+" if delta > 0 else ""
        parts.append(f"HP {sign}{delta}")
    if "xp_gained" in changes:
        parts.append(f"+{changes['xp_gained']} XP")
    if "gold_change" in changes:
        parts.append(f"+{changes['gold_change']} gold")
    if "damage_dealt" in changes:
        parts.append(f"Damage: {changes['damage_dealt']}")
    if parts:
        narrative_history.append(f">>> {' | '.join(parts)}")

    # Loot
    if result.loot_dropped:
        for item in result.loot_dropped:
            name = item.get("name", str(item)) if isinstance(item, dict) else str(item)
            narrative_history.append(f">>> Loot: {name}")

    # Level up
    if result.level_up is not None:
        lu = result.level_up
        if isinstance(lu, dict):
            new_level = lu.get("new_level", "?")
            hp_gain = lu.get("hp_gained", 0)
        else:
            new_level = getattr(lu, "new_level", "?")
            hp_gain = getattr(lu, "hp_gained", 0)
        narrative_history.append(f"*** LEVEL UP! Now level {new_level}! +{hp_gain} HP ***")

    # Combat state
    if result.combat_state and not result.combat_state.get("ended", True):
        cs = result.combat_state
        rnd = cs.get("round", 0)
        active = cs.get("active", "?")
        narrative_history.append(f"[Combat Round {rnd} | Turn: {active}]")


# ── Main ─────────────────────────────────────────────────────────────
def main():
    console.clear()

    try:
        name, char_class, map_type = character_creation()
    except (KeyboardInterrupt, EOFError):
        console.print(f"\n[{STYLE_SYSTEM}]Cancelled.[/{STYLE_SYSTEM}]")
        return

    location_by_map = {
        "town": "Harbor Town",
        "dungeon": "Ancient Dungeon",
        "wilderness": "Forest Road",
    }

    # Create engine and session
    engine = GameEngine()
    session = engine.new_session(
        player_name=name,
        player_class=char_class,
        location=location_by_map.get(map_type),
    )

    # Create map state (generates map, places entities, sets up viewport)
    ms = MapState(session, map_type=map_type)

    # Build opening narrative
    loc = session.dm_context.location
    opening_event = session.dm_context.history[-1] if session.dm_context.history else None
    opening = getattr(opening_event, "description", opening_event) if opening_event else (
        f"You arrive at {loc}. The air is thick with possibility."
    )

    game_loop(engine, session, ms, opening)


if __name__ == "__main__":
    main()
