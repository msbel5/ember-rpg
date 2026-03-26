"""
Deterministic soak and chaos sessions for terminal/backend gameplay hardening.
"""
import random
from pathlib import Path

import pytest

from engine.api.game_engine import GameEngine
from engine.api.routes import _sessions
from engine.core.character import Character
from engine.world.entity import Entity, EntityType


pytestmark = pytest.mark.playtest


def _entity_by_role(session, role):
    for entity_id, entity in session.entities.items():
        if entity.get("role") == role:
            return entity_id, entity
    raise AssertionError(f"Missing entity role: {role}")


def _log_entry(session, command, narrative):
    snapshot = session.to_dict()
    return {
        "command": command,
        "narrative": narrative,
        "hp": snapshot["player"]["hp"],
        "ap": snapshot["player"].get("ap"),
        "conditions": list(snapshot["player"].get("conditions", [])),
        "alignment": snapshot["player"].get("alignment"),
        "alignment_axes": dict(snapshot["player"].get("alignment_axes", {})),
        "conversation_state": dict(snapshot.get("conversation_state", {})),
    }


def _assert_session_sane(session, label):
    snapshot = session.to_dict()
    assert session.player is not None, f"player missing after {label}"
    assert session.player.hp >= 0, f"negative hp after {label}"
    assert session.game_time is not None, f"missing game time after {label}"
    assert snapshot["player"]["max_hp"] >= snapshot["player"]["hp"], f"hp overflow after {label}"
    assert snapshot["conversation_state"]["target_type"] in {"dm", "npc", "self"}, f"bad conversation state after {label}"
    if session.spatial_index is not None:
        player_count = sum(1 for entity in session.spatial_index.all_entities() if entity.id == "player")
        assert player_count == 1, f"duplicate player entities after {label}"
    return snapshot


def _prepare_session(tmp_path: Path, seed: int, session_id: str, *, player_name: str = "Chaos", player_class: str = "rogue"):
    random.seed(seed)
    _sessions.clear()
    engine = GameEngine()
    engine.save_system.save_dir = Path(tmp_path) / session_id
    engine.save_system.save_dir.mkdir(parents=True, exist_ok=True)

    session = engine.new_session(player_name, player_class, location="Harbor Town", alignment="CN")
    session.session_id = session_id
    if session.world_state is not None:
        session.world_state.game_id = session.session_id
    if session.npc_memory is not None:
        session.npc_memory.session_id = session.session_id
    return engine, session


def _install_hidden_cache(session) -> None:
    px, py = session.position
    for dx, dy in ((1, 0), (0, 1), (-1, 0), (0, -1)):
        tx, ty = px + dx, py + dy
        if session.map_data and not session.map_data.is_walkable(tx, ty):
            continue
        if session.spatial_index is not None:
            blockers = [entity for entity in session.spatial_index.at(tx, ty) if entity.blocking and entity.id != "player"]
            if blockers:
                continue
        hidden = Entity(
            id="hidden_cache",
            entity_type=EntityType.ITEM,
            name="Hidden Cache",
            position=(tx, ty),
            glyph="*",
            color="yellow",
            blocking=False,
        )
        hidden.hidden = True
        session.spatial_index.add(hidden)
        session.entities[hidden.id] = {
            "name": hidden.name,
            "position": [tx, ty],
            "glyph": hidden.glyph,
            "color": hidden.color,
            "blocking": False,
            "alive": True,
            "type": hidden.entity_type.value,
            "hidden": True,
            "entity_ref": hidden,
        }
        return
    raise AssertionError("Could not place hidden cache near player")


def _install_bread_run_offer(session):
    merchant_id, merchant = _entity_by_role(session, "merchant")
    session.quest_offers.append({
        "id": "chaos_bread_run",
        "title": "Bread Run",
        "type": "delivery",
        "source": "authored",
        "required_items": [{"id": "bread", "qty": 1}],
        "rewards": {"gold": 5},
        "meta": {
            "giver_entity_id": merchant_id,
            "giver_name": merchant["name"],
        },
    })
    session.add_item({"id": "bread", "name": "Bread", "qty": 1, "weight": 0.2}, merge=True)
    session.add_item({"id": "iron_bar", "name": "Iron Bar", "qty": 2, "weight": 0.4}, merge=True)


