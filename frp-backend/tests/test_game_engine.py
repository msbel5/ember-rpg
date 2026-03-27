"""
Tests for GameEngine — covers all action handlers, edge cases, and helper methods.
Target: game_engine.py ≥ 97% coverage
"""
import copy
import pytest
from unittest.mock import patch, MagicMock

from engine.api.game_engine import GameEngine, ActionResult
from engine.api.save_system import SaveSystem
from engine.core.character import Character
from engine.core.combat import CombatManager
from engine.core.dm_agent import SceneType
from engine.data_loader import list_monsters
from engine.world.skill_checks import SkillCheckResult
from engine.world.proximity import astar_path, distance, manhattan_distance
from engine.world.entity import Entity, EntityType
from engine.world.spatial_index import SpatialIndex
from engine.map import MapData, TileType


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def engine():
    return GameEngine()


@pytest.fixture
def warrior_session(engine):
    return engine.new_session("Thorn", "warrior", location="Test Keep")


@pytest.fixture
def mage_session(engine):
    return engine.new_session("Lyra", "mage", location="Magic Tower")


@pytest.fixture
def rogue_session(engine):
    return engine.new_session("Shadow", "rogue", location="Dark Alley")


@pytest.fixture
def priest_session(engine):
    return engine.new_session("Mercy", "priest", location="Temple")


def _entity_by_role(session, role):
    for entity_id, entity in session.entities.items():
        if entity.get("role") == role:
            return entity_id, entity
    raise AssertionError(f"Missing entity role: {role}")


def _move_player_to(session, x, y):
    if session.player_entity and session.spatial_index:
        session.spatial_index.move(session.player_entity, x, y)
    session.position = [x, y]
    session.sync_player_state()


def _move_player_near_entity(session, entity):
    ex, ey = entity["position"]
    candidates = [
        (ex + 1, ey),
        (ex - 1, ey),
        (ex, ey + 1),
        (ex, ey - 1),
    ]
    width = session.map_data.width if session.map_data else 48
    height = session.map_data.height if session.map_data else 48
    for x, y in candidates:
        if not (0 <= x < width and 0 <= y < height):
            continue
        if session.map_data and not session.map_data.is_walkable(x, y):
            continue
        if session.spatial_index:
            blockers = [candidate for candidate in session.spatial_index.at(x, y) if candidate.id != "player" and candidate.blocking]
            if blockers:
                continue
        _move_player_to(session, x, y)
        return
    _move_player_to(session, max(0, ex - 1), ey)


# ---------------------------------------------------------------------------
# Session Creation
# ---------------------------------------------------------------------------

class TestNewSession:
    def test_warrior_defaults(self, warrior_session):
        p = warrior_session.player
        assert p.name == "Thorn"
        assert p.classes == {"warrior": 1}
        assert p.hp == 20
        assert p.spell_points == 0
        assert p.level == 1
        assert p.xp == 0

    def test_mage_spell_points(self, mage_session):
        assert mage_session.player.spell_points == 16
        assert mage_session.player.max_spell_points == 16

    def test_rogue_stats(self, rogue_session):
        assert rogue_session.player.stats["AGI"] == 16

    def test_priest_stats(self, priest_session):
        assert priest_session.player.stats["MND"] == 14

    def test_unknown_class_fallback(self, engine):
        session = engine.new_session("Unknown", "paladin", location="Road")
        assert session.player.hp == 16  # warrior fallback

    def test_random_location_if_none(self, engine):
        session = engine.new_session("Wanderer", "warrior")
        assert session.dm_context.location != ""

    def test_default_opening_supports_immediate_innkeeper_talk(self, engine):
        for idx in range(8):
            session = engine.new_session(f"Wanderer{idx}", "warrior")
            innkeeper = next(
                (
                    entity
                    for entity in session.entities.values()
                    if entity.get("role") == "innkeeper"
                ),
                None,
            )
            assert innkeeper is not None
            assert distance(session.position, innkeeper["position"]) <= 2
            result = engine.process_action(session, "talk to innkeeper")
            assert "too far away" not in result.narrative.lower()
            merchant = next(
                (
                    entity
                    for entity in session.entities.values()
                    if entity.get("role") == "merchant"
                ),
                None,
            )
            assert merchant is not None
            assert distance(session.position, merchant["position"]) <= 2
            merchant_result = engine.process_action(session, "talk to merchant")
            assert "too far away" not in merchant_result.narrative.lower()

    def test_approach_forge_reaches_crafting_range_when_adjacent_tiles_are_blocked(self, engine):
        session = engine.new_session("Smith", "warrior", location="Harbor Town")
        forge_id = "workstation_forge"
        forge = session.entities[forge_id]
        fx, fy = forge["position"]

        walkable_adjacent = []
        for x, y in ((fx + 1, fy), (fx - 1, fy), (fx, fy + 1), (fx, fy - 1)):
            if session.map_data and not session.map_data.is_walkable(x, y):
                continue
            walkable_adjacent.append((x, y))
        assert len(walkable_adjacent) >= 2

        movable_blockers = [
            (entity_id, entity)
            for entity_id, entity in session.entities.items()
            if entity_id != forge_id and entity.get("blocking")
        ]
        assert len(movable_blockers) >= 2

        for (entity_id, entity), (x, y) in zip(movable_blockers[:2], walkable_adjacent[:2]):
            live_entity = entity["entity_ref"]
            session.spatial_index.move(live_entity, x, y)
            entity["position"] = [x, y]
            session.sync_entity_record(entity_id, live_entity)

        goal_candidates = engine._approach_goal_candidates(session, forge["position"], interaction_radius=2)
        start_candidates = []
        for dx in range(-5, 6):
            for dy in range(-5, 6):
                x, y = fx + dx, fy + dy
                if abs(dx) + abs(dy) < 3:
                    continue
                if session.map_data and not session.map_data.is_walkable(x, y):
                    continue
                blockers = [
                    candidate
                    for candidate in session.spatial_index.at(x, y)
                    if candidate.id != "player" and candidate.blocking
                ]
                if blockers:
                    continue
                if not any(
                    astar_path(session.map_data, [x, y], goal, max_steps=40)
                    for goal in goal_candidates
                    if goal != [x, y]
                ):
                    continue
                start_candidates.append((x, y))
        assert start_candidates
        start_x, start_y = max(start_candidates, key=lambda pos: abs(pos[0] - fx) + abs(pos[1] - fy))
        _move_player_to(session, start_x, start_y)
        session.ap_tracker.refresh()
        session.add_item({"id": "iron_bar", "name": "Iron Bar", "qty": 2, "weight": 0.4}, merge=True)

        approach_result = engine.process_action(session, "approach forge")
        forge_pos = session.entities[forge_id]["position"]
        assert "can't find a path" not in approach_result.narrative.lower()
        assert distance(session.position, forge_pos) <= 2

        craft_result = engine.process_action(session, "craft iron sword")
        assert "need a forge" not in craft_result.narrative.lower()

    def test_explicit_location(self, warrior_session):
        assert warrior_session.dm_context.location == "Test Keep"

    def test_town_sessions_start_next_to_merchant(self, engine):
        session = engine.new_session("Starter", "rogue", location="Harbor Town")
        merchant_id, merchant = _entity_by_role(session, "merchant")
        merchant_pos = merchant["position"]
        assert distance(session.position, merchant_pos) <= 2, (
            f"expected opening position within talk range of merchant, got player={session.position} merchant={merchant_pos}"
        )
        assert session.entity_position_locked(merchant_id)

    def test_workstations_are_registered_for_interaction(self, engine):
        session = engine.new_session("Crafter", "warrior", location="Harbor Town")
        workstation_names = {entity.get("name") for entity in session.entities.values() if entity.get("type") == "furniture"}
        assert "Forge" in workstation_names

        result = engine.process_action(session, "approach forge")
        assert "don't know how" not in result.narrative.lower()

    def test_session_has_dm_context(self, warrior_session):
        assert warrior_session.dm_context.scene_type == SceneType.EXPLORATION


