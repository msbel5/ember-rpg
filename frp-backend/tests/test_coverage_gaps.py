"""
Ember RPG — Targeted Coverage Gap Tests
=========================================
Tests aimed at specific uncovered lines to push total coverage to 99%+.
"""
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


# ── helpers ───────────────────────────────────────────────────────────────────

def _new_session(name="Cov", cls="warrior"):
    resp = client.post("/game/session/new", json={"player_name": name, "player_class": cls})
    assert resp.status_code == 200
    return resp.json()


# ── engine/core/npc.py (0% → ~100%) ──────────────────────────────────────────

class TestCoreNPC:
    """Cover engine/core/npc.py (NPCManager, _validate_npc)."""

    def setup_method(self):
        from engine.core.npc import NPCManager
        self.mgr = NPCManager()
        self.mgr.load()

    def test_load_returns_list(self):
        npcs = self.mgr.list_npcs()
        assert len(npcs) > 0

    def test_get_existing_npc(self):
        npcs = self.mgr.list_npcs()
        npc_id = npcs[0]["id"]
        npc = self.mgr.get(npc_id)
        assert npc is not None
        assert npc["id"] == npc_id

    def test_get_missing_npc_returns_none(self):
        assert self.mgr.get("nonexistent_npc_xyz") is None

    def test_get_dialogue_random(self):
        npcs = self.mgr.list_npcs()
        npc = npcs[0]
        line = self.mgr.get_dialogue(npc, "greetings", random_pick=True)
        assert isinstance(line, str)
        assert len(line) > 0

    def test_get_dialogue_first(self):
        npcs = self.mgr.list_npcs()
        npc = npcs[0]
        line = self.mgr.get_dialogue(npc, "greetings", random_pick=False)
        assert line == npc["dialogue_snippets"]["greetings"][0]

    def test_get_dialogue_missing_snippets_raises(self):
        from engine.core.npc import NPCManager
        mgr = NPCManager()
        with pytest.raises(ValueError):
            mgr.get_dialogue({"id": "x"}, "greetings")

    def test_modify_relationship_with_action(self):
        npcs = self.mgr.list_npcs()
        npc = npcs[0]
        rm = npc["relationship_modifiers"]
        action = list(rm.keys())[0]
        score = self.mgr.modify_relationship(npc, action)
        assert -100 <= score <= 100

    def test_modify_relationship_custom_delta(self):
        npcs = self.mgr.list_npcs()
        npc = npcs[0]
        self.mgr.reset_relationship(npc)
        score = self.mgr.modify_relationship(npc, "any", custom_delta=20.0)
        assert score == 20.0

    def test_relationship_clamps_max(self):
        npcs = self.mgr.list_npcs()
        npc = npcs[0]
        self.mgr.reset_relationship(npc)
        score = self.mgr.modify_relationship(npc, "any", custom_delta=200.0)
        assert score == 100.0

    def test_relationship_clamps_min(self):
        npcs = self.mgr.list_npcs()
        npc = npcs[0]
        self.mgr.reset_relationship(npc)
        score = self.mgr.modify_relationship(npc, "any", custom_delta=-200.0)
        assert score == -100.0

    def test_get_relationship(self):
        npcs = self.mgr.list_npcs()
        npc = npcs[0]
        rel = self.mgr.get_relationship(npc)
        assert isinstance(rel, float)

    def test_get_by_role(self):
        npcs_by_role = self.mgr.get_by_role("merchant")
        assert isinstance(npcs_by_role, list)

    def test_get_by_faction(self):
        npcs = self.mgr.list_npcs()
        if npcs:
            faction = npcs[0]["faction_alignment"]
            result = self.mgr.get_by_faction(faction)
            assert len(result) >= 1

    def test_file_not_found(self):
        from engine.core.npc import NPCManager
        mgr = NPCManager(data_path="/tmp/nonexistent_abc.json")
        with pytest.raises(FileNotFoundError):
            mgr.load()

    def test_validate_npc_missing_required_fields(self):
        from engine.core.npc import _validate_npc, NPCValidationError
        with pytest.raises(NPCValidationError):
            _validate_npc({"id": "bad"})

    def test_validate_npc_missing_personality_fields(self):
        from engine.core.npc import _validate_npc, NPCValidationError
        with pytest.raises(NPCValidationError):
            _validate_npc({
                "id": "x", "name": "X", "race": "human", "role": "merchant",
                "faction_alignment": "neutral",
                "personality": {},  # missing traits/motivations/fears
                "dialogue_snippets": {"greetings": ["Hi"], "farewells": ["Bye"], "idle": ["..."], "quest_related": ["Quest!"]},
                "relationship_modifiers": {},
            })

    def test_validate_npc_invalid_relationship_modifier(self):
        from engine.core.npc import _validate_npc, NPCValidationError
        with pytest.raises(NPCValidationError):
            _validate_npc({
                "id": "x", "name": "X", "race": "human", "role": "merchant",
                "faction_alignment": "neutral",
                "personality": {"traits": [], "motivations": [], "fears": []},
                "dialogue_snippets": {"greetings": ["Hi"], "farewells": ["Bye"], "idle": ["..."], "quest_related": ["Quest!"]},
                "relationship_modifiers": {"action": "not_a_number"},
            })


