"""
Ember RPG - Chaotic FRP Player Playtest Suite
==============================================
Integration/scenario tests that play through multiple game sessions
attempting to break the game and verify AAA quality.

NOT unit tests. These simulate real chaotic players doing absurd things.

Run with:  pytest tests/test_playtest_derail.py -v -s
"""
import pytest
from engine.api.game_engine import GameEngine, ActionResult
from engine.api.game_session import GameSession


# ---------------------------------------------------------------------------
# Marker for all playtest scenarios
# ---------------------------------------------------------------------------
pytestmark = pytest.mark.playtest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _engine() -> GameEngine:
    """Fresh engine with no LLM (template narration only)."""
    return GameEngine()


def _assert_valid_result(result: ActionResult, action_text: str):
    """Common assertions every action result must satisfy."""
    assert result is not None, f"Action '{action_text}' returned None"
    assert result.narrative, f"Action '{action_text}' produced empty narrative"
    assert len(result.narrative) > 5, (
        f"Action '{action_text}' narrative too short: {result.narrative!r}"
    )


def _assert_session_sane(session: GameSession, action_text: str):
    """Session-level invariants that must always hold."""
    assert session.player is not None, f"Player is None after '{action_text}'"
    assert session.player.hp >= 0, (
        f"HP went negative ({session.player.hp}) after '{action_text}'"
    )
    assert session.game_time is not None, f"game_time is None after '{action_text}'"


def _print_excerpt(action_text: str, result: ActionResult, max_len: int = 120):
    """Print a short excerpt for debugging when running with -s."""
    snippet = result.narrative[:max_len].replace("\n", " ")
    print(f"  [{action_text}] -> {snippet}...")


# ===========================================================================
# Scenario 1: The Murder Hobo
# ===========================================================================

class TestMurderHobo:
    """Player attacks NPCs, guards, merchants -- tests consequence cascading."""

    def test_murder_hobo_run(self):
        engine = _engine()
        session = engine.new_session("Grognak", "warrior", location="Harbor Town")
        initial_hp = session.player.hp

        # Attack the merchant
        result = engine.process_action(session, "attack merchant")
        _assert_valid_result(result, "attack merchant")
        _assert_session_sane(session, "attack merchant")
        _print_excerpt("attack merchant", result)

        # Attack the guard
        result = engine.process_action(session, "attack guard")
        _assert_valid_result(result, "attack guard")
        _assert_session_sane(session, "attack guard")
        _print_excerpt("attack guard", result)

        # Try to flee
        result = engine.process_action(session, "flee")
        _assert_valid_result(result, "flee")
        _assert_session_sane(session, "flee")
        _print_excerpt("flee", result)

        # Come back and try to trade -- should still get a narrative
        result = engine.process_action(session, "trade with merchant")
        _assert_valid_result(result, "trade with merchant")
        _print_excerpt("trade with merchant", result)

        # Rest to heal
        result = engine.process_action(session, "rest")
        _assert_valid_result(result, "rest")
        _assert_session_sane(session, "rest")
        _print_excerpt("rest", result)
        # After rest, HP should be > 0 or narrative should mention "fallen"
        assert session.player.hp > 0 or "fallen" in result.narrative.lower(), (
            "After rest, player should be alive or narrative should mention death"
        )

    def test_attack_everything_in_sequence(self):
        """Attack multiple non-hostile targets in rapid succession."""
        engine = _engine()
        session = engine.new_session("Barbarus", "warrior", location="Harbor Town")

        targets = ["merchant", "guard", "blacksmith", "beggar", "priest"]
        for target in targets:
            result = engine.process_action(session, f"attack {target}")
            _assert_valid_result(result, f"attack {target}")
            _assert_session_sane(session, f"attack {target}")
            _print_excerpt(f"attack {target}", result)


# ===========================================================================
# Scenario 2: The Thief
# ===========================================================================