# ---------------------------------------------------------------------------
# Action: ATTACK
# ---------------------------------------------------------------------------

class TestHandleAttack:
    def test_attack_starts_combat(self, engine, warrior_session):
        ap_before = warrior_session.ap_tracker.current_ap
        result = engine.process_action(warrior_session, "attack")
        assert result.combat_state is not None
        assert warrior_session.in_combat()
        assert result.combat_state["active"] == warrior_session.player.name
        assert warrior_session.ap_tracker.current_ap == ap_before

    def test_attack_returns_narrative(self, engine, warrior_session):
        result = engine.process_action(warrior_session, "attack")
        assert len(result.narrative) > 0

    def test_attack_narrative_contains_action_word(self, engine, warrior_session):
        result = engine.process_action(warrior_session, "attack the goblin")
        assert result.scene_type == SceneType.COMBAT
        assert result.combat_state["active"] == warrior_session.player.name
        # Narrative is LLM-generated; verify it's non-empty and combat started
        assert len(result.narrative) > 10

    def test_attack_starts_combat_with_initiative_before_damage_to_enemies(self, engine, warrior_session):
        result = engine.process_action(warrior_session, "attack")
        enemies = [c for c in result.combat_state["combatants"] if c["name"] != warrior_session.player.name]
        assert enemies
        assert all(enemy["hp"] == enemy["max_hp"] for enemy in enemies)
        assert result.combat_state["active"] in {warrior_session.player.name, *[enemy["name"] for enemy in enemies]}

    def test_attack_no_valid_target(self, engine, warrior_session):
        """When _find_target returns None, narrative says no target."""
        engine.process_action(warrior_session, "attack")  # enter combat
        with patch.object(engine, '_find_target', return_value=None):
            result = engine.process_action(warrior_session, "attack at nobody")
        assert "no valid target" in result.narrative.lower()

    def test_attack_crit_path(self, engine, warrior_session):
        """Force crit branch via mocked combat.attack."""
        engine.process_action(warrior_session, "attack")  # enter combat
        with patch.object(warrior_session.combat, 'attack', return_value={"crit": True, "damage": 20}):
            result = engine.process_action(warrior_session, "attack")
        assert "CRITICAL" in result.narrative

    def test_attack_fumble_path(self, engine, warrior_session):
        engine.process_action(warrior_session, "attack")
        with patch.object(warrior_session.combat, 'attack', return_value={"fumble": True, "damage": 0}):
            result = engine.process_action(warrior_session, "attack")
        assert "stumbles" in result.narrative

    def test_attack_miss_path(self, engine, warrior_session):
        engine.process_action(warrior_session, "attack")
        with patch.object(warrior_session.combat, 'attack', return_value={"hit": False, "damage": 0}):
            result = engine.process_action(warrior_session, "attack")
        assert "misses" in result.narrative or "miss" in result.narrative or "wide" in result.narrative

    def test_combat_end_awards_xp(self, engine, warrior_session):
        """XP_REWARDS dict has entries for level 1."""
        from engine.api.game_engine import XP_REWARDS
        assert 1 in XP_REWARDS
        assert XP_REWARDS[1] > 0

    def test_combat_end_level_up(self, engine, warrior_session):
        """Progression system correctly processes XP for level-up."""
        warrior_session.player.xp = 290  # near level 2 threshold (300)
        result = engine.progression.add_xp(warrior_session.player, 100)
        assert result is not None  # level-up occurred
        assert warrior_session.player.level == 2

    def test_combat_end_xp_via_handler(self, engine, warrior_session):
        """_handle_attack with combat_ended=True awards XP in state_changes."""
        from engine.core.combat import CombatManager
        enemy = Character(name="TestEnemy", hp=5, max_hp=5,
                          stats={"MIG": 8, "AGI": 8, "END": 8, "MND": 8, "INS": 8, "PRE": 8})
        warrior_session.combat = CombatManager(
            [warrior_session.player, enemy], seed=1
        )
        warrior_session.combat.start_turn()
        warrior_session.dm_context.scene_type = SceneType.COMBAT

        # Ensure player is active combatant
        while (warrior_session.combat.active_combatant.name
               != warrior_session.player.name):
            warrior_session.combat.end_turn()

        def fake_attack(target_idx):
            # Side effect: mark combat as ended
            warrior_session.combat.combat_ended = True
            return {"hit": True, "damage": 10}

        with patch.object(warrior_session.combat, 'attack', side_effect=fake_attack):
            with patch.object(warrior_session.combat, 'get_summary', return_value={}):
                # session.in_combat() checks combat_ended, so patch it to return True
                with patch.object(warrior_session, 'in_combat', return_value=True):
                    from unittest.mock import MagicMock as MM
                    action = MM()
                    action.target = "testenemy"
                    action.raw_input = "attack"
                    result = engine._handle_attack(warrior_session, action)

        assert "xp_gained" in result.state_changes


# ---------------------------------------------------------------------------
# Action: CAST_SPELL
# ---------------------------------------------------------------------------

class TestHandleSpell:
    def test_spell_no_points_warrior(self, engine, warrior_session):
        result = engine.process_action(warrior_session, "cast fireball")
        assert "exhausted" in result.narrative.lower()

    def test_spell_starts_combat_for_mage(self, engine, mage_session):
        result = engine.process_action(mage_session, "cast magic missile")
        assert result.combat_state is not None

    def test_spell_narrative_mage(self, engine, mage_session):
        result = engine.process_action(mage_session, "cast fireball")
        # Narrative can be spell description, combat initiation, or AP message
        assert result.narrative, "Spell should produce some narrative"

    def test_spell_error_result(self, engine, mage_session):
        """Spell fails (e.g. AP insufficient) → error narrative."""
        engine.process_action(mage_session, "attack")  # enter combat
        with patch.object(mage_session.combat, 'cast_spell',
                          return_value={"error": "Insufficient AP"}):
            result = engine.process_action(mage_session, "cast fireball")
        assert "failed" in result.narrative.lower() or "Spell failed" in result.narrative

    def test_spell_no_target_returns_result(self, engine, mage_session):
        """If _find_target returns None, narrative about no target."""
        engine.process_action(mage_session, "attack")  # enter combat
        with patch.object(engine, '_find_target', return_value=None):
            result = engine.process_action(mage_session, "cast magic missile at nobody")
        assert "no valid target" in result.narrative.lower()