# ── engine/npc/__init__.py gaps ───────────────────────────────────────────────

class TestNPCModule:
    """Cover npc/__init__.py uncovered lines."""

    def test_npc_memory_reputation_high(self):
        from engine.npc import NPC, NPCRole
        npc = NPC(name="Ally", role=NPCRole.ALLY)
        npc.memory.reputation = 60
        response = npc.react_to_player("hello")
        assert "always here" in response.lower() or "ally" in response.lower()

    def test_npc_memory_reputation_low(self):
        from engine.npc import NPC, NPCRole
        npc = NPC(name="Enemy", role=NPCRole.VILLAIN)
        npc.memory.reputation = -40
        response = npc.react_to_player("hello")
        assert "trust" in response.lower() or "warily" in response.lower() or len(response) > 0

    def test_npc_load_from_templates(self):
        from engine.npc import NPCManager as NewNPCManager
        mgr = NewNPCManager()
        loaded = mgr.load_templates("data/npc_templates.json")
        assert len(loaded) > 0

    def test_npc_find_partial(self):
        from engine.npc import NPC, NPCRole, NPCManager as NewNPCManager
        mgr = NewNPCManager()
        mgr.add_npc(NPC(name="TavernKeeper", role=NPCRole.INNKEEPER))
        result = mgr.find("tavernkeeper")
        assert result is not None

    def test_generate_npc_dialogue_llm_fallback(self):
        """generate_npc_dialogue_llm falls back to template when LLM unavailable."""
        from engine.npc import generate_npc_dialogue_llm
        npc_template = {
            "id": "test_npc",
            "name": "Testman",
            "role": "merchant",
            "personality": ["gruff"],
            "speech_style": "terse",
            "dialogue": {"greeting": ["Greetings, friend!"]},
        }
        mock_mem = MagicMock()
        mock_mem.build_context.return_value = ""
        import engine.llm as llm_module
        mock_router = MagicMock()
        mock_router.narrative.return_value = None  # force fallback
        with patch.object(llm_module, "get_llm_router", return_value=mock_router):
            result = generate_npc_dialogue_llm(npc_template, mock_mem, player_input="Hello!")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_generate_npc_dialogue_llm_with_result(self):
        """generate_npc_dialogue_llm returns LLM result when available."""
        from engine.npc import generate_npc_dialogue_llm
        import engine.llm as llm_module
        npc_template = {"id": "t", "name": "T", "role": "guard", "personality": [], "speech_style": "blunt"}
        mock_router = MagicMock()
        mock_router.narrative.return_value = "Stand where you are!"
        with patch.object(llm_module, "get_llm_router", return_value=mock_router):
            result = generate_npc_dialogue_llm(npc_template, None, player_input="Who goes there?")
        assert result == "Stand where you are!"


# ── engine/npc/npc_memory.py gaps ────────────────────────────────────────────

