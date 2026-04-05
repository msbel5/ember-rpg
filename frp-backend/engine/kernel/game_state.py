from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

from engine.kernel.actor import ActorRecord
from engine.kernel.area import AreaState
from engine.kernel.common import serialize_value


@dataclass
class JournalEntry:
    entry_id: str
    text: str
    quest_id: str = ""
    quest_stage: int = 0
    timestamp: int = 0
    entry_type: str = "info"

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "JournalEntry":
        return cls(**data)


@dataclass
class WorldTime:
    game_tick: int = 0
    hour: int = 12
    day: int = 1
    weather: str = "clear"
    ticks_per_hour: int = 100

    def advance(self, ticks: int) -> list[dict]:
        events: list[dict] = []
        ticks = max(0, int(ticks))
        start_hour = self.hour
        start_day = self.day
        self.game_tick += ticks
        elapsed_hours = self.game_tick // max(1, self.ticks_per_hour)
        self.hour = (12 + elapsed_hours) % 24
        self.day = 1 + ((12 + elapsed_hours) // 24)
        if self.hour != start_hour:
            events.append({"type": "hour_changed", "hour": self.hour})
        if self.day != start_day:
            events.append({"type": "day_changed", "day": self.day})
        return events

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorldTime":
        return cls(**data)


@dataclass
class DifficultySettings:
    level: str = "normal"
    enemy_damage_mult: float = 1.0
    party_damage_mult: float = 1.0
    enemy_hp_mult: float = 1.0

    @classmethod
    def from_level(cls, level: str) -> "DifficultySettings":
        presets = {
            "easy": cls(level="easy", enemy_damage_mult=0.5, party_damage_mult=2.0, enemy_hp_mult=0.75),
            "normal": cls(level="normal"),
            "core": cls(level="core"),
            "hard": cls(level="hard", enemy_damage_mult=1.5, party_damage_mult=0.75, enemy_hp_mult=1.5),
            "insane": cls(level="insane", enemy_damage_mult=2.0, party_damage_mult=0.5, enemy_hp_mult=2.0),
        }
        return presets.get(str(level).lower(), cls())

    def to_dict(self) -> dict[str, Any]:
        return serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DifficultySettings":
        return cls(**data)


FORMATIONS = {
    "line": [(0, 0), (0, 1), (0, 2), (0, 3), (0, 4), (0, 5)],
    "wedge": [(0, 0), (-1, 1), (1, 1), (-2, 2), (2, 2), (0, 2)],
    "circle": [(0, 0), (1, 0), (0, 1), (-1, 0), (0, -1), (1, 1)],
    "scatter": [(0, 0), (2, 1), (-2, 1), (1, -2), (-1, 2), (3, 0)],
}
PARTY_TACTIC_MODES = {"balanced", "aggressive", "guard"}

PARTY_TACTIC_MODES = {"balanced", "aggressive", "guard"}


def _normalized_formation_name(formation: str) -> str:
    normalized = str(formation or "wedge").lower().strip()
    return normalized if normalized in FORMATIONS else "wedge"


def _normalized_party_ids(party_ids: list[str]) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    for actor_id in [str(item) for item in list(party_ids or []) if str(item)]:
        if actor_id in seen:
            continue
        seen.add(actor_id)
        normalized.append(actor_id)
    if "player" in normalized:
        normalized.remove("player")
        normalized.insert(0, "player")
    return normalized


def _normalized_inactive_npc_ids(inactive_ids: list[str], party_ids: list[str]) -> list[str]:
    party = set(_normalized_party_ids(party_ids))
    seen: set[str] = set()
    normalized: list[str] = []
    for actor_id in [str(item) for item in list(inactive_ids or []) if str(item)]:
        if actor_id == "player" or actor_id in party or actor_id in seen:
            continue
        seen.add(actor_id)
        normalized.append(actor_id)
    return normalized


def _normalized_party_tactic_mode(mode: str) -> str:
    normalized = str(mode or "balanced").lower().strip()
    return normalized if normalized in PARTY_TACTIC_MODES else "balanced"


def _is_valid_party_tactic_mode(mode: str) -> bool:
    return str(mode or "").lower().strip() in PARTY_TACTIC_MODES


def _normalized_party_tactics(
    tactics: dict[str, str],
    *,
    known_actor_ids: set[str],
) -> dict[str, str]:
    normalized: dict[str, str] = {}
    seen: set[str] = set()
    for actor_id, mode in dict(tactics or {}).items():
        normalized_actor_id = str(actor_id).strip()
        if not normalized_actor_id or normalized_actor_id == "player":
            continue
        if normalized_actor_id not in known_actor_ids or normalized_actor_id in seen:
            continue
        raw_mode = str(mode or "").lower().strip()
        if raw_mode not in PARTY_TACTIC_MODES:
            continue
        normalized_mode = raw_mode
        normalized[normalized_actor_id] = normalized_mode
        seen.add(normalized_actor_id)
    return normalized


def normalize_party_state(state: "GameState") -> "GameState":
    state.party = _normalized_party_ids(state.party)
    state.inactive_npcs = _normalized_inactive_npc_ids(state.inactive_npcs, state.party)
    state.formation = _normalized_formation_name(getattr(state, "formation", "wedge"))
    known_actor_ids = {str(actor_id) for actor_id in getattr(state, "actors", {}).keys() if str(actor_id)}
    known_actor_ids.update(state.party)
    known_actor_ids.update(state.inactive_npcs)
    if hasattr(state, "party_tactics"):
        state.party_tactics = _normalized_party_tactics(
            getattr(state, "party_tactics", {}),
            known_actor_ids=known_actor_ids,
        )
    return state


@dataclass
class GameState:
    campaign_id: str
    seed: int
    party: list[str] = field(default_factory=list)
    inactive_npcs: list[str] = field(default_factory=list)
    party_tactics: dict[str, str] = field(default_factory=dict)
    current_area_id: str = ""
    loaded_area_ids: list[str] = field(default_factory=list)
    loaded_areas: dict[str, AreaState] = field(default_factory=dict)
    actors: dict[str, ActorRecord] = field(default_factory=dict)
    global_variables: dict[str, Any] = field(default_factory=dict)
    local_variables: dict[str, dict[str, Any]] = field(default_factory=dict)
    journal: list[JournalEntry] = field(default_factory=list)
    world_time: WorldTime = field(default_factory=WorldTime)
    reputation: int = 10
    difficulty: DifficultySettings = field(default_factory=DifficultySettings)
    formation: str = "wedge"
    play_time_ticks: int = 0
    creation_date: str = ""
    raw_payload: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        normalize_party_state(self)

    def to_dict(self) -> dict[str, Any]:
        normalize_party_state(self)
        return {
            "campaign_id": self.campaign_id,
            "seed": int(self.seed),
            "party": list(self.party),
            "inactive_npcs": list(self.inactive_npcs),
            "current_area_id": self.current_area_id,
            "loaded_area_ids": list(self.loaded_area_ids),
            "loaded_areas": {key: value.to_dict() for key, value in self.loaded_areas.items()},
            "actors": {key: value.to_dict(include_action_points=True) for key, value in self.actors.items()},
            "global_variables": serialize_value(self.global_variables),
            "local_variables": serialize_value(self.local_variables),
            "journal": [entry.to_dict() for entry in self.journal],
            "world_time": self.world_time.to_dict(),
            "reputation": int(self.reputation),
            "difficulty": self.difficulty.to_dict(),
            "formation": self.formation,
                "party_tactics": dict(self.party_tactics),
                "party_tactics": dict(self.party_tactics),
            "play_time_ticks": int(self.play_time_ticks),
            "creation_date": self.creation_date,
            "raw_payload": serialize_value(self.raw_payload),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GameState":
        state = cls(
            campaign_id=str(data["campaign_id"]),
            seed=int(data["seed"]),
            party=[str(item) for item in data.get("party", [])],
            inactive_npcs=[str(item) for item in data.get("inactive_npcs", [])],
            current_area_id=str(data.get("current_area_id", "")),
            loaded_area_ids=[str(item) for item in data.get("loaded_area_ids", [])],
            loaded_areas={key: AreaState.from_dict(value) for key, value in dict(data.get("loaded_areas", {})).items()},
            actors={key: ActorRecord.from_dict(value) for key, value in dict(data.get("actors", {})).items()},
            global_variables=dict(data.get("global_variables", {})),
            local_variables={str(key): dict(value) for key, value in dict(data.get("local_variables", {})).items()},
            journal=[JournalEntry.from_dict(entry) for entry in data.get("journal", [])],
            world_time=WorldTime.from_dict(data.get("world_time", {})),
            reputation=int(data.get("reputation", 10)),
            difficulty=DifficultySettings.from_dict(data.get("difficulty", {})),
            formation=str(data.get("formation", "wedge")),
                party_tactics={
                    str(key): _normalized_party_tactic_mode(value)
                    for key, value in dict(data.get("party_tactics", {})).items()
                },
            play_time_ticks=int(data.get("play_time_ticks", 0)),
            creation_date=str(data.get("creation_date", "")),
            raw_payload=dict(data.get("raw_payload", {})),
        )
        return normalize_party_state(state)


def create_game_state(campaign_id: str, seed: int, difficulty: str = "normal") -> GameState:
    return GameState(
        campaign_id=str(campaign_id),
        seed=int(seed),
        difficulty=DifficultySettings.from_level(difficulty),
        creation_date="",
    )


def add_to_party(state: GameState, actor_id: str) -> tuple[bool, str]:
    actor_id = str(actor_id)
    normalize_party_state(state)
    if actor_id == "player":
        if "player" not in state.party:
            state.party.insert(0, "player")
        normalize_party_state(state)
        return True, "already in party"
    if actor_id in state.party:
        return True, "already in party"
    if len(state.party) >= 6:
        return False, "party full"
    state.party.append(actor_id)
    normalize_party_state(state)
    return True, "added"


def remove_from_party(state: GameState, actor_id: str) -> None:
    actor_id = str(actor_id)
    normalize_party_state(state)
    if actor_id == "player":
        normalize_party_state(state)
        return
    if actor_id in state.party:
        state.party.remove(actor_id)
    state.party_tactics.pop(actor_id, None)
    if actor_id and actor_id not in state.party and actor_id not in state.inactive_npcs:
        state.inactive_npcs.append(actor_id)
    normalize_party_state(state)


def swap_party_member(state: GameState, active_id: str, inactive_id: str) -> tuple[bool, str]:
    normalize_party_state(state)
    active_id = str(active_id)
    inactive_id = str(inactive_id)
    if active_id == "player" or inactive_id == "player" or active_id == inactive_id:
        return False, "invalid swap"
    if active_id not in state.party or inactive_id not in state.inactive_npcs:
        return False, "invalid swap"
    index = state.party.index(active_id)
    state.party[index] = inactive_id
    state.inactive_npcs.remove(inactive_id)
    if active_id not in state.inactive_npcs:
        state.inactive_npcs.append(active_id)
    normalize_party_state(state)
    return True, "swapped"


def set_party_formation(state: GameState, formation: str) -> tuple[bool, str]:
    normalized = _normalized_formation_name(formation)
    if normalized != str(formation or "").lower().strip() and str(formation or "").lower().strip() not in FORMATIONS:
        return False, "invalid formation"
    state.formation = normalized
    normalize_party_state(state)
    return True, normalized


def set_party_tactic(state: GameState, actor_id: str, tactic: str) -> tuple[bool, str]:
    normalize_party_state(state)
    actor_id = str(actor_id)
    if not actor_id or actor_id == "player":
        return False, "invalid tactic"
    normalized = str(tactic or "").lower().strip()
    if not _is_valid_party_tactic_mode(normalized):
        return False, "invalid tactic"
    state.party_tactics[actor_id] = normalized
    normalize_party_state(state)
    return True, normalized


def set_party_tactics_for_party(state: GameState, tactic: str, actor_ids: list[str] | None = None) -> tuple[bool, str]:
    normalize_party_state(state)
    normalized = str(tactic or "").lower().strip()
    if not _is_valid_party_tactic_mode(normalized):
        return False, "invalid tactic"
    targets = [str(actor_id) for actor_id in (actor_ids if actor_ids is not None else state.party) if str(actor_id) and str(actor_id) != "player"]
    for actor_id in targets:
        state.party_tactics[actor_id] = normalized
    normalize_party_state(state)
    return True, normalized


def clear_party_tactic(state: GameState, actor_id: str) -> None:
    normalize_party_state(state)
    state.party_tactics.pop(str(actor_id), None)
    normalize_party_state(state)


def party_tactic_mode(state: GameState, actor_id: str) -> str:
    normalize_party_state(state)
    return _normalized_party_tactic_mode(state.party_tactics.get(str(actor_id), "balanced"))


    def party_tactic_for_actor(state: GameState, actor_id: str) -> str:
        return party_tactic_mode(state, actor_id)


def party_tactic_for_actor(state: GameState, actor_id: str) -> str:
    return party_tactic_mode(state, actor_id)


def transition_to_area(state: GameState, area_id: str, position: tuple[int, int] | None = None) -> dict:
    area_id = str(area_id)
    max_cache = int(state.raw_payload.get("max_area_cache", 4))
    evicted: str | None = None
    loaded = area_id in state.loaded_areas
    if loaded:
        if area_id in state.loaded_area_ids:
            state.loaded_area_ids.remove(area_id)
        state.loaded_area_ids.append(area_id)
    else:
        if len(state.loaded_area_ids) >= max_cache and state.loaded_area_ids:
            evicted = state.loaded_area_ids.pop(0)
            state.loaded_areas.pop(evicted, None)
        state.loaded_area_ids.append(area_id)
        state.loaded_areas[area_id] = AreaState(area_id=area_id)
    state.current_area_id = area_id
    if position is not None:
        state.raw_payload["current_area_position"] = [int(position[0]), int(position[1])]
    return {"loaded": not loaded, "evicted": evicted}


def set_global_variable(state: GameState, scope: str, name: str, value: Any) -> None:
    scope_key = str(scope)
    if scope_key == "GLOBAL":
        state.global_variables[str(name)] = value
        return
    if scope_key == "MYAREA":
        scope_key = state.current_area_id
    state.local_variables.setdefault(scope_key, {})[str(name)] = value


def get_global_variable(state: GameState, scope: str, name: str, default: Any = None) -> Any:
    scope_key = str(scope)
    if scope_key == "GLOBAL":
        return state.global_variables.get(str(name), default)
    if scope_key == "MYAREA":
        scope_key = state.current_area_id
    return state.local_variables.get(scope_key, {}).get(str(name), default)


def add_journal_entry(state: GameState, text: str, quest_id: str = "", quest_stage: int = 0) -> None:
    entry = JournalEntry(
        entry_id=f"journal_{len(state.journal) + 1}",
        text=str(text),
        quest_id=str(quest_id),
        quest_stage=int(quest_stage),
        timestamp=int(state.world_time.game_tick),
        entry_type="quest" if quest_id else "info",
    )
    state.journal.append(entry)


def get_quest_entries(state: GameState, quest_id: str) -> list[JournalEntry]:
    return [entry for entry in state.journal if entry.quest_id == str(quest_id)]


def get_latest_stage(state: GameState, quest_id: str) -> int:
    entries = get_quest_entries(state, quest_id)
    if not entries:
        return 0
    return max(int(entry.quest_stage) for entry in entries)


def advance_time(state: GameState, ticks: int) -> list[dict]:
    state.play_time_ticks += max(0, int(ticks))
    return state.world_time.advance(int(ticks))


def modify_reputation(state: GameState, delta: int) -> int:
    state.reputation = max(1, min(20, int(state.reputation) + int(delta)))
    return state.reputation


def set_difficulty(state: GameState, level: str) -> None:
    state.difficulty = DifficultySettings.from_level(level)


def derive_seed(base_seed: int, context: str) -> int:
    digest = hashlib.sha256(f"{int(base_seed)}::{context}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big", signed=False)