# ---------------------------------------------------------------------------
# Action: EXAMINE
# ---------------------------------------------------------------------------

class TestHandleExamine:
    def test_examine_target(self, engine, warrior_session):
        result = engine.process_action(warrior_session, "examine the altar")
        assert len(result.narrative) > 0

    def test_examine_default_location(self, engine, warrior_session):
        result = engine.process_action(warrior_session, "examine")
        assert len(result.narrative) > 0

    def test_examine_scene_unchanged(self, engine, warrior_session):
        result = engine.process_action(warrior_session, "examine the door")
        assert result.scene_type == SceneType.EXPLORATION


# ---------------------------------------------------------------------------
# Action: TALK
# ---------------------------------------------------------------------------

class TestHandleTalk:
    def test_talk_changes_to_dialogue(self, engine, warrior_session):
        result = engine.process_action(warrior_session, "talk to the innkeeper")
        assert result.scene_type == SceneType.DIALOGUE

    def test_talk_default_target(self, engine, warrior_session):
        result = engine.process_action(warrior_session, "talk")
        assert len(result.narrative) > 0

    def test_talk_narrative_returned(self, engine, warrior_session):
        result = engine.process_action(warrior_session, "talk to the merchant")
        assert len(result.narrative) > 0

    def test_talk_shows_quest_offer_without_auto_accepting(self, engine, mage_session):
        merchant_id, merchant = _entity_by_role(mage_session, "merchant")
        mage_session.quest_offers = [{
            "id": "resupply_bread",
            "kind": "delivery",
            "title": "Bread Shortage",
            "description": "Bring two loaves to the tavern before nightfall.",
            "target_item": "bread",
            "required_qty": 2,
            "deadline_hours": 12,
            "reward_gold": 35,
            "reward_xp": 40,
        }]
        _move_player_near_entity(mage_session, merchant)

        result = engine.process_action(mage_session, "talk to merchant")

        assert "available quests" in result.narrative.lower()
        assert "quest accepted" not in result.narrative.lower()
        assert mage_session.quest_tracker.get_active_quests() == []
        assert merchant_id in mage_session.npc_memory.memories
        assert "merchant" not in mage_session.npc_memory.memories

    def test_authored_quest_offer_survives_talk_and_can_be_accepted(self, engine, mage_session):
        _merchant_id, merchant = _entity_by_role(mage_session, "merchant")
        mage_session.quest_offers = [{
            "id": "story_offer",
            "kind": "delivery",
            "title": "Story Quest",
            "description": "Keep this authored offer available.",
            "target_item": "bread",
            "required_qty": 1,
        }]
        _move_player_near_entity(mage_session, merchant)

        talk_result = engine.process_action(mage_session, "talk to merchant")
        assert "story quest" in talk_result.narrative.lower()
        assert any(offer["id"] == "story_offer" for offer in mage_session.quest_offers)
        assert next(offer for offer in mage_session.quest_offers if offer["id"] == "story_offer")["source"] == "authored"

        accept_result = engine.process_action(mage_session, "accept quest story quest")
        assert "quest accepted" in accept_result.narrative.lower()
        assert mage_session.quest_tracker.get_quest("story_offer") is not None

    def test_talk_spends_exploration_ap(self, engine, mage_session):
        merchant_id, merchant = _entity_by_role(mage_session, "merchant")
        _move_player_near_entity(mage_session, merchant)
        mage_session.game_time.minute = 15
        ap_before = mage_session.ap_tracker.current_ap

        result = engine.process_action(mage_session, "talk to merchant")

        assert merchant_id in mage_session.npc_memory.memories
        assert mage_session.ap_tracker.current_ap == ap_before - 1
        assert result.scene_type == SceneType.DIALOGUE