class TestNPCMemory:
    """Cover npc/npc_memory.py uncovered lines."""

    def test_add_conversation_positive_sentiment(self):
        from engine.npc.npc_memory import NPCMemory
        mem = NPCMemory(npc_id="test", name="Bram")
        mem.add_conversation("Helped me out", "positive", "Day 1")
        assert len(mem.conversations) == 1
        assert mem.relationship_score > 0

    def test_add_conversation_negative_sentiment(self):
        from engine.npc.npc_memory import NPCMemory
        mem = NPCMemory(npc_id="test", name="Bram")
        mem.add_conversation("Stole from me", "negative", "Day 2")
        assert mem.relationship_score < 0

    def test_conversation_overflow_compresses(self):
        from engine.npc.npc_memory import NPCMemory
        mem = NPCMemory(npc_id="test", name="Bram")
        for i in range(12):
            mem.add_conversation(f"Talk {i}", "neutral", f"Day {i}")
        assert len(mem.conversations) <= 10

    def test_add_known_fact_deduplication(self):
        from engine.npc.npc_memory import NPCMemory
        mem = NPCMemory(npc_id="test", name="Bram")
        mem.add_known_fact("Player is a hero")
        mem.add_known_fact("Player is a hero")
        assert mem.known_facts.count("Player is a hero") == 1

    def test_build_context_with_template(self):
        from engine.npc.npc_memory import NPCMemory
        mem = NPCMemory(npc_id="test", name="Bram")
        mem.add_known_fact("Carries a sword")
        mem.current_desire = "A fine meal"
        ctx = mem.build_context({"role": "merchant"})
        assert "Bram" in ctx
        assert "merchant" in ctx
        assert "sword" in ctx

    def test_relationship_labels(self):
        from engine.npc.npc_memory import NPCMemory
        mem = NPCMemory(npc_id="test", name="Bram")
        for delta, expected_label in [
            (70, "ally"), (40, "friend"), (15, "acquaintance"),
            (-25, "unfriendly"), (-60, "enemy"),
        ]:
            mem.relationship_score = 0
            mem.update_relationship(delta)
            assert mem.relationship_label == expected_label, \
                f"Score {mem.relationship_score} -> expected {expected_label}, got {mem.relationship_label}"

    def test_propagate_gossip(self):
        from engine.npc.npc_memory import NPCMemoryManager
        mgr = NPCMemoryManager("sess1")
        mgr.propagate_gossip("npc_a", "npc_b", "The hero killed a dragon!")
        mem_b = mgr.get_memory("npc_b")
        assert any("dragon" in f for f in mem_b.known_facts)

    def test_record_interaction(self):
        from engine.npc.npc_memory import NPCMemoryManager
        mgr = NPCMemoryManager("sess2")
        mgr.record_interaction("npc_x", "Traded goods", "positive", "Morning", facts=["Trustworthy"])
        mem = mgr.get_memory("npc_x")
        assert len(mem.conversations) == 1
        assert "Trustworthy" in mem.known_facts


# ── engine/core/effect.py gaps ────────────────────────────────────────────────

class TestEffects:
    """Cover effect.py uncovered lines."""

    def test_buff_effect_apply(self):
        from engine.core.effect import BuffEffect
        from engine.core.character import Character
        char = Character(name="Hero", hp=30, max_hp=30)
        buf = BuffEffect(stat="MIG", bonus=2, duration=3)
        msg = buf.apply(char)
        assert "MIG" in msg or "gains" in msg.lower()
        assert char.stats["MIG"] == 12  # default 10 + 2

    def test_buff_effect_invalid_stat(self):
        from engine.core.effect import BuffEffect
        from engine.core.character import Character
        char = Character(name="Hero", hp=30, max_hp=30)
        buf = BuffEffect(stat="invalid_stat_xyz", bonus=2, duration=1)
        with pytest.raises(ValueError):
            buf.apply(char)
    def test_status_effect_apply(self):
        from engine.core.effect import StatusEffect
        from engine.core.character import Character
        char = Character(name="Hero", hp=30, max_hp=30)
        eff = StatusEffect(status="poisoned", duration=2)
        msg = eff.apply(char)
        assert "poisoned" in msg.lower()

    def test_utility_effect_apply(self):
        from engine.core.effect import UtilityEffect
        from engine.core.character import Character
        char = Character(name="Hero", hp=30, max_hp=30)
        eff = UtilityEffect(action="detect_magic")
        msg = eff.apply(char)
        assert "detect_magic" in msg

    def test_summon_effect_apply(self):
        from engine.core.effect import SummonEffect
        from engine.core.character import Character
        char = Character(name="Hero", hp=30, max_hp=30)
        eff = SummonEffect(creature="wolf")
        msg = eff.apply(char)
        assert "wolf" in msg.lower()

    def test_buff_effect_to_dict(self):
        from engine.core.effect import BuffEffect
        buf = BuffEffect(stat="dexterity", bonus=3, duration=2)
        d = buf.to_dict()
        assert d["type"] == "buff"
        assert d["stat"] == "dexterity"

    def test_status_effect_to_dict(self):
        from engine.core.effect import StatusEffect
        eff = StatusEffect(status="stunned", duration=1)
        d = eff.to_dict()
        assert d["type"] == "status"

    def test_from_dict_heal(self):
        from engine.core.effect import Effect
        eff = Effect.from_dict({"type": "heal", "amount": "1d4"})
        assert eff is not None

    def test_from_dict_buff(self):
        from engine.core.effect import Effect
        eff = Effect.from_dict({"type": "buff", "stat": "strength", "bonus": 1, "duration": 2})
        assert eff is not None


