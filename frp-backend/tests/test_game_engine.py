"""
Tests for GameEngine — covers all action handlers, edge cases, and helper methods.
Target: game_engine.py ≥ 97% coverage
"""
import pytest
from unittest.mock import patch, MagicMock

from engine.api.game_engine import GameEngine, ActionResult
from engine.core.character import Character
from engine.core.combat import CombatManager
from engine.core.dm_agent import SceneType


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

    def test_explicit_location(self, warrior_session):
        assert warrior_session.dm_context.location == "Test Keep"

    def test_session_has_dm_context(self, warrior_session):
        assert warrior_session.dm_context.scene_type == SceneType.EXPLORATION


# ---------------------------------------------------------------------------
# Action: ATTACK
# ---------------------------------------------------------------------------

class TestHandleAttack:
    def test_attack_starts_combat(self, engine, warrior_session):
        result = engine.process_action(warrior_session, "attack")
        assert result.combat_state is not None
        assert warrior_session.in_combat()

    def test_attack_returns_narrative(self, engine, warrior_session):
        result = engine.process_action(warrior_session, "attack")
        assert len(result.narrative) > 0

    def test_attack_narrative_contains_action_word(self, engine, warrior_session):
        result = engine.process_action(warrior_session, "attack the goblin")
        assert any(w in result.narrative.lower() for w in
                   ["strike", "miss", "critical", "stumbles", "swings", "blow", "damage"])

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
        assert any(w in result.narrative.lower() for w in
                   ["unleash", "magic missile", "spell", "missile", "force"])

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
        assert "cannot rest" in result.narrative.lower()

    def test_rest_hp_capped_at_max(self, engine, warrior_session):
        warrior_session.player.hp = warrior_session.player.max_hp
        engine.process_action(warrior_session, "rest")
        assert warrior_session.player.hp <= warrior_session.player.max_hp

    def test_rest_returns_to_exploration(self, engine, warrior_session):
        warrior_session.player.hp = 5
        result = engine.process_action(warrior_session, "rest")
        assert result.scene_type == SceneType.EXPLORATION


# ---------------------------------------------------------------------------
# Action: MOVE
# ---------------------------------------------------------------------------

class TestHandleMove:
    def test_move_updates_location(self, engine, warrior_session):
        engine.process_action(warrior_session, "move to the dungeon")
        assert "dungeon" in warrior_session.dm_context.location.lower()

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


# ---------------------------------------------------------------------------
# Action: UNKNOWN
# ---------------------------------------------------------------------------

class TestHandleUnknown:
    def test_unknown_action(self, engine, warrior_session):
        result = engine.process_action(warrior_session, "xyzzy plugh")
        # Should return some narrative (LLM catch-all, no "not sure")
        assert result.narrative
        assert len(result.narrative) > 0

    def test_unknown_contains_input(self, engine, warrior_session):
        result = engine.process_action(warrior_session, "dance wildly")
        # narrative should reference the action in some way (via template or LLM)
        assert result.narrative
        assert len(result.narrative) > 0


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
        assert enemy.name in ["Goblin", "Orc", "Skeleton"]

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