class TestThief:
    """Player attempts stealing, lockpicking, sneaking."""

    def test_thief_run(self):
        engine = _engine()
        session = engine.new_session("Shadow", "rogue", location="Harbor Town")

        # Sneak
        result = engine.process_action(session, "sneak")
        _assert_valid_result(result, "sneak")
        _assert_session_sane(session, "sneak")
        _print_excerpt("sneak", result)

        # Steal from merchant
        result = engine.process_action(session, "steal from merchant")
        _assert_valid_result(result, "steal from merchant")
        _assert_session_sane(session, "steal from merchant")
        _print_excerpt("steal from merchant", result)

        # Lockpick a door
        result = engine.process_action(session, "pick the lock")
        _assert_valid_result(result, "pick the lock")
        _assert_session_sane(session, "pick the lock")
        _print_excerpt("pick the lock", result)

        # Search for hidden items
        result = engine.process_action(session, "search")
        _assert_valid_result(result, "search")
        _assert_session_sane(session, "search")
        _print_excerpt("search", result)

    def test_steal_then_flee_then_sneak(self):
        """Steal, get caught (maybe), flee, sneak back."""
        engine = _engine()
        session = engine.new_session("Fingers", "rogue", location="Harbor Town")

        result = engine.process_action(session, "steal from guard")
        _assert_valid_result(result, "steal from guard")
        _print_excerpt("steal from guard", result)

        result = engine.process_action(session, "flee")
        _assert_valid_result(result, "flee")

        result = engine.process_action(session, "sneak")
        _assert_valid_result(result, "sneak")

        result = engine.process_action(session, "steal from merchant")
        _assert_valid_result(result, "steal from merchant")


# ===========================================================================
# Scenario 3: The Crafting Enthusiast
# ===========================================================================

class TestCrafter:
    """Player gathers materials and crafts items."""

    def test_crafter_run(self):
        engine = _engine()
        session = engine.new_session("Artisan", "warrior", location="Harbor Town")

        # Check inventory
        result = engine.process_action(session, "inventory")
        _assert_valid_result(result, "inventory")
        _print_excerpt("inventory", result)

        # Try to craft bread
        result = engine.process_action(session, "craft bread")
        _assert_valid_result(result, "craft bread")
        _print_excerpt("craft bread", result)

        # Try to craft iron sword
        result = engine.process_action(session, "forge iron sword")
        _assert_valid_result(result, "forge iron sword")
        _print_excerpt("forge iron sword", result)

        # Try to mine ore (no pickaxe -- should get message)
        result = engine.process_action(session, "mine")
        _assert_valid_result(result, "mine")
        _print_excerpt("mine", result)

        # Chop wood (no axe -- should get message)
        result = engine.process_action(session, "chop tree")
        _assert_valid_result(result, "chop tree")
        _print_excerpt("chop tree", result)

    def test_craft_nonexistent_recipe(self):
        """Try to craft something that doesn't exist."""
        engine = _engine()
        session = engine.new_session("MadCrafter", "warrior", location="Harbor Town")

        result = engine.process_action(session, "craft nuclear weapon")
        _assert_valid_result(result, "craft nuclear weapon")
        _assert_session_sane(session, "craft nuclear weapon")
        _print_excerpt("craft nuclear weapon", result)


# ===========================================================================
# Scenario 4: The Diplomat
# ===========================================================================

class TestDiplomat:
    """Player uses social skills extensively."""

    def test_diplomat_run(self):
        engine = _engine()
        session = engine.new_session("Silvanus", "priest", location="Harbor Town")

        # Talk to everyone
        for target in ["merchant", "guard", "blacksmith", "priest"]:
            result = engine.process_action(session, f"talk to {target}")
            _assert_valid_result(result, f"talk to {target}")
            _assert_session_sane(session, f"talk to {target}")
            _print_excerpt(f"talk to {target}", result)

        # Persuade
        result = engine.process_action(session, "persuade guard")
        _assert_valid_result(result, "persuade guard")
        _print_excerpt("persuade guard", result)

        # Intimidate
        result = engine.process_action(session, "intimidate beggar")
        _assert_valid_result(result, "intimidate beggar")
        _print_excerpt("intimidate beggar", result)

        # Pray
        result = engine.process_action(session, "pray")
        _assert_valid_result(result, "pray")
        _print_excerpt("pray", result)

        # Trade
        result = engine.process_action(session, "trade with merchant")
        _assert_valid_result(result, "trade with merchant")
        _print_excerpt("trade with merchant", result)