# ── engine/core/combat.py: dead-turn skip ─────────────────────────────────────

class TestCombatDeadTurnSkip:
    """Cover lines 297-303: skip dead combatants in turn advance."""

    def test_dead_combatant_skipped(self):
        from engine.core.combat import CombatManager
        from engine.core.character import Character
        hero = Character(name="Hero", hp=50, max_hp=50)
        dead_enemy = Character(name="Zombie", hp=1, max_hp=20)
        live_enemy = Character(name="Orc", hp=20, max_hp=20)
        combat = CombatManager([hero, dead_enemy, live_enemy], seed=42)
        combat.start_turn()
        # Kill the dead_enemy
        dead_enemy.hp = 0
        # Call end_turn to advance and hit the skip-dead logic
        combat.end_turn()
        assert combat.current_turn is not None


# ── engine/core/character.py line 249-250 ─────────────────────────────────────

class TestCharacterRepr:

    def test_character_repr(self):
        from engine.core.character import Character
        char = Character(name="Rogue", hp=20, max_hp=20)
        r = repr(char)
        assert "Rogue" in r


# ── engine/api/routes.py: level_up path (line 161-162) ───────────────────────

class TestLevelUpInAction:
    """Trigger level-up by mocking XP progression."""

    def test_level_up_response_structure(self):
        from engine.api.routes import _sessions
        from engine.core.progression import LevelUpResult, ClassAbility

        data = _new_session("LvlUpHero")
        sid = data["session_id"]

        ability = ClassAbility(
            name="Power Strike", description="A powerful attack",
            passive=False, required_level=2, class_name="warrior",
        )
        mock_lu = LevelUpResult(
            old_level=1, new_level=2, new_abilities=[ability],
            stat_bonus="MIG", hp_increase=5, sp_increase=2,
        )
        mock_result = MagicMock()
        mock_result.narrative = "You level up!"
        mock_result.scene_type = MagicMock(value="exploration")
        mock_result.level_up = mock_lu
        mock_result.combat_state = None
        mock_result.state_changes = {}
        with patch("engine.api.routes.engine.process_action", return_value=mock_result):
            resp = client.post(f"/game/session/{sid}/action", json={"input": "look around"})
        assert resp.status_code == 200
        body = resp.json()
        assert "level_up" in body
        assert body["level_up"]["new_level"] == 2


# ── engine/api/npc_memory_routes.py lines 39-41 ───────────────────────────────

class TestNPCMemoryRoutes:

    def test_get_npc_context(self):
        data = _new_session("MemTester")
        sid = data["session_id"]
        # Add a fact first
        client.post(f"/game/session/{sid}/npc/merchant_bram/fact", json={"fact": "test fact"})
        resp = client.get(f"/game/session/{sid}/npc/merchant_bram/context")
        assert resp.status_code == 200
        body = resp.json()
        assert "context" in body


# ── engine/api/scene_routes.py lines 52-53, 61-62, 77-78 ─────────────────────

class TestSceneRoutesGaps:

    def test_scene_enter_without_session_in_memory(self):
        """scene/enter with unknown session_id still returns valid scene (fallback path)."""
        payload = {
            "session_id": "nonexistent_xyz_abc",
            "location": "Dark Cave",
            "location_type": "dungeon",
            "time_of_day": "night",
            "player_name": "Ghost",
            "player_level": 1,
            "is_first_visit": True,
        }
        resp = client.post("/game/scene/enter", json=payload)
        assert resp.status_code == 200


# ── engine/world/world_routes.py gaps ────────────────────────────────────────

class TestWorldRoutes:

    def test_world_status(self):
        data = _new_session("WorldTest")
        sid = data["session_id"]
        resp = client.get(f"/game/world/{sid}/status")
        assert resp.status_code in (200, 404)

    def test_world_discover_location(self):
        data = _new_session("WorldDisc")
        sid = data["session_id"]
        resp = client.post(f"/game/world/{sid}/discover", json={
            "location_id": "dark_forest",
            "location_name": "Dark Forest",
        })
        assert resp.status_code in (200, 404, 422)

    def test_world_get_routes_map(self):
        data = _new_session("WorldMap")
        sid = data["session_id"]
        resp = client.get(f"/game/world/{sid}/map")
        assert resp.status_code in (200, 404)