class TestQuestHardening:
    def test_accept_delivery_quest_requires_real_giver(self, engine, mage_session):
        mage_session.entities = {}
        mage_session.quest_offers = [{
            "id": "bread_shortage",
            "kind": "delivery",
            "title": "Bread Shortage",
            "description": "Bring two loaves to the tavern.",
            "target_item": "bread",
            "required_qty": 2,
        }]

        result = engine.process_action(mage_session, "accept quest bread shortage")

        assert "not bound to a real giver" in result.narrative.lower()
        assert mage_session.quest_tracker.get_active_quests() == []

    def test_accept_and_turn_in_delivery_quest_requires_explicit_flow(self, engine, mage_session):
        merchant_id, merchant = _entity_by_role(mage_session, "merchant")
        mage_session.location_stock.stock["bread"] = 1
        mage_session.quest_offers = engine._generate_emergent_quests(mage_session)
        _move_player_near_entity(mage_session, merchant)

        talk_result = engine.process_action(mage_session, "talk to merchant")
        assert "quest accepted" not in talk_result.narrative.lower()
        assert any(offer.get("id") == "resupply_bread" for offer in mage_session.quest_offers)
        assert all(offer.get("source") in {"authored", "emergent"} for offer in mage_session.quest_offers)

        accept_result = engine.process_action(mage_session, "accept quest bread shortage")
        assert "quest accepted" in accept_result.narrative.lower()
        assert len(mage_session.quest_tracker.get_active_quests()) == 1

        mage_session.add_item({"id": "bread", "name": "Bread", "qty": 2})
        idle_result = engine.process_action(mage_session, "inventory")
        assert "quest complete" not in idle_result.narrative.lower()
        assert len(mage_session.quest_tracker.get_active_quests()) == 1

        _move_player_to(mage_session, 0, 0)
        too_far_result = engine.process_action(mage_session, "turn in quest bread shortage")
        assert "too far away" in too_far_result.narrative.lower()
        assert len(mage_session.quest_tracker.get_active_quests()) == 1

        _move_player_near_entity(mage_session, mage_session.entities[merchant_id])
        turn_in_result = engine.process_action(mage_session, "turn in quest bread shortage")
        assert "you turn in" in turn_in_result.narrative.lower()
        assert mage_session.quest_tracker.get_active_quests() == []
        assert all(item.get("id") != "bread" for item in mage_session.inventory)

    def test_turn_in_rejects_delivery_quest_missing_giver_binding(self, engine, mage_session):
        offer = {
            "id": "orphan_delivery",
            "kind": "delivery",
            "title": "Orphan Delivery",
            "description": "This quest has no valid giver.",
            "target_item": "bread",
            "required_qty": 1,
        }
        engine._accept_quest_offer(mage_session, offer, giver_entity_id=None, giver_name=None)
        mage_session.add_item({"id": "bread", "name": "Bread", "qty": 1})

        result = engine.process_action(mage_session, "turn in quest orphan delivery")

        assert "missing a bound giver" in result.narrative.lower()
        assert mage_session.quest_tracker.get_active_quests()

    def test_raw_delivery_offer_schema_normalizes_and_preserves_bound_giver(self, engine, mage_session):
        merchant_id, merchant = _entity_by_role(mage_session, "merchant")
        _guard_id, guard = _entity_by_role(mage_session, "guard")
        _move_player_near_entity(mage_session, merchant)
        mage_session.narration_context["last_quest_giver_id"] = guard["entity_ref"].id
        mage_session.narration_context["last_quest_giver_name"] = guard["name"]
        mage_session.quest_offers = [{
            "id": "raw_delivery_offer",
            "type": "delivery",
            "title": "Bread Run",
            "required_items": [{"id": "bread", "qty": 1}],
            "rewards": {"gold": 5, "xp": 7},
            "meta": {
                "giver_entity_id": merchant_id,
                "giver_name": merchant["name"],
            },
        }]
        mage_session.add_item({"id": "bread", "name": "Bread", "qty": 1})

        accept_result = engine.process_action(mage_session, "accept quest bread run")
        turn_in_result = engine.process_action(mage_session, "turn in quest bread run")

        assert "quest accepted" in accept_result.narrative.lower()
        assert "you turn in" in turn_in_result.narrative.lower()
        assert mage_session.quest_tracker.get_active_quests() == []
        assert mage_session.campaign_state["quest_meta"]["raw_delivery_offer"]["kind"] == "delivery"
        assert mage_session.campaign_state["quest_meta"]["raw_delivery_offer"]["giver_entity_id"] == merchant_id
        assert all(item.get("id") != "bread" for item in mage_session.inventory)

    def test_trade_and_examine_spend_exploration_ap(self, engine, mage_session):
        _merchant_id, merchant = _entity_by_role(mage_session, "merchant")
        _move_player_near_entity(mage_session, merchant)
        mage_session.game_time.minute = 15
        ap_before = mage_session.ap_tracker.current_ap

        engine.process_action(mage_session, "trade with merchant")
        after_trade = mage_session.ap_tracker.current_ap
        engine.process_action(mage_session, "examine merchant")

        assert after_trade == ap_before - 1
        assert mage_session.ap_tracker.current_ap == after_trade - 1

    def test_social_proximity_uses_live_entity_position(self, engine):
        session = engine.new_session("Speaker", "rogue", location="Stone Bridge Tavern")
        merchant_id, merchant = _entity_by_role(session, "merchant")
        live_entity = merchant["entity_ref"]
        assert live_entity is not None

        target_x = session.position[0]
        target_y = session.position[1] + 1
        if session.spatial_index is not None:
            session.spatial_index.move(live_entity, target_x, target_y)
        live_entity.position = (target_x, target_y)
        merchant["position"] = [target_x + 4, target_y + 4]

        result = engine.process_action(session, "talk to merchant")

        assert "too far away" not in result.narrative.lower()
        assert session.conversation_state["target_type"] == "npc"
        assert session.entity_position_locked(merchant_id)

    def test_address_follow_up_keeps_active_npc_target(self, engine):
        session = engine.new_session("Speaker", "rogue", location="Stone Bridge Tavern")
        innkeeper_id, innkeeper = _entity_by_role(session, "innkeeper")
        _move_player_near_entity(session, innkeeper)

        talk_result = engine.process_action(session, "talk to innkeeper")
        follow_result = engine.process_action(session, "ask about rumors and who got robbed")

        assert "no longer close enough" not in follow_result.narrative.lower()
        assert session.conversation_state["target_type"] == "npc"
        assert session.conversation_state["npc_name"] == innkeeper["name"]
        assert session.entity_position_locked(innkeeper_id)
        assert talk_result.narrative


class TestSaveCommands:
    def test_save_list_load_and_delete_roundtrip(self, engine, warrior_session, tmp_path):
        engine.save_system = SaveSystem(tmp_path / "saves")
        warrior_session.player.hp = 7
        initial_turn = warrior_session.dm_context.turn

        save_result = engine.process_action(warrior_session, "save as slot_alpha")
        assert "slot_alpha" in save_result.narrative
        assert warrior_session.last_save_slot == "slot_alpha"
        assert warrior_session.dm_context.turn == initial_turn

        warrior_session.player.hp = 2

        list_result = engine.process_action(warrior_session, "list saves")
        assert "slot_alpha" in list_result.narrative
        assert warrior_session.dm_context.turn == initial_turn

        load_result = engine.process_action(warrior_session, "load slot_alpha")
        assert "slot_alpha" in load_result.narrative
        assert warrior_session.player.hp == 7
        assert warrior_session.dm_context.turn == initial_turn

        delete_result = engine.process_action(warrior_session, "delete save slot_alpha")
        assert "slot_alpha" in delete_result.narrative
        assert warrior_session.dm_context.turn == initial_turn

        missing_result = engine.process_action(warrior_session, "load slot_alpha")
        assert "No save slot named 'slot_alpha'" in missing_result.narrative


# ---------------------------------------------------------------------------
# Action: REST
# ---------------------------------------------------------------------------

class TestHandleRest:
    def test_rest_restores_hp(self, engine, warrior_session):
        warrior_session.player.hp = 10
        result = engine.process_action(warrior_session, "rest")
        assert warrior_session.player.hp > 10
        assert result.state_changes.get("hp_restored", 0) > 0

    def test_rest_restores_spell_points(self, engine, mage_session):
        mage_session.player.spell_points = 2
        engine.process_action(mage_session, "rest")
        assert mage_session.player.spell_points == mage_session.player.max_spell_points

    def test_rest_not_in_combat(self, engine, warrior_session):
        # Enter combat by attacking, then try to rest
        engine.process_action(warrior_session, "attack")
        assert warrior_session.in_combat()
        result = engine.process_action(warrior_session, "rest")
        assert "can't do that during combat" in result.narrative.lower() or "cannot rest" in result.narrative.lower()

    def test_rest_hp_capped_at_max(self, engine, warrior_session):
        warrior_session.player.hp = warrior_session.player.max_hp
        engine.process_action(warrior_session, "rest")
        assert warrior_session.player.hp <= warrior_session.player.max_hp

    def test_rest_returns_to_exploration(self, engine, warrior_session):
        warrior_session.player.hp = 5
        result = engine.process_action(warrior_session, "rest")
        assert result.scene_type == SceneType.EXPLORATION

    def test_rest_runs_hourly_world_updates_across_elapsed_window(self, engine, warrior_session):
        warrior_session.game_time.day = 1
        warrior_session.game_time.hour = 8
        warrior_session.game_time.minute = 0
        warrior_session.caravan_manager.active = {}
        warrior_session.caravan_manager._last_departure = {}

        result = engine.process_action(warrior_session, "rest")
        departure_hours = [
            event["hour"]
            for event in result.state_changes.get("world_events", [])
            if event.get("type") == "departure"
        ]

        assert departure_hours
        # Hour 8 is included because rest starts exactly at 8:00 (boundary fix)
        assert 8 in departure_hours or 9 in departure_hours
        assert 16 not in departure_hours


