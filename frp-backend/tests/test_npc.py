"""
Ember RPG - Phase 5: NPC Agent Tests
"""
import pytest
from engine.npc import (
    NPC, NPCRole, Disposition, NPCMemory, DialogueLine, DialogueNode, NPCManager
)


class TestNPCMemory:
    def test_initial_state(self):
        mem = NPCMemory()
        assert mem.reputation == 0
        assert mem.has_met_player is False
        assert mem.events == []

    def test_add_event(self):
        mem = NPCMemory()
        mem.add_event("Talked about the weather")
        assert len(mem.events) == 1

    def test_events_trimmed_to_max(self):
        mem = NPCMemory()
        for i in range(15):
            mem.add_event(f"Event {i}")
        assert len(mem.events) == NPCMemory.MAX_EVENTS

    def test_adjust_reputation_positive(self):
        mem = NPCMemory()
        mem.adjust_reputation(30)
        assert mem.reputation == 30

    def test_adjust_reputation_clamped_high(self):
        mem = NPCMemory()
        mem.adjust_reputation(200)
        assert mem.reputation == 100

    def test_adjust_reputation_clamped_low(self):
        mem = NPCMemory()
        mem.adjust_reputation(-200)
        assert mem.reputation == -100

    def test_adjust_reputation_accumulates(self):
        mem = NPCMemory()
        mem.adjust_reputation(20)
        mem.adjust_reputation(-10)
        assert mem.reputation == 10


class TestNPC:
    def test_creation(self):
        npc = NPC(name="Aria", role=NPCRole.MERCHANT)
        assert npc.name == "Aria"
        assert npc.role == NPCRole.MERCHANT
        assert npc.disposition == Disposition.NEUTRAL

    def test_greet_neutral(self):
        npc = NPC(name="Guard", role=NPCRole.GUARD)
        greeting = npc.greet()
        assert "Guard" in greeting
        assert isinstance(greeting, str)

    def test_greet_hostile(self):
        npc = NPC(name="Bandit", disposition=Disposition.HOSTILE)
        greeting = npc.greet()
        assert "Bandit" in greeting

    def test_greet_friendly(self):
        npc = NPC(name="Innkeeper", disposition=Disposition.FRIENDLY)
        greeting = npc.greet()
        assert "Innkeeper" in greeting

    def test_greet_all_dispositions(self):
        for disp in Disposition:
            npc = NPC(name="Test", disposition=disp)
            greeting = npc.greet()
            assert isinstance(greeting, str)
            assert len(greeting) > 0

    def test_react_trade_with_inventory(self):
        npc = NPC(name="Trader", role=NPCRole.MERCHANT, inventory=["Sword", "Shield"])
        response = npc.react_to_player("satın almak istiyorum")
        assert "Sword" in response or "Shield" in response

    def test_react_trade_no_inventory(self):
        npc = NPC(name="Trader", role=NPCRole.MERCHANT)
        response = npc.react_to_player("buy something")
        assert "Trader" in response

    def test_react_quest_with_quest(self):
        npc = NPC(name="Elder", quest="Kuzeyden bir şey getir.")
        response = npc.react_to_player("görev var mı")
        assert "Kuzeyden" in response

    def test_react_quest_no_quest(self):
        npc = NPC(name="Guard", role=NPCRole.GUARD)
        response = npc.react_to_player("any quests?")
        assert isinstance(response, str)

    def test_react_hostile_refuses(self):
        npc = NPC(name="Bandit", disposition=Disposition.HOSTILE)
        response = npc.react_to_player("yardım eder misin?")
        assert "Bandit" in response

    def test_react_high_reputation(self):
        npc = NPC(name="Friend")
        npc.memory.adjust_reputation(60)
        response = npc.react_to_player("nasılsın?")
        assert isinstance(response, str)

    def test_react_low_reputation(self):
        npc = NPC(name="Enemy")
        npc.memory.adjust_reputation(-40)
        response = npc.react_to_player("merhaba")
        assert isinstance(response, str)

    def test_build_prompt(self):
        npc = NPC(name="Wizard", role=NPCRole.QUEST_GIVER,
                  personality="Mysterious and cryptic.")
        prompt = npc.build_prompt("Merhaba, yardım lazım")
        assert "Wizard" in prompt
        assert "quest_giver" in prompt
        assert "Merhaba" in prompt

    def test_personality_line_all_roles(self):
        for role in NPCRole:
            npc = NPC(name="Test", role=role)
            line = npc._personality_line()
            assert isinstance(line, str)
            assert len(line) > 0


class TestNPCManager:
    def test_add_and_find_npc(self):
        manager = NPCManager()
        npc = NPC(name="Barkeep")
        manager.add_npc(npc)
        found = manager.find("barkeep")
        assert found is not None
        assert found.name == "Barkeep"

    def test_find_case_insensitive(self):
        manager = NPCManager()
        npc = NPC(name="Guard")
        manager.add_npc(npc)
        assert manager.find("GUARD") is not None
        assert manager.find("guard") is not None

    def test_find_partial_match(self):
        manager = NPCManager()
        npc = NPC(name="Town Guard")
        manager.add_npc(npc)
        found = manager.find("town")
        assert found is not None

    def test_find_nonexistent_returns_none(self):
        manager = NPCManager()
        assert manager.find("nobody") is None

    def test_interact_marks_as_met(self):
        manager = NPCManager()
        npc = NPC(name="Elder")
        manager.add_npc(npc)
        assert npc.memory.has_met_player is False
        manager.interact(npc, "Merhaba")
        assert npc.memory.has_met_player is True

    def test_interact_records_event(self):
        manager = NPCManager()
        npc = NPC(name="Merchant")
        manager.add_npc(npc)
        manager.interact(npc, "Eşya satıyor musunuz?")
        assert len(npc.memory.events) >= 1

    def test_interact_returns_string(self):
        manager = NPCManager()
        npc = NPC(name="Guard", role=NPCRole.GUARD)
        manager.add_npc(npc)
        response = manager.interact(npc, "Merhaba")
        assert isinstance(response, str)
        assert len(response) > 0

    def test_interact_with_mock_llm(self):
        def mock_llm(prompt):
            return "Bu benim LLM cevabım."

        manager = NPCManager(llm=mock_llm)
        npc = NPC(name="Mage")
        manager.add_npc(npc)
        response = manager.interact(npc, "Büyü öğretir misin?")
        assert response == "Bu benim LLM cevabım."

    def test_spawn_default_npcs_inn(self):
        manager = NPCManager()
        npcs = manager.spawn_default_npcs("Taş Köprü Meyhanesi")
        assert len(npcs) >= 1
        names = [n.name for n in npcs]
        assert "Barkeep" in names

    def test_spawn_default_npcs_has_guard(self):
        manager = NPCManager()
        npcs = manager.spawn_default_npcs("Liman Kasabası")
        names = [n.name for n in npcs]
        assert "Guard" in names

    def test_list_npcs(self):
        manager = NPCManager()
        manager.add_npc(NPC(name="A"))
        manager.add_npc(NPC(name="B"))
        assert len(manager.list_npcs()) == 2

    def test_barkeep_has_quest(self):
        manager = NPCManager()
        manager.spawn_default_npcs("Taş Köprü Meyhanesi")
        barkeep = manager.find("barkeep")
        assert barkeep is not None
        assert barkeep.quest is not None