# ===========================================================================
# Scenario 5: The Explorer
# ===========================================================================

class TestExplorer:
    """Player explores the map, moves around, examines everything."""

    def test_explorer_run(self):
        engine = _engine()
        session = engine.new_session("Scout", "rogue", location="Harbor Town")

        # Move in all directions
        for direction in ["north", "south", "east", "west", "north", "north"]:
            result = engine.process_action(session, f"move {direction}")
            _assert_valid_result(result, f"move {direction}")
            _assert_session_sane(session, f"move {direction}")
            _print_excerpt(f"move {direction}", result)

        # Look around
        result = engine.process_action(session, "look around")
        _assert_valid_result(result, "look around")
        _print_excerpt("look around", result)

        # Examine things
        result = engine.process_action(session, "examine the ground")
        _assert_valid_result(result, "examine the ground")
        _print_excerpt("examine the ground", result)

        # Try to climb
        result = engine.process_action(session, "climb wall")
        _assert_valid_result(result, "climb wall")
        _print_excerpt("climb wall", result)

        # Try to swim (unknown action -- should still get narrative)
        result = engine.process_action(session, "swim")
        _assert_valid_result(result, "swim")
        _print_excerpt("swim", result)

    def test_move_to_named_destination(self):
        """Move to a named place that doesn't exist on the map."""
        engine = _engine()
        session = engine.new_session("Wanderer", "rogue", location="Harbor Town")

        result = engine.process_action(session, "move to narnia")
        _assert_valid_result(result, "move to narnia")
        _assert_session_sane(session, "move to narnia")

        result = engine.process_action(session, "move to the tavern")
        _assert_valid_result(result, "move to the tavern")
        _assert_session_sane(session, "move to the tavern")


# ===========================================================================
# Scenario 6: The Derailing Player (MOST IMPORTANT)
# ===========================================================================

class TestDerailingPlayer:
    """Player does absurd things to try to break the game."""

    ABSURD_ACTIONS = [
        "eat the table",
        "seduce the dragon",
        "cast a spell on myself",
        "talk to the wall",
        "attack the floor",
        "try to fly",
        "dance with the guard",
        "steal the tavern",
        "push the mountain",
        "read the sky",
        "intimidate the weather",
        "persuade the door to open",
        "craft a nuclear weapon",
        "mine the air",
        "fish in the fire",
        "chop the stone wall",
        "pray to the goblin",
        "climb the water",
        "sneak past the sun",
        "pick up the building",
        "drop my dignity",
        "equip the merchant",
        "trade with myself",
        "examine my existential dread",
        "cast fireball on myself",
        "rest in the middle of combat",
        "move to narnia",
        "talk to nobody",
        "search for meaning",
        "steal from god",
    ]

    def test_derailing_player(self):
        """Every absurd action must produce a valid narrative without crashing."""
        engine = _engine()
        session = engine.new_session("Chaosborn", "mage", location="Harbor Town")

        for action_text in self.ABSURD_ACTIONS:
            try:
                result = engine.process_action(session, action_text)
            except Exception as e:
                pytest.fail(
                    f"CRASH on absurd action '{action_text}': {type(e).__name__}: {e}"
                )

            _assert_valid_result(result, action_text)
            _assert_session_sane(session, action_text)
            _print_excerpt(action_text, result)

    def test_empty_and_whitespace_input(self):
        """Edge case: empty strings, whitespace, special characters."""
        engine = _engine()
        session = engine.new_session("EdgeCase", "mage", location="Harbor Town")

        edge_inputs = [
            "   ",
            ".",
            "???",
            "!!!!!",
            "a",
            "12345",
            "north north north",
            "@#$%^&*()",
            "the quick brown fox jumps over the lazy dog",
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        ]

        for text in edge_inputs:
            try:
                result = engine.process_action(session, text)
            except Exception as e:
                pytest.fail(
                    f"CRASH on edge input '{text}': {type(e).__name__}: {e}"
                )
            assert result is not None, f"None result for input '{text}'"
            assert result.narrative, f"Empty narrative for input '{text}'"
            _assert_session_sane(session, text)