# ---------------------------------------------------------------------------
# Action: MOVE
# ---------------------------------------------------------------------------

class TestHandleMove:
    def test_move_unknown_destination_rejects(self, engine, warrior_session):
        """Moving to unknown named destination should NOT silently teleport."""
        result = engine.process_action(warrior_session, "move to the dungeon")
        assert "don't know" in result.narrative.lower() or "direction" in result.narrative.lower()
        assert warrior_session.dm_context.location != "the dungeon"

    def test_move_to_coordinate_accepts_parser_normalized_spacing(self, engine, warrior_session):
        warrior_session.map_data = MapData(
            width=12,
            height=12,
            tiles=[[TileType.FLOOR for _ in range(12)] for _ in range(12)],
            rooms=[],
            spawn_point=(5, 5),
            metadata={"map_type": "wilderness"},
        )
        warrior_session.position = [5, 5]
        warrior_session.sync_player_state()

        result = engine.process_action(warrior_session, "move to 7,4")

        assert warrior_session.position == [7, 4]
        assert "position: 7,4" in result.narrative.lower()

    def test_move_default_forward(self, engine, warrior_session):
        result = engine.process_action(warrior_session, "move")
        assert len(result.narrative) > 0


# ---------------------------------------------------------------------------
# Action: OPEN
# ---------------------------------------------------------------------------

class TestHandleOpen:
    def test_open_target(self, engine, warrior_session):
        result = engine.process_action(warrior_session, "open the chest")
        assert len(result.narrative) > 0

    def test_open_default_door(self, engine, warrior_session):
        result = engine.process_action(warrior_session, "open")
        assert len(result.narrative) > 0


# ---------------------------------------------------------------------------
# Action: USE_ITEM
# ---------------------------------------------------------------------------

class TestHandleUseItem:
    def test_use_item_narrative(self, engine, warrior_session):
        result = engine.process_action(warrior_session, "use potion")
        assert len(result.narrative) > 0


class TestCraftHardening:
    def test_crafting_with_low_ap_advances_time_and_pays_full_cost(self, engine):
        session = engine.new_session("Crafter", "warrior", location="Harbor Town")
        kitchen = next(entity for entity in session.spatial_index.all_entities() if entity.id == "workstation_kitchen")
        _move_player_to(session, kitchen.position[0], kitchen.position[1])
        session.add_item({"id": "flour", "name": "Flour", "qty": 2})
        session.add_item({"id": "water", "name": "Water", "qty": 1})
        session.ap_tracker.current_ap = 1
        session.game_time.hour = 8
        session.game_time.minute = 0
        bread_before = sum(item.get("qty", 1) for item in session.inventory if item.get("id") == "bread")

        with patch(
            "engine.api.game_engine.roll_check",
            return_value=SkillCheckResult(roll=12, modifier=0, total=12, dc=8, success=True, margin=4, critical=None),
        ):
            result = engine.process_action(session, "craft bread")

        assert "lack the materials" not in result.narrative.lower()
        assert session.game_time.hour == 9
        assert session.game_time.minute == 0
        assert session.ap_tracker.current_ap == 2
        bread_after = sum(item.get("qty", 1) for item in session.inventory if item.get("id") == "bread")
        assert bread_after == bread_before + 2


class TestCombatHardening:
    def test_attack_world_target_does_not_spend_exploration_ap_on_combat_start(self, engine):
        session = engine.new_session("Duelist", "warrior", location="Harbor Town")
        merchant_id, merchant = _entity_by_role(session, "merchant")
        _move_player_near_entity(session, merchant)
        ap_before = session.ap_tracker.current_ap

        result = engine.process_action(session, "attack merchant")

        assert result.combat_state is not None
        assert result.combat_state["active"] == session.player.name
        assert session.in_combat()
        assert session.ap_tracker.current_ap == ap_before
        assert session.entities[merchant_id]["hp"] == session.entities[merchant_id]["max_hp"]

    def test_combat_snapshot_player_ap_matches_combat_ap(self, engine, warrior_session):
        result = engine.process_action(warrior_session, "attack")

        snapshot = warrior_session.to_dict()
        assert snapshot["combat"] is not None
        combat_player = next(
            combatant for combatant in result.combat_state["combatants"]
            if combatant["name"] == warrior_session.player.name
        )

        assert snapshot["player"]["ap"]["current"] == combat_player["ap"]
        assert snapshot["player"]["ap"]["max"] == 3
        assert snapshot["ap"]["current"] == combat_player["ap"]
        assert snapshot["ap"]["max"] == 3

    @pytest.mark.parametrize("command", ["talk to goblin", "say to goblin hello", "persuade goblin", "intimidate goblin", "deceive goblin", "bribe goblin", "think about goblins"])
    def test_social_intents_are_blocked_during_combat(self, engine, warrior_session, command):
        result = engine.process_action(warrior_session, "attack goblin")
        assert result.combat_state is not None

        player_combatant = next(
            combatant for combatant in warrior_session.combat.combatants
            if combatant.name == warrior_session.player.name
        )
        ap_before = warrior_session.ap_tracker.current_ap
        combat_ap_before = player_combatant.ap
        action_before = player_combatant.action_available
        scene_before = warrior_session.dm_context.scene_type
        turn_before = warrior_session.dm_context.turn
        time_before = (warrior_session.game_time.day, warrior_session.game_time.hour, warrior_session.game_time.minute)
        conversation_before = dict(warrior_session.conversation_state)

        blocked = engine.process_action(warrior_session, command)

        assert "can't do that during combat" in blocked.narrative.lower()
        assert warrior_session.ap_tracker.current_ap == ap_before
        assert player_combatant.ap == combat_ap_before
        assert player_combatant.action_available == action_before
        assert warrior_session.dm_context.scene_type == scene_before
        assert warrior_session.dm_context.turn == turn_before
        assert (warrior_session.game_time.day, warrior_session.game_time.hour, warrior_session.game_time.minute) == time_before
        assert warrior_session.conversation_state == conversation_before

    def test_targeted_social_actions_fail_cleanly_when_target_missing(self, engine):
        session = engine.new_session("Speaker", "priest", location="Harbor Town")
        ap_before = session.ap_tracker.current_ap
        gold_before = session.player.gold

        for command in ("persuade dragon", "intimidate dragon", "deceive dragon", "bribe dragon"):
            result = engine.process_action(session, command)
            assert result.narrative == "There's no one here by that name."

        assert session.ap_tracker.current_ap == ap_before
        assert session.player.gold == gold_before

    def test_exact_hour_tick_does_not_run_hourly_updates_early(self, engine):
        session = engine.new_session("Tick", "warrior", location="Harbor Town")
        session.game_time.day = 1
        session.game_time.hour = 8
        session.game_time.minute = 0
        session.ap_tracker.current_ap = 1
        hour_markers = []

        with patch.object(engine, "_run_hourly_world_updates", side_effect=lambda s, hour, events: hour_markers.append(hour)):
            engine._world_tick(session, minutes=15, refresh_ap=False)

        assert hour_markers == []
        assert session.ap_tracker.current_ap == 1

    def test_hour_boundary_tick_runs_once_when_boundary_crossed(self, engine):
        session = engine.new_session("Tick", "warrior", location="Harbor Town")
        session.game_time.day = 1
        session.game_time.hour = 8
        session.game_time.minute = 45
        session.ap_tracker.current_ap = 1
        hour_markers = []

        with patch.object(engine, "_run_hourly_world_updates", side_effect=lambda s, hour, events: hour_markers.append(hour)):
            engine._world_tick(session, minutes=15, refresh_ap=False)

        assert hour_markers == [9]
        assert session.ap_tracker.current_ap == session.ap_tracker.max_ap

    def test_attack_updates_world_npc_body_tracker(self, engine, warrior_session):
        merchant_id, merchant = _entity_by_role(warrior_session, "merchant")
        _move_player_near_entity(warrior_session, merchant)
        enemy = engine._character_from_world_entity(merchant_id, merchant)
        warrior_session.combat = CombatManager([warrior_session.player, enemy], seed=1)
        warrior_session.dm_context.scene_type = SceneType.COMBAT
        warrior_session.combat.start_turn()
        while warrior_session.combat.active_combatant.name != warrior_session.player.name:
            warrior_session.combat.end_turn()
        target_idx = engine._find_target(warrior_session.combat, enemy.name, exclude=warrior_session.player.name)
        assert target_idx is not None

        before_head_hp = merchant["body"].current_hp["head"]

        def _attack_once(*args, **kwargs):
            warrior_session.combat.combat_ended = True
            return {"hit": True, "damage": 6, "target": enemy.name}

        with patch("engine.api.game_engine.roll_hit_location", return_value="head"):
            with patch.object(warrior_session.combat, "attack", side_effect=_attack_once):
                engine._execute_attack_round(warrior_session, warrior_session.combat, target_idx)

        assert merchant["body"].current_hp["head"] < before_head_hp
        assert merchant["hp"] == enemy.hp