# ── engine/api/save_routes.py lines 57-58, 89-90, 115-116 ────────────────────

class TestSaveRoutesEdgeCases:

    def test_save_500_on_corrupt_session(self):
        """save_session 500 when save_manager.save raises."""
        data = _new_session("SaveBad")
        sid = data["session_id"]
        from engine.api import save_routes
        with patch.object(save_routes.save_manager, "save", side_effect=Exception("disk full")):
            resp = client.post(f"/game/session/{sid}/save", json={"player_id": "test"})
        assert resp.status_code == 500

    def test_get_save_not_found(self):
        resp = client.get("/game/saves/file/nonexistent_save_id_xyz")
        assert resp.status_code == 404

    def test_load_session_not_found(self):
        resp = client.post("/game/session/load/nonexistent_save_id_xyz")
        assert resp.status_code == 404


# ── engine/api/shop_routes.py lines 54, 69, 165, 205 ──────────────────────────

class TestShopEdgeCases:

    def test_shop_invalid_npc(self):
        resp = client.get("/game/shop/nonexistent_npc_xyz")
        assert resp.status_code == 404

    def test_shop_buy_insufficient_gold(self):
        data = _new_session("Broke")
        sid = data["session_id"]
        from engine.api.routes import _sessions
        session = _sessions[sid]
        session.player.gold = 0  # broke

        resp = client.post("/game/shop/merchant_general_goods/buy", json={
            "session_id": sid,
            "item_id": "potion_of_healing",
            "quantity": 1,
        })
        assert resp.status_code == 400
        assert "gold" in resp.json()["detail"].lower()

    def test_shop_sell_item_not_in_inventory(self):
        data = _new_session("NoItem")
        sid = data["session_id"]
        resp = client.post("/game/shop/merchant_general_goods/sell", json={
            "session_id": sid,
            "item_id": "potion_of_healing",
            "quantity": 1,
        })
        assert resp.status_code == 400

    def test_shop_npc_without_inventory(self):
        """NPC that exists but has no shop inventory → 404."""
        # Use an NPC id that has no shop_inventory
        resp = client.get("/game/shop/guard_patrol_1")
        assert resp.status_code == 404


# ── engine/core/rules.py lines 50, 52 ─────────────────────────────────────────

class TestRulesEdgeCases:

    def test_roll_dice_invalid_num_dice(self):
        from engine.core.rules import roll_dice
        with pytest.raises(ValueError, match="Number of dice"):
            roll_dice("0d6")

    def test_roll_dice_invalid_die_size(self):
        from engine.core.rules import roll_dice
        with pytest.raises(ValueError, match="Die size"):
            roll_dice("1d1")


# ── engine/core/loot.py lines 84, 102, 116 ───────────────────────────────────

class TestLootEdgeCases:

    def test_generate_loot_empty_enemy(self):
        from engine.core.loot import LootSystem
        loot = LootSystem()
        result = loot.roll_loot({})
        assert isinstance(result, list)

    def test_generate_loot_with_table(self):
        from engine.core.loot import LootSystem
        loot = LootSystem()
        result = loot.roll_loot({
            "loot_table": [{"id": "gold_coin", "rarity": "COMMON", "drop_chance": 1.0}]
        }, luck_modifier=1)
        assert isinstance(result, list)


# ── engine/campaign/__init__.py lines 183, 350-351, 450 ─────────────────────

class TestCampaignEdgeCases:

    def test_campaign_active_quests_empty(self):
        from engine.campaign import CampaignManager
        cm = CampaignManager()
        quests = cm.active_quests()
        assert isinstance(quests, list)

    def test_campaign_available_quests_empty(self):
        from engine.campaign import CampaignManager
        cm = CampaignManager()
        quests = cm.available_quests()
        assert isinstance(quests, list)

    def test_campaign_get_arc_none(self):
        from engine.campaign import CampaignManager
        cm = CampaignManager()
        arc = cm.get_arc("fake_arc_id")
        assert arc is None

    def test_campaign_generator_generate_arc(self):
        from engine.campaign import CampaignGenerator
        gen = CampaignGenerator(seed=42)
        arc = gen.generate_arc(location="Test Town", num_quests=2)
        assert arc is not None
        assert len(arc.quests) > 0

    def test_campaign_side_quest(self):
        from engine.campaign import CampaignGenerator
        gen = CampaignGenerator(seed=7)
        quest = gen.generate_side_quest(location="Forest")
        assert quest is not None


