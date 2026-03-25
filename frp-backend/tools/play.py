#!/usr/bin/env python3
"""
Ember RPG - Rich Terminal Client
A playable terminal client using the rich library.
Run: python -m tools.play   (from frp-backend/)
"""
import sys
import os

# Force UTF-8 output on Windows to avoid cp1254 encoding errors
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

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.prompt import Prompt, IntPrompt
from rich.columns import Columns
from rich.rule import Rule
from rich.style import Style
from rich.markup import escape
import readchar
import time

from engine.api.game_engine import GameEngine, ActionResult
from engine.api.game_session import GameSession
from engine.core.dm_agent import SceneType

# ── Styles ──────────────────────────────────────────────────────────
STYLE_NARRATIVE = "white"
STYLE_COMBAT    = "bold red"
STYLE_NPC       = "cyan"
STYLE_SYSTEM    = "yellow"
STYLE_CMD       = "green"
STYLE_HEADER    = "bold bright_white on dark_blue"
STYLE_HP_OK     = "bold green"
STYLE_HP_LOW    = "bold yellow"
STYLE_HP_CRIT   = "bold red"
STYLE_MUTED     = "dim"

console = Console(force_terminal=True)

# ── Direction keys ──────────────────────────────────────────────────
ARROW_COMMANDS = {
    readchar.key.UP:    "move north",
    readchar.key.DOWN:  "move south",
    readchar.key.LEFT:  "move west",
    readchar.key.RIGHT: "move east",
}


def hp_style(current: int, maximum: int) -> str:
    ratio = current / max(maximum, 1)
    if ratio > 0.5:
        return STYLE_HP_OK
    elif ratio > 0.25:
        return STYLE_HP_LOW
    return STYLE_HP_CRIT


def hp_bar(current: int, maximum: int, width: int = 20) -> Text:
    filled = int(width * current / max(maximum, 1))
    filled = min(filled, width)
    bar_text = "#" * filled + "-" * (width - filled)
    style = hp_style(current, maximum)
    txt = Text()
    txt.append(f"[{bar_text}]", style=style)
    txt.append(f" {current}/{maximum}", style=style)
    return txt


def format_game_time(session: GameSession) -> str:
    gt = session.game_time
    if gt is None:
        return "??:??"
    period = gt.period.value.capitalize()
    return f"Day {gt.day} {gt.hour:02d}:{gt.minute:02d} ({period})"


def render_header(session: GameSession) -> Panel:
    p = session.player
    char_class = list(p.classes.keys())[0].capitalize() if p.classes else "Unknown"
    loc = session.dm_context.location

    tbl = Table.grid(expand=True)
    tbl.add_column(ratio=2)
    tbl.add_column(ratio=2)
    tbl.add_column(ratio=2)
    tbl.add_column(ratio=2)

    hp_txt = hp_bar(p.hp, p.max_hp, width=15)

    tbl.add_row(
        Text(f" {p.name}", style="bold bright_white"),
        Text(f"Class: {char_class} Lv{p.level}", style="bright_cyan"),
        hp_txt,
        Text(f"{loc}  {format_game_time(session)}", style="bright_yellow"),
    )

    # Second row: XP, SP, Gold
    sp_text = f"SP: {p.spell_points}/{p.max_spell_points}" if p.max_spell_points > 0 else ""
    tbl.add_row(
        Text(f" XP: {p.xp}", style=STYLE_MUTED),
        Text(f"Gold: {p.gold}", style="bright_yellow"),
        Text(sp_text, style="bright_magenta"),
        Text(f"AC: {p.ac}  Pos: {session.position}", style=STYLE_MUTED),
    )

    return Panel(tbl, style="on dark_blue", padding=(0, 1))


def render_combat(combat_state: dict) -> Panel:
    """Render combat status panel."""
    tbl = Table(title="COMBAT", style=STYLE_COMBAT, expand=True, show_lines=True)
    tbl.add_column("Combatant", style="bold")
    tbl.add_column("HP", justify="center")
    tbl.add_column("Status", justify="center")

    combatants = combat_state.get("combatants", [])
    for c in combatants:
        name = c.get("name", "???")
        chp = c.get("hp", 0)
        cmhp = c.get("max_hp", 1)
        dead = c.get("dead", False)
        bar = hp_bar(chp, cmhp, width=12)
        status = Text("DEAD", style="bold red") if dead else Text("Active", style="green")
        tbl.add_row(name, bar, status)

    active = combat_state.get("active")
    rnd = combat_state.get("round", 0)
    subtitle = f"Round {rnd}"
    if active:
        subtitle += f" | Turn: {active}"

    return Panel(tbl, title="[bold red]Combat[/bold red]", subtitle=subtitle,
                 border_style="red")