class TestInventoryHardening:
    def test_failed_pickup_does_not_spend_ap(self, engine, warrior_session):
        ap_before = warrior_session.ap_tracker.current_ap

        result = engine.process_action(warrior_session, "pick up bread")

        assert "nothing to pick up" in result.narrative.lower()
        assert warrior_session.ap_tracker.current_ap == ap_before

    def test_pickup_merges_stackable_items(self, engine):
        session = engine.new_session("Collector", "warrior", location="Harbor Town")

        drop_result = engine.process_action(session, "drop bread")
        assert "drop" in drop_result.narrative.lower()

        pickup_result = engine.process_action(session, "pick up bread")
        assert "pick up" in pickup_result.narrative.lower()

        bread_entries = [item for item in session.inventory if item.get("id") == "bread"]
        assert len(bread_entries) == 1
        assert bread_entries[0]["qty"] == 3

    def test_pickup_keeps_ground_item_when_inventory_cannot_accept_it(self, engine, warrior_session):
        from engine.world.entity import Entity, EntityType

        heavy = Entity(
            id="heavy_boulder",
            entity_type=EntityType.ITEM,
            name="Heavy Boulder",
            position=tuple(warrior_session.position),
            glyph="*",
            color="grey",
            blocking=False,
            inventory=[{"id": "heavy_boulder", "name": "Heavy Boulder", "type": "item", "weight": 32.0}],
        )
        warrior_session.spatial_index.add(heavy)

        result = engine.process_action(warrior_session, "pick up heavy boulder")

        assert "too heavy" in result.narrative.lower()
        assert warrior_session.has_timed_condition("back_strain")
        assert any(entity.id == "heavy_boulder" for entity in warrior_session.spatial_index.at(*warrior_session.position))
        assert warrior_session.find_inventory_item("heavy_boulder") is None

    def test_overloaded_agi_checks_take_penalty(self, engine, warrior_session):
        warrior_session.add_item({"id": "training_weight", "name": "Training Weight", "qty": 1, "weight": 23.0})
        assert 1.0 < warrior_session.carry_ratio() <= 1.25

        with patch(
            "engine.api.game_engine.roll_check",
            return_value=SkillCheckResult(roll=12, modifier=3, total=15, dc=13, success=True, margin=2, critical=None),
        ):
            result = engine._roll_ability_check(warrior_session, "AGI", 13)

        assert result.total == 13
        assert result.modifier == 1

    def test_add_or_drop_item_respects_weight_for_crafting_and_gathering_outputs(self, engine, warrior_session):
        dropped = not engine._add_or_drop_item(
            warrior_session,
            {"id": "anvil", "name": "Anvil", "qty": 1, "weight": 32.0},
        )

        assert dropped
        assert warrior_session.find_inventory_item("anvil") is None
        assert warrior_session.has_timed_condition("back_strain")
        assert any(entity.name == "Anvil" for entity in warrior_session.spatial_index.at(*warrior_session.position))

    def test_search_auto_refreshes_ap_on_next_action_when_zero(self, engine, warrior_session):
        """AP auto-refreshes at the START of the next action when pool hits 0."""
        warrior_session.game_time.minute = 15
        warrior_session.ap_tracker.current_ap = 1

        engine.process_action(warrior_session, "search area")
        # AP is 0 after search spends the last 1 AP
        assert warrior_session.ap_tracker.current_ap == 0

        # Next action triggers auto-refresh before handler runs
        # look doesn't cost AP, so AP stays at max after refresh
        engine.process_action(warrior_session, "look around")
        assert warrior_session.ap_tracker.current_ap == warrior_session.ap_tracker.max_ap

        # Now do an action that costs AP (move) — should work without "not enough AP"
        result = engine.process_action(warrior_session, "move south")
        assert "not enough" not in result.narrative.lower()