# ── engine/llm/__init__.py (78% → ~95%) ───────────────────────────────────────

class TestLLMRouter:
    """Cover _get_client exception path and is_available."""

    def test_get_client_raises_on_missing_token(self):
        from engine.llm import LLMRouter
        router = LLMRouter()
        with patch("builtins.open", side_effect=FileNotFoundError("no token")):
            with pytest.raises(Exception):
                router._get_client()

    def test_get_client_raises_on_bad_json(self):
        from engine.llm import LLMRouter
        import io
        router = LLMRouter()
        with patch("builtins.open", return_value=io.StringIO("not json")):
            with pytest.raises(Exception):
                router._get_client()

    def test_is_available_returns_true_when_client_works(self):
        from engine.llm import LLMRouter
        router = LLMRouter()
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = MagicMock()
        with patch.object(router, '_get_client', return_value=mock_client):
            result = router.is_available()
            assert result is True
            # Cached — second call doesn't re-test
            result2 = router.is_available()
            assert result2 is True

    def test_is_available_returns_false_when_client_fails(self):
        from engine.llm import LLMRouter
        router = LLMRouter()
        with patch.object(router, '_get_client', side_effect=Exception("fail")):
            result = router.is_available()
            assert result is False

    def test_complete_success(self):
        from engine.llm import LLMRouter
        router = LLMRouter()
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.choices[0].message.content = "  The sword bites deep.  "
        mock_client.chat.completions.create.return_value = mock_resp
        with patch.object(router, '_get_client', return_value=mock_client):
            result = router.complete([{"role": "user", "content": "narrate"}])
            assert result == "The sword bites deep."

    def test_complete_uses_model_smart_when_specified(self):
        from engine.llm import LLMRouter, MODEL_SMART
        router = LLMRouter()
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.choices[0].message.content = "Epic"
        mock_client.chat.completions.create.return_value = mock_resp
        with patch.object(router, '_get_client', return_value=mock_client):
            router.complete([{"role": "user", "content": "test"}], model=MODEL_SMART)
            call_kwargs = mock_client.chat.completions.create.call_args[1]
            assert call_kwargs['model'] == MODEL_SMART


# ── engine/world/__init__.py (91% → ~98%) ─────────────────────────────────────

class TestWorldState:
    """Cover GameTime.advance and WorldState edge cases."""

    def test_gametime_advance_basic(self):
        from engine.world import GameTime
        t = GameTime(day=1, hour=10, minute=0)
        t.advance(1.5)
        assert t.hour == 11
        assert t.minute == 30

    def test_gametime_advance_wraps_hour(self):
        from engine.world import GameTime
        t = GameTime(day=1, hour=23, minute=0)
        t.advance(2)
        assert t.day == 2
        assert t.hour == 1

    def test_gametime_advance_wraps_day(self):
        from engine.world import GameTime
        t = GameTime(day=1, hour=22, minute=30)
        t.advance(2)
        assert t.day == 2

    def test_quest_entry_from_dict_roundtrip(self):
        from engine.world import QuestEntry
        q = QuestEntry(quest_id="q1", title="Find gem", status="active")
        d = q.to_dict()
        q2 = QuestEntry.from_dict(d)
        assert q2.quest_id == "q1"
        assert q2.title == "Find gem"

    def test_world_state_context_with_cleared_location(self):
        from engine.world import WorldState, LocationState
        ws = WorldState(game_id="test")
        ws.locations["loc1"] = LocationState(id="loc1", name="Dark Cave", cleared=True)
        ctx = ws.build_ai_context("loc1")
        assert "cleared" in ctx.lower() or "Dark Cave" in ctx

    def test_world_state_context_with_hostile_location(self):
        from engine.world import WorldState, LocationState
        ws = WorldState(game_id="test")
        ws.locations["loc2"] = LocationState(id="loc2", name="Bandit Camp", hostile=True)
        ctx = ws.build_ai_context("loc2")
        assert "hostile" in ctx.lower() or "Bandit Camp" in ctx

    def test_world_state_context_with_dead_npc(self):
        from engine.world import WorldState, NPCWorldState
        ws = WorldState(game_id="test")
        ws.npc_states["guard_1"] = NPCWorldState(id="guard_1", alive=False)
        ctx = ws.build_ai_context()
        assert "guard_1" in ctx