def render_narrative(text: str, scene_type: SceneType = SceneType.EXPLORATION,
                     combat_state: dict = None) -> None:
    """Print narrative text with appropriate coloring."""
    lines = text.strip().split("\n")
    for line in lines:
        line = line.strip()
        if not line:
            console.print()
            continue
        # Detect NPC speech (quoted text)
        if line.startswith('"') or line.startswith('\u201c'):
            console.print(f"  {line}", style=STYLE_NPC)
        elif scene_type == SceneType.COMBAT or (combat_state and not combat_state.get("ended", True)):
            console.print(f"  {line}", style=STYLE_COMBAT)
        else:
            console.print(f"  {line}", style=STYLE_NARRATIVE)


def render_state_changes(changes: dict) -> None:
    """Show state changes in yellow."""
    if not changes:
        return
    parts = []
    if "hp_change" in changes:
        delta = changes["hp_change"]
        sign = "+" if delta > 0 else ""
        parts.append(f"HP {sign}{delta}")
    if "xp_gained" in changes:
        parts.append(f"+{changes['xp_gained']} XP")
    if "gold_change" in changes:
        parts.append(f"+{changes['gold_change']} gold")
    if "hit_location" in changes:
        parts.append(f"Hit: {changes['hit_location']}")
    if "armor_reduction" in changes:
        parts.append(f"Armor absorbed: {changes['armor_reduction']}")
    if "damage_dealt" in changes:
        parts.append(f"Damage: {changes['damage_dealt']}")
    if parts:
        console.print(f"  [{STYLE_SYSTEM}]>>> {' | '.join(parts)}[/{STYLE_SYSTEM}]")


def render_level_up(level_up) -> None:
    if level_up is None:
        return
    if isinstance(level_up, dict):
        new_level = level_up.get("new_level", "?")
        hp_gain = level_up.get("hp_gained", 0)
    else:
        new_level = getattr(level_up, "new_level", "?")
        hp_gain = getattr(level_up, "hp_gained", 0)
    console.print()
    console.print(Panel(
        f"[bold bright_yellow]LEVEL UP! You are now level {new_level}![/bold bright_yellow]\n"
        f"[green]+{hp_gain} HP[/green]",
        border_style="bright_yellow",
        title="[bold]LEVEL UP[/bold]",
    ))


def show_help() -> None:
    """Display help panel."""
    help_text = Table(title="Commands", show_header=False, expand=True,
                      style="bright_white", padding=(0, 2))
    help_text.add_column("Command", style=STYLE_CMD, ratio=1)
    help_text.add_column("Description", ratio=2)

    commands = [
        ("look around", "Observe your surroundings"),
        ("move north/south/east/west", "Move in a direction (or use arrow keys)"),
        ("talk <npc>", "Talk to an NPC"),
        ("attack <target>", "Attack a creature"),
        ("examine <object>", "Examine something closely"),
        ("rest", "Rest and recover"),
        ("trade with <npc>", "Open trade with an NPC"),
        ("inventory", "Check your inventory"),
        ("cast <spell>", "Cast a spell"),
        ("open <object>", "Open a door, chest, etc."),
        ("help", "Show this help"),
        ("quit / exit", "Exit the game"),
        ("Arrow keys", "Quick movement (Up/Down/Left/Right)"),
    ]
    for cmd, desc in commands:
        help_text.add_row(cmd, desc)

    console.print(Panel(help_text, border_style="bright_blue"))