def _force_death_save_segment(engine: GameEngine, session, logs, coverage):
    enemy = Character(
        name="Executioner",
        classes={"warrior": 5},
        stats={"MIG": 20, "AGI": 12, "END": 16, "MND": 8, "INS": 10, "PRE": 8},
        hp=28,
        max_hp=28,
        level=5,
        xp=0,
    )
    enemy.sync_derived_progression()

    session.player.hp = 1
    session.player.base_ac = 8
    session.player._base_ac = 8
    session.equipment = {slot: None for slot in session.equipment.keys()}
    session.sync_player_state()
    engine._start_combat(session, [enemy])

    player_combatant = next(combatant for combatant in session.combat.combatants if combatant.name == session.player.name)
    session.player.hp = 0
    player_combatant.character.hp = 0
    session.sync_player_state()

    if session.combat.active_combatant.name == session.player.name:
        session.combat.end_turn()
    messages = engine._advance_combat_until_player_turn(session)
    logs.append(_log_entry(session, "death-save-resolution", "\n".join(messages) or "death save resolution"))
    _assert_session_sane(session, "death-save-resolution")
    if session.player.death_save_successes or session.player.death_save_failures or session.player.hp == 0:
        coverage["death_save"] = True
    assert coverage["death_save"], "Death save path never triggered during soak segment"

    session.combat = None
    session.player.hp = session.player.max_hp
    session.player.death_save_successes = 0
    session.player.death_save_failures = 0
    session.player.conditions = [condition for condition in session.player.conditions if condition != "unconscious"]
    session.sync_player_state()


def _run_command(engine: GameEngine, session, command: str, logs, coverage):
    result = engine.process_action(session, command)
    snapshot = _assert_session_sane(session, command)
    assert isinstance(result.narrative, str), f"non-string narrative for {command}"
    assert result.narrative.strip(), f"empty narrative for {command}"
    logs.append(_log_entry(session, command, result.narrative))

    lowered = command.lower()
    if lowered.startswith("approach "):
        coverage["approached_roles"].add(lowered.replace("approach ", "").strip())
    if lowered.startswith("talk to "):
        coverage["talked_roles"].add(lowered.replace("talk to ", "").strip())
    if lowered.startswith("persuade "):
        coverage["social_actions"].add("persuade")
    if lowered.startswith("bribe "):
        coverage["social_actions"].add("bribe")
    if lowered.startswith("deceive "):
        coverage["social_actions"].add("deceive")
    if lowered.startswith("intimidate "):
        coverage["social_actions"].add("intimidate")
    if "think" in lowered and "history" in lowered:
        coverage["think_topics"].add("history")
    if "think" in lowered and "arcana" in lowered:
        coverage["think_topics"].add("arcana")
    if "think" in lowered and "religion" in lowered:
        coverage["think_topics"].add("religion")
    if lowered == "disengage":
        coverage["disengage"] = True
    if lowered == "flee":
        coverage["flee"] = True
    if lowered == "short rest":
        coverage["short_rest"] = True
    if lowered == "long rest":
        coverage["long_rest"] = True
    if lowered.startswith("steal "):
        coverage["steal"] = True
    if lowered.startswith("save game") and "saved" in result.narrative.lower():
        coverage["saved"] = True
    if lowered.startswith("load ") and "loaded save slot" in result.narrative.lower():
        coverage["loaded"] = True
    if lowered.startswith("accept quest") and (
        result.state_changes.get("accepted_quest")
        or "quest accepted" in result.narrative.lower()
    ):
        coverage["quest_accept"] = True
    if lowered.startswith("turn in quest") and (
        result.state_changes.get("turned_in_quest")
        or "you turn in" in result.narrative.lower()
    ):
        coverage["quest_turn_in"] = True
    if lowered.startswith("craft ") and result.state_changes.get("crafted"):
        coverage["crafted"] = True
    if lowered.startswith("attack "):
        coverage["combat"] = True
    if "hidden cache" in result.narrative.lower() or not session.entities.get("hidden_cache", {}).get("hidden", True):
        coverage["passive_reveal"] = True
    if any(int(value) != 0 for value in snapshot["player"].get("alignment_axes", {}).values()):
        coverage["alignment_shift"] = True
    return result


