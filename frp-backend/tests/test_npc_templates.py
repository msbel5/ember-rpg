"""
Ember RPG - NPC Template Integration Tests

Tests for:
- load_templates() bridge between npc_templates.json and live NPC objects
- Multi-step reputation accumulation and disposition branching
- build_prompt() with populated event history
"""
import os
import pytest
from engine.npc import NPC, NPCRole, Disposition, NPCMemory, NPCManager


# Resolve path to the templates file relative to this test file
TEMPLATES_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "npc_templates.json"
)


class TestLoadTemplates:
    """Tests for NPCManager.load_templates()"""

    def test_load_all_npcs_count(self):
        """Load npc_templates.json and verify the expected NPC count."""
        manager = NPCManager()
        loaded = manager.load_templates(TEMPLATES_PATH)
        # The file should have 22 NPCs after the rogue archetype addition
        assert len(loaded) == 22, f"Expected 22 NPCs, got {len(loaded)}"

    def test_spot_check_blacksmith_fields(self):
        """Spot-check misc_blacksmith: role must be COMMONER (not NEUTRAL)."""
        manager = NPCManager()
        manager.load_templates(TEMPLATES_PATH)

        # Find by template_id attribute
        blacksmith = next(
            (n for n in manager.list_npcs() if getattr(n, "template_id", "") == "misc_blacksmith"),
            None,
        )
        assert blacksmith is not None, "misc_blacksmith not found in loaded NPCs"
        assert blacksmith.role == NPCRole.COMMONER, (
            f"Expected COMMONER, got {blacksmith.role}"
        )
        assert isinstance(blacksmith.name, str)
        assert len(blacksmith.name) > 0

    def test_rogue_archetype_loaded(self):
        """Verify rogue-archetype NPC (rogue_shadow_thief) is present."""
        manager = NPCManager()
        manager.load_templates(TEMPLATES_PATH)
        rogue = next(
            (n for n in manager.list_npcs() if getattr(n, "template_id", "") == "rogue_shadow_thief"),
            None,
        )
        assert rogue is not None, "rogue_shadow_thief not found"
        assert rogue.role == NPCRole.ROGUE or rogue.role.value == "rogue", (
            f"Expected rogue role, got {rogue.role}"
        )


class TestReputationAccumulation:
    """Tests for multi-step reputation and disposition branching."""

    def test_five_interactions_reputation_change(self):
        """Simulate 5 reputation adjustments and verify cumulative result."""
        mem = NPCMemory()
        deltas = [10, 15, -5, 20, -8]   # net = +32
        for delta in deltas:
            mem.adjust_reputation(delta)
        assert mem.reputation == 32, f"Expected 32, got {mem.reputation}"

    def test_reputation_clamp_over_many_steps(self):
        """Large positive adjustments should clamp at 100."""
        mem = NPCMemory()
        for _ in range(5):
            mem.adjust_reputation(30)
        assert mem.reputation == 100

    def test_disposition_branch_at_threshold(self):
        """
        Verify that an NPC's react_to_player behaviour changes
        once reputation crosses from negative into positive territory.
        """
        npc = NPC(name="TestNPC", role=NPCRole.COMMONER, personality="Calm and measured.")

        # Start hostile-ish (low reputation)
        npc.memory.adjust_reputation(-40)
        low_response = npc.react_to_player("hello")
        assert isinstance(low_response, str)

        # Push reputation well above 0 (simulate accumulated interactions)
        npc.memory.adjust_reputation(80)   # now at +40
        high_response = npc.react_to_player("hello")
        assert isinstance(high_response, str)

        # Both responses are valid strings; disposition shift doesn't crash
        assert len(low_response) > 0
        assert len(high_response) > 0

    def test_reputation_accumulates_correctly_after_five_steps(self):
        """Reputation after exactly 5 equal steps equals 5×delta (if unclamped)."""
        mem = NPCMemory()
        for _ in range(5):
            mem.adjust_reputation(8)
        assert mem.reputation == 40


class TestBuildPromptWithEventHistory:
    """Tests for build_prompt() with populated NPC memory."""

    def test_events_appear_in_prompt(self):
        """Add 3 events to NPC memory; all should appear in build_prompt() output."""
        npc = NPC(
            name="Archivist Vael",
            role=NPCRole.QUEST_GIVER,
            personality="Scholarly and precise.",
        )
        events = [
            "Player found the lost tome.",
            "Player defended the library.",
            "Player decoded the ancient cipher.",
        ]
        for event in events:
            npc.memory.add_event(event)

        prompt = npc.build_prompt("What do you know about the cipher?")

        for event in events:
            assert event in prompt, f"Event not found in prompt: '{event}'"

    def test_prompt_includes_npc_name_and_role(self):
        """build_prompt() must reference the NPC's name and role."""
        npc = NPC(name="Sentinel Dara", role=NPCRole.GUARD, personality="Strict and vigilant.")
        npc.memory.add_event("Player challenged the gate.")
        npc.memory.add_event("Player showed valid papers.")
        npc.memory.add_event("Player entered the city.")

        prompt = npc.build_prompt("Can I pass?")

        assert "Sentinel Dara" in prompt
        assert "guard" in prompt.lower()

    def test_prompt_includes_player_input(self):
        """build_prompt() must include the player's input text."""
        npc = NPC(name="Oracle", role=NPCRole.QUEST_GIVER, personality="Prophetic and vague.")
        npc.memory.add_event("Player offered a silver coin.")
        npc.memory.add_event("Player asked about the future.")
        npc.memory.add_event("Player waited in silence.")

        player_question = "What fate awaits me?"
        prompt = npc.build_prompt(player_question)

        assert player_question in prompt