def character_creation() -> tuple:
    """Interactive character creation. Returns (name, class)."""
    console.print()
    console.print(Rule("[bold bright_yellow]EMBER RPG[/bold bright_yellow]", style="bright_yellow"))
    console.print()
    console.print(Panel(
        "[bright_white]Welcome, traveler. A world of danger and wonder awaits.\n"
        "Before you step through the gate, tell me about yourself...[/bright_white]",
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
    classes_table.add_column("Strengths", style="bright_white")

    class_info = [
        ("1", "Warrior", "20", "0", "MIG 16, END 14 -- Tank & melee damage"),
        ("2", "Rogue", "16", "0", "AGI 16, INS 14 -- Stealth & precision"),
        ("3", "Mage", "12", "16", "MND 16, INS 14 -- Arcane power"),
        ("4", "Priest", "16", "12", "INS 16, MND 14 -- Healing & divine magic"),
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

    console.print()
    console.print(f"[bold bright_yellow]{name} the {char_class.capitalize()} steps into the world...[/bold bright_yellow]")
    console.print()
    time.sleep(0.5)

    return name, char_class


def read_input() -> str:
    """Read a line of input, supporting arrow keys for quick movement.

    Uses readchar.readkey() which returns full key sequences on all platforms.
    """
    console.print()
    sys.stdout.write("\033[32m> \033[0m")
    sys.stdout.flush()

    buf = []
    while True:
        key = readchar.readkey()

        # Arrow keys -> instant direction command
        if key in ARROW_COMMANDS:
            sys.stdout.write('\r\033[K')
            cmd = ARROW_COMMANDS[key]
            sys.stdout.write(f"\033[32m> \033[0m{cmd}\n")
            sys.stdout.flush()
            return cmd

        # Enter
        if key in ('\r', '\n', readchar.key.ENTER):
            sys.stdout.write('\n')
            sys.stdout.flush()
            return ''.join(buf)

        # Backspace
        if key in ('\x7f', '\x08', readchar.key.BACKSPACE):
            if buf:
                buf.pop()
                sys.stdout.write('\b \b')
                sys.stdout.flush()
            continue

        # Ctrl+C
        if key == readchar.key.CTRL_C:
            raise KeyboardInterrupt

        # Ctrl+D (EOF)
        if key == '\x04':
            raise EOFError

        # Skip other special keys (multi-byte sequences we don't handle)
        if len(key) > 1:
            continue

        # Regular printable character
        if key.isprintable():
            buf.append(key)
            sys.stdout.write(key)
            sys.stdout.flush()


def game_loop(engine: GameEngine, session: GameSession, opening_narrative: str) -> None:
    """Main game loop."""
    # Show opening
    console.print(render_header(session))
    console.print()
    render_narrative(opening_narrative)
    console.print()

    show_help()

    while True:
        # Render header
        console.print(render_header(session))

        try:
            cmd = read_input()
        except (KeyboardInterrupt, EOFError):
            console.print(f"\n[{STYLE_SYSTEM}]Farewell, adventurer. Until next time.[/{STYLE_SYSTEM}]")
            break

        cmd = cmd.strip()
        if not cmd:
            continue

        # Local commands
        if cmd.lower() in ("quit", "exit", "q"):
            console.print(f"[{STYLE_SYSTEM}]Farewell, adventurer. Until next time.[/{STYLE_SYSTEM}]")
            break
        if cmd.lower() in ("help", "?", "h"):
            show_help()
            continue
        if cmd.lower() == "clear":
            console.clear()
            continue

        # Echo the command
        console.print(f"  [{STYLE_CMD}]> {escape(cmd)}[/{STYLE_CMD}]")

        # Process through engine
        try:
            result: ActionResult = engine.process_action(session, cmd)
        except Exception as e:
            console.print(f"  [{STYLE_SYSTEM}]Engine error: {e}[/{STYLE_SYSTEM}]")
            continue

        console.print()

        # Render narrative
        render_narrative(result.narrative, result.scene_type, result.combat_state)

        # Combat panel
        if result.combat_state and not result.combat_state.get("ended", True):
            console.print()
            console.print(render_combat(result.combat_state))

        # State changes
        render_state_changes(result.state_changes)

        # Loot
        if result.loot_dropped:
            for item in result.loot_dropped:
                if isinstance(item, dict):
                    console.print(f"  [{STYLE_SYSTEM}]Loot: {item.get('name', item)}[/{STYLE_SYSTEM}]")
                else:
                    console.print(f"  [{STYLE_SYSTEM}]Loot: {item}[/{STYLE_SYSTEM}]")

        # Level up
        render_level_up(result.level_up)

        console.print()


def main():
    """Entry point."""
    console.clear()
    console.print(Panel(
        "[bold bright_yellow]"
        "  _____ __  __ ____  _____ ____      ____  ____   ____ \n"
        " | ____|  \\/  | __ )| ____|  _ \\    |  _ \\|  _ \\ / ___|\n"
        " |  _| | |\\/| |  _ \\|  _| | |_) |   | |_) | |_) | |  _ \n"
        " | |___| |  | | |_) | |___|  _ <    |  _ <|  __/| |_| |\n"
        " |_____|_|  |_|____/|_____|_| \\_\\   |_| \\_\\_|    \\____|"
        "[/bold bright_yellow]",
        subtitle="[dim]A Living World Adventure[/dim]",
        border_style="bright_yellow",
    ))

    try:
        name, char_class = character_creation()
    except (KeyboardInterrupt, EOFError):
        console.print(f"\n[{STYLE_SYSTEM}]Cancelled.[/{STYLE_SYSTEM}]")
        return

    # Create engine and session
    engine = GameEngine()
    session = engine.new_session(player_name=name, player_class=char_class)

    # Build opening narrative
    loc = session.dm_context.location
    opening = session.dm_context.history[-1] if session.dm_context.history else (
        f"You arrive at {loc}. The air is thick with possibility."
    )

    game_loop(engine, session, opening)


if __name__ == "__main__":
    main()