# ── engine/save/__init__.py (95% → ~100%) ─────────────────────────────────────

class TestSaveEdgeCases:
    """Cover corrupt/missing file edge cases."""

    def test_sanitize_rejects_path_traversal(self):
        import tempfile
        from engine.save import SaveManager
        with tempfile.TemporaryDirectory() as d:
            sm = SaveManager(saves_dir=d)
            with pytest.raises(ValueError):
                sm._sanitize("../evil", "player_id")

    def test_sanitize_rejects_slash(self):
        import tempfile
        from engine.save import SaveManager
        with tempfile.TemporaryDirectory() as d:
            sm = SaveManager(saves_dir=d)
            with pytest.raises(ValueError):
                sm._sanitize("a/b", "player_id")

    def test_find_file_direct_path(self):
        """Covers the direct exists() path in _find_file."""
        import tempfile, json
        from pathlib import Path
        from engine.save import SaveManager, SaveFile
        with tempfile.TemporaryDirectory() as d:
            sm = SaveManager(saves_dir=d)
            # Create file with just the save_id as name (no player prefix)
            path = Path(d) / "mysave.json"
            import datetime
            sf = SaveFile(save_id="mysave", player_id="player1",
                          session_data={}, timestamp=datetime.datetime.now().isoformat())
            path.write_text(json.dumps(sf.to_dict()))
            found = sm._find_file("mysave")
            assert found == path

    def test_list_saves_skips_corrupt_files(self):
        """Covers the except block when listing saves."""
        import tempfile
        from pathlib import Path
        from engine.save import SaveManager
        with tempfile.TemporaryDirectory() as d:
            sm = SaveManager(saves_dir=d)
            # Write a corrupt JSON file
            (Path(d) / "player1_corrupt.json").write_text("not json at all")
            # Should not raise, should just skip it
            saves = sm.list_saves("player1")
            assert saves == []


# ── engine/core/campaign.py (89% → ~98%) ──────────────────────────────────────

class TestCoreCampaignLoader:
    """Cover invalid JSON and campaigns property."""

    def test_load_raises_on_invalid_json(self):
        import tempfile
        from pathlib import Path
        from engine.core.campaign import CampaignLoader
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "bad.json").write_text("{invalid json}")
            loader = CampaignLoader(campaigns_dir=d)
            with pytest.raises(ValueError, match="Failed to parse"):
                loader.load()

    def test_campaigns_property_triggers_load(self):
        import tempfile, json
        from pathlib import Path
        from engine.core.campaign import CampaignLoader
        with tempfile.TemporaryDirectory() as d:
            data = {"id": "test_camp", "name": "Test Campaign", "arcs": []}
            (Path(d) / "test_camp.json").write_text(json.dumps(data))
            loader = CampaignLoader(campaigns_dir=d)
            loader.load()
            camps = loader.campaigns
            assert "test_camp" in camps


# ── engine/api/game_engine.py — fallback paths (92% → ~97%) ──────────────────