def test_seeded_500_turn_terminal_soak(tmp_path):
    engine, session = _prepare_session(tmp_path, 1337, "soak-500")
    _install_hidden_cache(session)
    _install_bread_run_offer(session)

    coverage = {
        "approached_roles": set(),
        "talked_roles": set(),
        "social_actions": set(),
        "think_topics": set(),
        "combat": False,
        "disengage": False,
        "flee": False,
        "death_save": False,
        "short_rest": False,
        "long_rest": False,
        "crafted": False,
        "quest_accept": False,
        "quest_turn_in": False,
        "saved": False,
        "loaded": False,
        "steal": False,
        "passive_reveal": False,
        "alignment_shift": False,
    }

    scripted_prefix = [
        "look",
        "approach merchant",
        "talk to merchant",
        "trade with merchant",
        "deceive merchant",
        "think what do i know about this town's history",
        "approach guard",
        "talk to guard",
        "bribe guard",
        "approach blacksmith",
        "talk to blacksmith",
        "persuade blacksmith",
        "approach priest",
        "talk to priest",
        "think what does my arcana tell me about these runes",
        "think what does religion tell me about this temple",
        "approach beggar",
        "talk to beggar",
        "intimidate beggar",
        "approach forge",
        "craft iron sword",
        "approach merchant",
        "accept quest bread run",
        "turn in quest bread run",
        "steal from merchant",
        "attack guard",
        "disengage",
        "flee",
        "short rest",
        "long rest",
        "save game as soak_slot",
        "load soak_slot",
        "list saves",
    ]
    filler_cycle = [
        "look",
        "inventory",
        "approach merchant",
        "talk to merchant",
        "trade with merchant",
        "approach guard",
        "talk to guard",
        "approach blacksmith",
        "talk to blacksmith",
        "approach priest",
        "talk to priest",
        "approach beggar",
        "talk to beggar",
        "think town history",
        "think arcana of the harbor lights",
        "think religion of the old shrine",
        "search",
        "north",
        "south",
        "east",
        "west",
        "rest",
    ]

    logs = []
    for command in scripted_prefix:
        _run_command(engine, session, command, logs, coverage)

    _force_death_save_segment(engine, session, logs, coverage)

    while len(logs) < 500:
        for command in filler_cycle:
            if len(logs) >= 500:
                break
            _run_command(engine, session, command, logs, coverage)

    snapshot = session.to_dict()
    assert len(logs) == 500
    assert coverage["approached_roles"] >= {"merchant", "guard", "blacksmith", "priest", "beggar"}
    assert coverage["talked_roles"] >= {"merchant", "guard", "blacksmith", "priest", "beggar"}
    assert coverage["social_actions"] == {"persuade", "bribe", "deceive", "intimidate"}
    assert coverage["think_topics"] == {"history", "arcana", "religion"}
    assert coverage["combat"]
    assert coverage["disengage"]
    assert coverage["flee"]
    assert coverage["death_save"]
    assert coverage["short_rest"]
    assert coverage["long_rest"]
    assert coverage["crafted"]
    assert coverage["quest_accept"]
    assert coverage["quest_turn_in"]
    assert coverage["saved"]
    assert coverage["loaded"]
    assert coverage["steal"]
    assert coverage["passive_reveal"]
    assert coverage["alignment_shift"]
    assert snapshot["player"]["alignment"]
    assert snapshot["conversation_state"]["target_type"] in {"dm", "npc", "self"}


@pytest.mark.parametrize("seed", [7, 19, 73])
def test_seeded_chaos_matrix(tmp_path, seed):
    engine, session = _prepare_session(tmp_path, seed, f"chaos-{seed}")
    _install_bread_run_offer(session)

    rng = random.Random(seed)
    action_pool = [
        "look",
        "inventory",
        "approach merchant",
        "talk to merchant",
        "trade with merchant",
        "approach guard",
        "talk to guard",
        "deceive guard",
        "approach priest",
        "talk to priest",
        "approach blacksmith",
        "talk to blacksmith",
        "approach beggar",
        "talk to beggar",
        "search",
        "north",
        "south",
        "east",
        "west",
        "rest",
        "short rest",
        "steal from merchant",
        "attack goblin",
        "flee",
        "save game as matrix_slot",
        "load matrix_slot",
    ]

    logs = []
    for command in [
        "look",
        "approach merchant",
        "talk to merchant",
        "accept quest bread run",
        "turn in quest bread run",
        "save game as matrix_slot",
        "load matrix_slot",
    ]:
        result = engine.process_action(session, command)
        logs.append(_log_entry(session, command, result.narrative))
        _assert_session_sane(session, command)

    for turn in range(150):
        command = rng.choice(action_pool)
        result = engine.process_action(session, command)
        logs.append(_log_entry(session, command, result.narrative))
        snapshot = _assert_session_sane(session, f"seed={seed} turn={turn} cmd={command}")
        assert result.narrative.strip()
        assert snapshot["player"]["alignment"]

    final_snapshot = session.to_dict()
    assert len(logs) == 157
    assert final_snapshot["player"]["hp"] >= 0
    assert final_snapshot["conversation_state"]["target_type"] in {"dm", "npc", "self"}
    assert final_snapshot["player"]["alignment"]