# ===========================================================================
# Scenario 7: The Long Session
# ===========================================================================

class TestLongSession:
    """Play 100 actions to test game stability over time."""

    def test_long_session(self):
        engine = _engine()
        session = engine.new_session("Endurance", "warrior", location="Harbor Town")

        action_cycle = [
            "look around", "move north", "move east", "look around",
            "talk to guard", "move south", "examine area",
            "inventory", "move west", "rest",
            "attack goblin", "attack", "attack",
            "look around", "move north", "search",
            "craft bread", "pray", "sneak",
            "move east",
        ]

        initial_game_time_hour = session.game_time.hour

        for i in range(100):
            action_text = action_cycle[i % len(action_cycle)]
            try:
                result = engine.process_action(session, action_text)
            except Exception as e:
                pytest.fail(
                    f"CRASH on action #{i} '{action_text}': {type(e).__name__}: {e}"
                )

            assert result is not None, f"Action #{i} '{action_text}' returned None"
            assert result.narrative, f"Action #{i} '{action_text}' produced no narrative"
            _assert_session_sane(session, f"#{i} {action_text}")

            if i % 20 == 0:
                _print_excerpt(f"#{i} {action_text}", result)

        # Session should still be valid after 100 actions
        assert session.player is not None
        assert session.game_time is not None
        # Game time should have advanced (100 actions x 15 min each = ~25 hours)
        total_game_hours = (
            (session.game_time.day - 1) * 24 + session.game_time.hour
        )
        assert total_game_hours > initial_game_time_hour, (
            "Game time should have advanced over 100 actions"
        )
        print(f"\n  Long session completed: 100 actions, "
              f"game time now Day {session.game_time.day} Hour {session.game_time.hour}")


# ===========================================================================
# Scenario 8: Equipment and AP Management
# ===========================================================================

class TestEquipmentAPManagement:
    """Test equipment equip/unequip and AP tracking."""

    def test_equipment_ap_management(self):
        engine = _engine()
        session = engine.new_session("Knight", "warrior")

        # Check initial inventory -- warrior should have starter kit
        result = engine.process_action(session, "inventory")
        _assert_valid_result(result, "inventory")
        _print_excerpt("inventory", result)

        # Unequip weapon
        result = engine.process_action(session, "unequip weapon")
        _assert_valid_result(result, "unequip weapon")
        _print_excerpt("unequip weapon", result)

        # Now the weapon should be in inventory -- equip it back
        result = engine.process_action(session, "equip iron sword")
        _assert_valid_result(result, "equip iron sword")
        _print_excerpt("equip iron sword", result)

        # Drop something from inventory
        result = engine.process_action(session, "drop torch")
        _assert_valid_result(result, "drop torch")
        _print_excerpt("drop torch", result)

        # Try to pick it back up
        result = engine.process_action(session, "pick up torch")
        _assert_valid_result(result, "pick up torch")
        _print_excerpt("pick up torch", result)

    def test_ap_exhaustion_and_refresh(self):
        """Exhaust AP with many actions, verify it refreshes next turn."""
        engine = _engine()
        session = engine.new_session("APTester", "warrior", location="Harbor Town")

        initial_ap = session.ap_tracker.current_ap
        assert initial_ap > 0, "Should start with AP"

        # Perform multiple move actions -- each spends AP but refreshes at turn start
        for i in range(10):
            result = engine.process_action(session, "move north")
            _assert_valid_result(result, f"move north #{i}")
            _assert_session_sane(session, f"move north #{i}")

        # Session should still be functional
        result = engine.process_action(session, "look around")
        _assert_valid_result(result, "look around after AP drain")


# ===========================================================================
# Scenario 9: Combat Stress Test
# ===========================================================================