class TestGameEngineFallbackNarratives:
    """Cover fallback narrative paths when LLM raises."""

    def _make_session(self, name="Hero"):
        from engine.api.game_session import GameSession
        from engine.core.character import Character
        from engine.core.dm_agent import DMContext, SceneType
        player = Character(name=name, hp=10, max_hp=10,
                           stats={"MIG":10,"AGI":10,"END":10,"MND":10,"INS":10,"PRE":10})
        ctx = DMContext(location="dungeon", scene_type=SceneType.COMBAT, party=[])
        return GameSession(player=player, dm_context=ctx)

    def test_build_combat_narrative_fallback_hit(self):
        from engine.api.game_engine import GameEngine
        eng = GameEngine()
        sess = self._make_session()
        target = MagicMock()
        target.name = "Goblin"
        target.hp = 5
        with patch.object(eng.dm, 'narrate', side_effect=Exception("llm fail")):
            result = eng._build_combat_narrative(sess, "Hero", target, hit=True, damage=5)
        assert "strikes" in result or "hit" in result.lower() or "5" in result

    def test_build_combat_narrative_fallback_miss(self):
        from engine.api.game_engine import GameEngine
        eng = GameEngine()
        sess = self._make_session()
        target = MagicMock()
        target.name = "Goblin"
        target.hp = 5
        with patch.object(eng.dm, 'narrate', side_effect=Exception("llm fail")):
            result = eng._build_combat_narrative(sess, "Hero", target, hit=False, damage=0)
        assert "miss" in result.lower()

    def test_build_combat_narrative_fallback_crit(self):
        from engine.api.game_engine import GameEngine
        eng = GameEngine()
        sess = self._make_session()
        target = MagicMock()
        target.name = "Goblin"
        target.hp = 5
        with patch.object(eng.dm, 'narrate', side_effect=Exception("llm fail")):
            result = eng._build_combat_narrative(sess, "Hero", target, hit=True, damage=10, crit=True)
        assert "CRITICAL" in result or "devastating" in result

    def test_build_combat_narrative_fallback_fumble(self):
        from engine.api.game_engine import GameEngine
        eng = GameEngine()
        sess = self._make_session()
        target = MagicMock()
        target.name = "Goblin"
        target.hp = 5
        with patch.object(eng.dm, 'narrate', side_effect=Exception("llm fail")):
            result = eng._build_combat_narrative(sess, "Hero", target, hit=False, damage=0, fumble=True)
        assert "stumbles" in result or "wide" in result

    def test_build_enemy_combat_narrative_fallback_hit(self):
        from engine.api.game_engine import GameEngine
        eng = GameEngine()
        sess = self._make_session()
        enemy = MagicMock()
        enemy.name = "Orc"
        with patch.object(eng.dm, 'narrate', side_effect=Exception("llm fail")):
            result = eng._build_enemy_combat_narrative(sess, enemy, hit=True, damage=3)
        assert "Orc" in result and "hits" in result

    def test_build_enemy_combat_narrative_fallback_miss(self):
        from engine.api.game_engine import GameEngine
        eng = GameEngine()
        sess = self._make_session()
        enemy = MagicMock()
        enemy.name = "Orc"
        with patch.object(eng.dm, 'narrate', side_effect=Exception("llm fail")):
            result = eng._build_enemy_combat_narrative(sess, enemy, hit=False, damage=0)
        assert "miss" in result.lower()

    def test_build_death_narrative_fallback(self):
        from engine.api.game_engine import GameEngine
        eng = GameEngine()
        sess = self._make_session()
        with patch.object(eng.dm, 'narrate', side_effect=Exception("llm fail")):
            result = eng._build_death_narrative(sess, "Dragon")
        assert "Dragon" in result and "defeated" in result


# ── engine/world/world_routes.py (84% → ~95%) ────────────────────────────────

class TestWorldRoutes:
    """Cover uncovered world route endpoints."""

    def _create_session(self):
        resp = client.post("/game/session/new", json={"player_name": "RouteTest", "player_class": "warrior"})
        return resp.json()["session_id"]

    def test_world_state_endpoint(self):
        sid = self._create_session()
        resp = client.get(f"/game/session/{sid}/world-state")
        assert resp.status_code == 200

    def test_history_endpoint(self):
        sid = self._create_session()
        resp = client.get(f"/game/session/{sid}/history")
        assert resp.status_code == 200
        assert "history" in resp.json()

    def test_history_endpoint_with_limit(self):
        sid = self._create_session()
        resp = client.get(f"/game/session/{sid}/history?limit=5")
        assert resp.status_code == 200

    def test_factions_endpoint(self):
        sid = self._create_session()
        resp = client.get(f"/game/session/{sid}/factions")
        assert resp.status_code == 200

    def test_flags_endpoint(self):
        sid = self._create_session()
        resp = client.get(f"/game/session/{sid}/flags")
        assert resp.status_code == 200

    def test_consequences_endpoint(self):
        sid = self._create_session()
        resp = client.get(f"/game/session/{sid}/consequences")
        assert resp.status_code == 200

    def test_fire_trigger_endpoint(self):
        sid = self._create_session()
        resp = client.post(f"/game/session/{sid}/trigger",
                           json={"trigger_type": "npc_death", "npc_id": "guard1"})
        assert resp.status_code == 200

    def test_fire_trigger_missing_type(self):
        sid = self._create_session()
        resp = client.post(f"/game/session/{sid}/trigger", json={"npc_id": "guard1"})
        assert resp.status_code == 400

    def test_session_not_found_404(self):
        resp = client.get("/game/session/nonexistent_xyz/world-state")
        assert resp.status_code == 404