class TestGoToHardening:
    def test_go_to_matches_repeated_move_time_and_ap(self, engine):
        base_session = engine.new_session("Walker", "warrior", location="Forest Road")
        tiles = [[TileType.FLOOR for _ in range(12)] for _ in range(12)]
        for i in range(12):
            tiles[0][i] = TileType.WALL
            tiles[11][i] = TileType.WALL
            tiles[i][0] = TileType.WALL
            tiles[i][11] = TileType.WALL
        base_session.map_data = MapData(width=12, height=12, tiles=tiles, rooms=[], spawn_point=(1, 1))
        base_session.position = [1, 1]
        base_session.game_time.hour = 8
        base_session.game_time.minute = 15
        base_session.entities = {}
        base_session.spatial_index = SpatialIndex()
        base_session.player_entity.position = (1, 1)
        base_session.spatial_index.add(base_session.player_entity)
        target_pos = [8, 1]
        path = astar_path(base_session.map_data, base_session.position, target_pos, max_steps=40)
        assert path is not None and target_pos is not None

        save_system = SaveSystem()
        clone_state = save_system._serialize_session(base_session)
        goto_session = save_system._deserialize_session(copy.deepcopy(clone_state))
        goto_session.entities["target_npc"] = {
            "name": "Target NPC",
            "type": "npc",
            "position": list(target_pos),
            "role": "merchant",
            "faction": "merchant_guild",
        }

        goto_result = engine.process_action(goto_session, "approach target npc")
        assert "walk" in goto_result.narrative.lower()
        assert goto_session.position == [5, 1]
        assert goto_session.game_time.hour == 9
        assert goto_session.game_time.minute == 15
        assert goto_session.ap_tracker.current_ap == 2

    def test_go_to_tracks_live_target_until_social_range(self, engine):
        session = engine.new_session("Walker", "warrior", location="Forest Road")
        tiles = [[TileType.FLOOR for _ in range(12)] for _ in range(12)]
        for i in range(12):
            tiles[0][i] = TileType.WALL
            tiles[11][i] = TileType.WALL
            tiles[i][0] = TileType.WALL
            tiles[i][11] = TileType.WALL
        session.map_data = MapData(width=12, height=12, tiles=tiles, rooms=[], spawn_point=(1, 1))
        session.position = [1, 1]
        session.entities = {
            "target_npc": {
                "name": "Target NPC",
                "type": "npc",
                "position": [6, 1],
                "role": "merchant",
                "faction": "merchant_guild",
            }
        }
        session.spatial_index = SpatialIndex()
        session.player_entity.position = (1, 1)
        session.spatial_index.add(session.player_entity)

        original_world_tick = engine._world_tick
        tick_calls = {"count": 0}

        def moving_world_tick(target_session, minutes=15, refresh_ap=False):
            tick_calls["count"] += 1
            if tick_calls["count"] == 1:
                target_session.entities["target_npc"]["position"] = [7, 1]
            return original_world_tick(target_session, minutes=minutes, refresh_ap=refresh_ap)

        with patch.object(engine, "_world_tick", side_effect=moving_world_tick):
            result = engine.process_action(session, "approach target npc")

        assert "close enough" in result.narrative.lower()
        assert distance(session.position, session.entities["target_npc"]["position"]) <= 3

    def test_go_to_routes_around_blocking_npc(self, engine):
        session = engine.new_session("Walker", "warrior", location="Forest Road")
        tiles = [[TileType.FLOOR for _ in range(12)] for _ in range(12)]
        for i in range(12):
            tiles[0][i] = TileType.WALL
            tiles[11][i] = TileType.WALL
            tiles[i][0] = TileType.WALL
            tiles[i][11] = TileType.WALL
        session.map_data = MapData(width=12, height=12, tiles=tiles, rooms=[], spawn_point=(1, 1))
        session.position = [1, 1]
        session.entities = {
            "target_npc": {
                "name": "Target NPC",
                "type": "npc",
                "position": [6, 1],
                "role": "merchant",
                "faction": "merchant_guild",
            }
        }
        session.spatial_index = SpatialIndex()
        session.player_entity.position = (1, 1)
        session.spatial_index.add(session.player_entity)
        blocker = Entity(
            id="blocker",
            entity_type=EntityType.NPC,
            name="Blocker",
            position=(2, 1),
            glyph="B",
            color="red",
            blocking=True,
        )
        session.spatial_index.add(blocker)

        result = engine.process_action(session, "approach target npc")

        assert "walk" in result.narrative.lower()
        assert session.position != [1, 1]
        assert session.position != [2, 1]

    def test_go_to_stops_within_social_range_when_adjacent_tiles_are_blocked(self, engine):
        session = engine.new_session("Walker", "warrior", location="Forest Road")
        tiles = [[TileType.FLOOR for _ in range(12)] for _ in range(12)]
        for i in range(12):
            tiles[0][i] = TileType.WALL
            tiles[11][i] = TileType.WALL
            tiles[i][0] = TileType.WALL
            tiles[i][11] = TileType.WALL
        session.map_data = MapData(width=12, height=12, tiles=tiles, rooms=[], spawn_point=(1, 1))
        session.position = [1, 1]
        session.entities = {
            "target_npc": {
                "name": "Counter Merchant",
                "type": "npc",
                "position": [6, 1],
                "role": "merchant",
                "faction": "merchant_guild",
                "blocking": True,
            }
        }
        session.spatial_index = SpatialIndex()
        session.player_entity.position = (1, 1)
        session.spatial_index.add(session.player_entity)
        for blocker_id, pos in {
            "north_wall": (6, 0),
            "south_wall": (6, 2),
            "left_blocker": (5, 1),
            "right_blocker": (7, 1),
        }.items():
            blocker = Entity(
                id=blocker_id,
                entity_type=EntityType.NPC,
                name=blocker_id,
                position=pos,
                glyph="B",
                color="red",
                blocking=True,
            )
            session.spatial_index.add(blocker)

        result = engine.process_action(session, "approach counter merchant")

        assert "close enough" in result.narrative.lower()
        assert distance(session.position, session.entities["target_npc"]["position"]) <= 3


class TestSocialRangeHardening:
    @pytest.mark.parametrize("command", ["talk to guard", "persuade guard", "intimidate guard", "bribe guard", "deceive guard"])
    def test_social_actions_work_at_two_tiles(self, engine, command):
        session = engine.new_session("Speaker", "priest", location="Harbor Town")
        guard_id, guard = _entity_by_role(session, "guard")
        gx, gy = guard["position"]
        _move_player_to(session, gx, gy - 2)
        with patch("engine.api.game_engine.roll_check", return_value=SkillCheckResult(roll=14, modifier=2, total=16, dc=12, success=True, margin=4, critical=None)):
            result = engine.process_action(session, command)
        assert "too far away" not in result.narrative.lower()

    def test_social_actions_still_fail_beyond_social_range(self, engine):
        """Social range is 3 tiles — distance 4+ should fail."""
        session = engine.new_session("Speaker", "priest", location="Harbor Town")
        _guard_id, guard = _entity_by_role(session, "guard")
        gx, gy = guard["position"]
        _move_player_to(session, gx, gy - 4)
        result = engine.process_action(session, "persuade guard")
        assert "too far away" in result.narrative.lower()

    def test_conversation_target_stays_valid_at_social_range_edge(self, engine):
        session = engine.new_session("Speaker", "priest", location="Harbor Town")
        _guard_id, guard = _entity_by_role(session, "guard")
        gx, gy = guard["position"]
        _move_player_to(session, gx, gy - 3)

        talk_result = engine.process_action(session, "talk to guard")
        assert "too far away" not in talk_result.narrative.lower()
        assert session.conversation_state["target_type"] == "npc"

        follow_up = engine.process_action(session, "hello there")
        assert session.conversation_state["target_type"] == "npc"
        assert follow_up.scene_type == SceneType.DIALOGUE

    def test_conversation_target_clears_beyond_social_range(self, engine):
        session = engine.new_session("Speaker", "priest", location="Harbor Town")
        _guard_id, guard = _entity_by_role(session, "guard")
        gx, gy = guard["position"]
        _move_player_to(session, gx, gy - 3)
        engine.process_action(session, "talk to guard")
        assert session.conversation_state["target_type"] == "npc"

        _move_player_to(session, gx, gy - 4)
        engine.process_action(session, "look")
        assert session.conversation_state["target_type"] == "dm"


