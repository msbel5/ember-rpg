"""
Seeded 100-turn chaos session smoke test for the final D&D pass.
"""
import random
from pathlib import Path

from engine.api.game_engine import GameEngine
from engine.api.routes import _sessions


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


def test_seeded_100_turn_chaos_session(tmp_path):
    random.seed(1337)
    _sessions.clear()
    engine = GameEngine()
    engine.save_system.save_dir = Path(tmp_path) / "saves"
    engine.save_system.save_dir.mkdir(parents=True, exist_ok=True)

    session = engine.new_session("Chaos", "rogue", location="Market Town", alignment="CN")
    session.session_id = "chaos-session-fixed"
    if session.world_state is not None:
        session.world_state.game_id = session.session_id
    if session.npc_memory is not None:
        session.npc_memory.session_id = session.session_id
    merchant_id, merchant = _entity_by_role(session, "merchant")
    _guard_id, _guard = _entity_by_role(session, "guard")
    _blacksmith_id, _blacksmith = _entity_by_role(session, "blacksmith")
    _priest_id, _priest = _entity_by_role(session, "priest")

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

    scripted_prefix = [
        "look",
        "approach merchant",
        "talk to merchant",
        "I am the mayor's envoy.",
        "deceive merchant",
        "trade with merchant",
        "think what do i know about this town's history",
        "approach guard",
        "talk to guard",
        "bribe guard",
        "deceive guard",
        "approach blacksmith",
        "talk to blacksmith",
        "persuade blacksmith",
        "approach priest",
        "talk to priest",
        "approach beggar",
        "talk to beggar",
        "intimidate beggar",
        "approach merchant",
        "accept quest bread run",
        "turn in quest bread run",
        "steal from merchant",
        "attack merchant",
        "disengage",
        "flee",
        "short rest",
        "long rest",
        "save game as chaos_slot",
        "load chaos_slot",
        "list saves",
    ]
    filler_cycle = [
        "look",
        "inventory",
        "think town history",
        "talk to priest",
        "The town feels tense.",
        "approach guard",
        "talk to guard",
        "approach merchant",
        "trade with merchant",
        "north",
        "south",
        "east",
        "west",
    ]

    commands = list(scripted_prefix)
    while len(commands) < 100:
        commands.extend(filler_cycle)
    commands = commands[:100]

    logs = []
    for command in commands:
        result = engine.process_action(session, command)
        assert isinstance(result.narrative, str)
        assert result.narrative.strip()
        logs.append(_log_entry(session, command, result.narrative))

    snapshot = session.to_dict()
    assert len(logs) == 100
    assert all(entry["command"] for entry in logs)
    assert all(entry["narrative"] for entry in logs)
    assert snapshot["player"]["alignment"] != ""
    assert "conversation_state" in snapshot
    assert session.player.hp > 0
    assert any(
        int(value) != 0 for value in session.player.alignment_axes.values()
    ) or any(
        any(int(value) != 0 for value in entry["alignment_axes"].values())
        for entry in logs
    )
    assert any("Game saved" in entry["narrative"] for entry in logs)
    assert any("Loaded save slot" in entry["narrative"] for entry in logs)