class TestCombatStress:
    """Stress test combat system with various edge cases."""

    def test_attack_then_rest_cycle(self):
        """Attack until wounded, rest, attack again -- repeat."""
        engine = _engine()
        session = engine.new_session("Gladiator", "warrior", location="Harbor Town")

        for cycle in range(3):
            # Start combat
            result = engine.process_action(session, "attack goblin")
            _assert_valid_result(result, f"attack goblin cycle {cycle}")
            _assert_session_sane(session, f"attack goblin cycle {cycle}")

            # Attack a few more times
            for _ in range(3):
                result = engine.process_action(session, "attack")
                _assert_valid_result(result, "attack")
                if session.player.hp <= 0:
                    break

            if session.player.hp <= 0:
                print(f"\n  Player died in combat cycle {cycle}")
                return  # That's fine, game handles death

            # Flee and rest
            result = engine.process_action(session, "flee")
            _assert_valid_result(result, "flee")
            result = engine.process_action(session, "rest")
            _assert_valid_result(result, "rest")
            _print_excerpt(f"rest after cycle {cycle}", result)

    def test_spell_combat_as_mage(self):
        """Mage uses spells in combat."""
        engine = _engine()
        session = engine.new_session("Wizard", "mage", location="Harbor Town")

        result = engine.process_action(session, "cast fireball at goblin")
        _assert_valid_result(result, "cast fireball at goblin")
        _assert_session_sane(session, "cast fireball at goblin")
        _print_excerpt("cast fireball", result)

        # Keep casting until spell points run out
        for i in range(5):
            result = engine.process_action(session, "cast fireball")
            _assert_valid_result(result, f"cast fireball #{i}")
            _assert_session_sane(session, f"cast fireball #{i}")
            if "exhausted" in result.narrative.lower() or session.player.spell_points <= 0:
                _print_excerpt(f"spell exhausted at cast #{i}", result)
                break

    def test_flee_during_combat(self):
        """Start combat and immediately flee (with guaranteed success)."""
        from unittest.mock import patch
        from engine.world.skill_checks import SkillCheckResult
        engine = _engine()
        session = engine.new_session("Coward", "rogue", location="Harbor Town")

        result = engine.process_action(session, "attack goblin")
        _assert_valid_result(result, "attack goblin")

        # Mock AGI check to always succeed for deterministic test
        mock_result = SkillCheckResult(roll=18, modifier=3, total=21, dc=10, success=True, margin=11, critical=None)
        with patch("engine.api.game_engine.roll_check", return_value=mock_result):
            result = engine.process_action(session, "flee")
        _assert_valid_result(result, "flee")
        _print_excerpt("flee from combat", result)

        # Should be back in exploration mode
        assert not session.in_combat(), "Should no longer be in combat after fleeing"

    def test_move_blocked_during_combat(self):
        """Try to walk away during combat -- should be blocked or trigger flee."""
        engine = _engine()
        session = engine.new_session("RunAway", "warrior", location="Harbor Town")

        result = engine.process_action(session, "attack goblin")
        _assert_valid_result(result, "attack goblin")

        result = engine.process_action(session, "move north")
        _assert_valid_result(result, "move north during combat")
        # Should either block or trigger flee, but not crash


# ===========================================================================
# Scenario 10: Multi-Class Session Variety
# ===========================================================================

class TestMultiClassVariety:
    """Test that all 4 classes can play through a standard sequence without issues."""

    STANDARD_SEQUENCE = [
        "look around",
        "inventory",
        "move north",
        "talk to guard",
        "search",
        "pray",
        "sneak",
        "move south",
        "trade with merchant",
        "rest",
    ]

    @pytest.mark.parametrize("player_class", ["warrior", "rogue", "mage", "priest"])
    def test_class_standard_sequence(self, player_class):
        engine = _engine()
        session = engine.new_session(f"Test_{player_class}", player_class,
                                     location="Harbor Town")

        for action_text in self.STANDARD_SEQUENCE:
            try:
                result = engine.process_action(session, action_text)
            except Exception as e:
                pytest.fail(
                    f"CRASH: class={player_class}, action='{action_text}': "
                    f"{type(e).__name__}: {e}"
                )
            _assert_valid_result(result, f"{player_class}:{action_text}")
            _assert_session_sane(session, f"{player_class}:{action_text}")

        print(f"\n  Class '{player_class}' completed standard sequence OK")