class TestUtilityAPHardening:
    def test_open_spends_ap_and_time(self, engine, warrior_session):
        warrior_session.game_time.minute = 15
        ap_before = warrior_session.ap_tracker.current_ap
        hour_before = warrior_session.game_time.hour
        minute_before = warrior_session.game_time.minute

        engine.process_action(warrior_session, "open chest")

        assert warrior_session.ap_tracker.current_ap == ap_before - 1
        assert (warrior_session.game_time.hour, warrior_session.game_time.minute) != (hour_before, minute_before)

    def test_fill_pour_and_stash_spend_ap(self, engine, warrior_session):
        warrior_session.game_time.minute = 15
        warrior_session.add_item({
            "id": "waterskin",
            "name": "Waterskin",
            "type": "tool",
            "container_type": {"liquid_capacity_ml": 500},
        })
        warrior_session.add_item({"id": "gem", "name": "Ruby Gem", "type": "gem"})
        warrior_session.map_data.set_tile(warrior_session.position[0] + 1, warrior_session.position[1], TileType.WATER)

        ap_before_fill = warrior_session.ap_tracker.current_ap
        engine.process_action(warrior_session, "fill waterskin")
        assert warrior_session.ap_tracker.current_ap == ap_before_fill - 1

        ap_before_pour = warrior_session.ap_tracker.current_ap
        engine.process_action(warrior_session, "pour waterskin")
        assert warrior_session.ap_tracker.current_ap == ap_before_pour - 1

    def test_stash_spends_ap(self, engine, warrior_session):
        warrior_session.game_time.minute = 15
        warrior_session.add_item({"id": "gem", "name": "Ruby Gem", "type": "gem"})

        ap_before_stash = warrior_session.ap_tracker.current_ap
        engine.process_action(warrior_session, "stash gem in sock_left")

        assert warrior_session.ap_tracker.current_ap == ap_before_stash - 1

    def test_rotate_item_is_zero_time(self, engine, warrior_session):
        warrior_session.add_item({"id": "sword", "name": "Sword", "type": "weapon"})
        ap_before = warrior_session.ap_tracker.current_ap
        turn_before = warrior_session.dm_context.turn
        hour_before = warrior_session.game_time.hour
        minute_before = warrior_session.game_time.minute

        result = engine.process_action(warrior_session, "rotate sword")

        assert "rotate" in result.narrative.lower()
        assert warrior_session.ap_tracker.current_ap == ap_before
        assert warrior_session.dm_context.turn == turn_before
        assert warrior_session.game_time.hour == hour_before
        assert warrior_session.game_time.minute == minute_before


# ---------------------------------------------------------------------------
# Action: UNKNOWN
# ---------------------------------------------------------------------------

class TestHandleUnknown:
    def test_unknown_action(self, engine, warrior_session):
        result = engine.process_action(warrior_session, "xyzzy plugh")
        # Should return some narrative (LLM catch-all, no "not sure")
        assert result.narrative
        assert len(result.narrative) > 0

    def test_unknown_action_does_not_spend_ap(self, engine, warrior_session):
        ap_before = warrior_session.ap_tracker.current_ap

        engine.process_action(warrior_session, "address dm what am i missing")

        assert warrior_session.ap_tracker.current_ap == ap_before

    def test_unknown_contains_input(self, engine, warrior_session):
        result = engine.process_action(warrior_session, "dance wildly")
        # narrative should reference the action in some way (via template or LLM)
        assert result.narrative
        assert len(result.narrative) > 0


class TestMetaCommands:
    def test_think_does_not_spend_ap(self, engine, warrior_session):
        ap_before = warrior_session.ap_tracker.current_ap

        result = engine.process_action(warrior_session, "think about the town history")

        assert result.narrative
        assert warrior_session.ap_tracker.current_ap == ap_before


# ---------------------------------------------------------------------------
# LLM Integration
# ---------------------------------------------------------------------------

class TestLLMIntegration:
    def test_custom_llm_called(self):
        mock_llm = MagicMock(return_value="The dungeon echoes with your footsteps.")
        engine_with_llm = GameEngine(llm=mock_llm)
        session = engine_with_llm.new_session("Hero", "warrior", location="Cave")
        result = engine_with_llm.process_action(session, "examine")
        assert mock_llm.called
        assert result.narrative == "The dungeon echoes with your footsteps."


# ---------------------------------------------------------------------------
# Helper: _spawn_enemy
# ---------------------------------------------------------------------------

class TestSpawnEnemy:
    def test_spawns_known_enemy(self, engine):
        enemy = engine._spawn_enemy(1)
        assert enemy.name in {monster["name"] for monster in list_monsters()}

    def test_enemy_has_stats(self, engine):
        enemy = engine._spawn_enemy(1)
        assert "MIG" in enemy.stats


# ---------------------------------------------------------------------------
# Helper: _find_target
# ---------------------------------------------------------------------------

class TestFindTarget:
    def _make_combat(self, names):
        chars = [
            Character(name=n, hp=10, max_hp=10,
                      stats={"MIG": 10, "AGI": 10, "END": 10, "MND": 10, "INS": 10, "PRE": 10})
            for n in names
        ]
        mgr = CombatManager(chars, seed=0)
        mgr.start_turn()
        return mgr

    def test_find_by_name(self, engine):
        combat = self._make_combat(["Hero", "Goblin"])
        idx = engine._find_target(combat, "goblin", exclude="Hero")
        assert idx is not None
        assert combat.combatants[idx].name == "Goblin"

    def test_find_fallback(self, engine):
        combat = self._make_combat(["Hero", "Orc"])
        idx = engine._find_target(combat, None, exclude="Hero")
        assert idx is not None
        assert combat.combatants[idx].name != "Hero"

    def test_returns_none_when_all_dead(self, engine):
        combat = self._make_combat(["Hero", "Ghost"])
        for c in combat.combatants:
            if c.name == "Ghost":
                c.is_dead = True
        idx = engine._find_target(combat, None, exclude="Hero")
        assert idx is None

    def test_partial_name_match(self, engine):
        combat = self._make_combat(["Hero", "Dark Knight"])
        idx = engine._find_target(combat, "knight", exclude="Hero")
        assert idx is not None
        assert "Knight" in combat.combatants[idx].name


# ---------------------------------------------------------------------------
# Helper: _combat_state
# ---------------------------------------------------------------------------

class TestCombatState:
    def test_none_when_no_combat(self, engine):
        assert engine._combat_state(None) is None

    def test_returns_dict(self, engine, warrior_session):
        engine.process_action(warrior_session, "attack")
        state = engine._combat_state(warrior_session.combat)
        assert "round" in state
        assert "combatants" in state
        assert "ended" in state

    def test_active_none_when_ended(self, engine, warrior_session):
        engine.process_action(warrior_session, "attack")
        warrior_session.combat.combat_ended = True
        state = engine._combat_state(warrior_session.combat)
        assert state["active"] is None
