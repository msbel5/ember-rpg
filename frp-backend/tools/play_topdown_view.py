"""Rendering helpers for the top-down terminal client."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from rich.layout import Layout
from rich.panel import Panel
from rich.text import Text

from engine.core.character_creation import ABILITY_ORDER, assign_stats_to_class
from engine.map import TileType

MAP_WIDTH = 40
MAP_HEIGHT = 20
VISIBLE_NARRATIVES = 14

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

ABILITY_LABELS = {
    "MIG": "Might",
    "END": "Endurance",
    "AGI": "Agility",
    "MND": "Mind",
    "INS": "Insight",
    "PRE": "Presence",
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
    """Compatibility wrapper that accepts either a legacy session or a campaign snapshot."""

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


def build_character_sheet(snapshot: dict[str, Any]) -> dict[str, Any]:
    sheet = dict(snapshot.get("character_sheet") or {})
    if sheet:
        return sheet

    campaign = dict(snapshot.get("campaign") or snapshot)
    player = dict(campaign.get("player") or snapshot.get("player") or {})
    stats = dict(player.get("stats") or {})
    if not stats:
        stats = assign_stats_to_class(
            list(campaign.get("creation_state", {}).get("current_roll") or []),
            str(player.get("player_class", "warrior")),
        )

    abilities = []
    for ability in ABILITY_ORDER:
        value = int(stats.get(ability, 10))
        abilities.append(
            {
                "ability": ability,
                "label": ABILITY_LABELS.get(ability, ability),
                "value": value,
                "modifier": (value - 10) // 2,
            }
        )

    ap_state = player.get("ap") if isinstance(player.get("ap"), dict) else {}
    current_ap = int(ap_state.get("current", player.get("action_points", 0)))
    max_ap = int(ap_state.get("max", player.get("max_action_points", max(current_ap, 1))))

    return {
        "name": str(player.get("name", "Adventurer")),
        "class": str(player.get("player_class", "warrior")),
        "alignment": str(player.get("alignment", campaign.get("creation_state", {}).get("recommended_alignment", "NN"))),
        "skills": list(player.get("skill_proficiencies") or campaign.get("creation_state", {}).get("recommended_skills") or []),
        "stats": abilities,
        "hp": {
            "current": int(player.get("hp", 0)),
            "max": int(player.get("max_hp", 1)),
        },
        "ap": {
            "current": current_ap,
            "max": max_ap,
        },
        "adapter_id": str(snapshot.get("adapter_id", campaign.get("adapter_id", "fantasy_ember"))),
        "profile_id": str(snapshot.get("profile_id", campaign.get("profile_id", "standard"))),
        "creation_summary": dict(campaign.get("creation_state") or snapshot.get("creation_state") or {}),
    }


def render_character_sheet(snapshot: dict[str, Any]) -> Panel:
    sheet = build_character_sheet(snapshot)
    text = Text()
    text.append("%s | %s | %s\n\n" % (sheet["name"], sheet["class"].capitalize(), sheet["alignment"]))
    text.append("Stats\n", style="bold")
    for stat in sheet["stats"]:
        text.append("- %s: %d (%+d)\n" % (stat["ability"], int(stat["value"]), int(stat["modifier"])))
    text.append("\nSkills\n", style="bold")
    skills = sheet.get("skills") or []
    if skills:
        for skill in skills:
            text.append("- %s\n" % skill)
    else:
        text.append("- None\n", style="dim")
    text.append("\nResources\n", style="bold")
    text.append(
        "HP %d/%d  SP %d/%d  AP %d/%d" % (
            int(sheet["hp"]["current"]),
            int(sheet["hp"]["max"]),
            int(sheet.get("sp", {}).get("current", 0)),
            int(sheet.get("sp", {}).get("max", 0)),
            int(sheet["ap"]["current"]),
            int(sheet["ap"]["max"]),
        )
    )
    creation_summary = dict(sheet.get("creation_summary") or {})
    if creation_summary:
        text.append("\n\nCreation\n", style="bold")
        text.append(
            "Recommended: %s / %s\n"
            % (
                str(creation_summary.get("recommended_class", sheet["class"])).capitalize(),
                str(creation_summary.get("recommended_alignment", sheet["alignment"])),
            )
        )
        text.append("Current roll: %s\n" % _roll_text(creation_summary.get("current_roll", [])))
        text.append("Saved roll: %s" % _roll_text(creation_summary.get("saved_roll", [])))
    return Panel(text, title="[bold bright_white]Character[/bold bright_white]", border_style="bright_blue")


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
    layout["sidebar"].split_column(
        Layout(name="narrative", ratio=3),
        Layout(name="character", ratio=2),
        Layout(name="settlement", ratio=2),
    )
    layout["narrative"].update(render_narrative(screen_state.narrative_history))
    layout["character"].update(render_character_sheet(screen_state.snapshot))
    layout["settlement"].update(render_settlement(screen_state.campaign))
    return layout


def _tile_style(tile: Any) -> tuple[str, str]:
    if tile in LEGACY_TILE_GLYPHS:
        return LEGACY_TILE_GLYPHS[tile]
    return TERRAIN_GLYPHS.get(str(tile).lower(), ("?", "white"))


def _roll_text(values: Any) -> str:
    if values is None:
        return "-"
    if not isinstance(values, list):
        values = list(values)
    if not values:
        return "-"
    return ", ".join(str(value) for value in values)