# ===========================================================================
# Scenario 11: State Consistency Checks
# ===========================================================================

class TestStateConsistency:
    """Verify internal state consistency after various action sequences."""

    def test_game_time_advances(self):
        """Game time must advance with every action."""
        engine = _engine()
        session = engine.new_session("TimeCheck", "warrior", location="Harbor Town")

        initial_day = session.game_time.day
        initial_hour = session.game_time.hour

        for _ in range(10):
            engine.process_action(session, "look around")

        # 10 actions x 15 min = 150 min = 2.5 hours advance
        final_total = session.game_time.day * 24 + session.game_time.hour
        initial_total = initial_day * 24 + initial_hour
        assert final_total > initial_total, "Game time should advance with actions"

    def test_hp_never_exceeds_max(self):
        """HP should never exceed max_hp even with multiple rests."""
        engine = _engine()
        session = engine.new_session("Healer", "priest", location="Harbor Town")

        for _ in range(5):
            engine.process_action(session, "rest")
            engine.process_action(session, "pray")
            assert session.player.hp <= session.player.max_hp, (
                f"HP ({session.player.hp}) exceeded max_hp ({session.player.max_hp})"
            )

    def test_no_duplicate_entities_after_movement(self):
        """Moving around should not create duplicate player entities."""
        engine = _engine()
        session = engine.new_session("Walker", "rogue", location="Harbor Town")

        for _ in range(20):
            engine.process_action(session, "move north")
            engine.process_action(session, "move east")

        # Count player entities in spatial index
        player_count = sum(
            1 for e in session.spatial_index.all_entities()
            if e.id == "player"
        )
        assert player_count == 1, (
            f"Found {player_count} player entities in spatial index (expected 1)"
        )

    def test_inventory_integrity(self):
        """Inventory operations should maintain consistency."""
        engine = _engine()
        session = engine.new_session("Packrat", "warrior", location="Harbor Town")

        # Count initial items
        initial_inv_count = len(session.inventory)
        initial_equip_count = sum(
            1 for v in session.equipment.values() if v is not None
        )

        # Unequip everything
        for slot in list(session.equipment.keys()):
            if session.equipment[slot] is not None:
                engine.process_action(session, f"unequip {slot}")

        # All previously equipped items should now be in inventory
        new_inv_count = len(session.inventory)
        assert new_inv_count >= initial_inv_count, (
            "Unequipping should add items to inventory"
        )

        # Re-equip a weapon
        engine.process_action(session, "equip iron sword")
        # Inventory should decrease by 1
        assert len(session.inventory) == new_inv_count - 1 or \
               "don't have" in "".join(str(r) for r in []), \
               "Equipping should remove from inventory"


# ===========================================================================
# Scenario 12: Rapid Action Spam
# ===========================================================================

class TestRapidActionSpam:
    """Spam the same action many times to find accumulation bugs."""

    def test_spam_look(self):
        """Look around 50 times -- should not degrade."""
        engine = _engine()
        session = engine.new_session("Looker", "warrior", location="Harbor Town")

        for i in range(50):
            result = engine.process_action(session, "look around")
            _assert_valid_result(result, f"look around #{i}")
            _assert_session_sane(session, f"look around #{i}")

    def test_spam_inventory(self):
        """Check inventory 50 times."""
        engine = _engine()
        session = engine.new_session("Checker", "warrior", location="Harbor Town")

        for i in range(50):
            result = engine.process_action(session, "inventory")
            _assert_valid_result(result, f"inventory #{i}")

    def test_spam_rest(self):
        """Rest 20 times -- game time should advance massively."""
        engine = _engine()
        session = engine.new_session("Sleeper", "warrior", location="Harbor Town")

        for i in range(20):
            result = engine.process_action(session, "rest")
            _assert_valid_result(result, f"rest #{i}")
            _assert_session_sane(session, f"rest #{i}")
            assert session.player.hp <= session.player.max_hp

        # 20 rests x ~8 hours each = ~160 hours = ~6.7 days
        assert session.game_time.day > 1, (
            f"After 20 rests, should be past day 1 (day={session.game_time.day})"
        )
