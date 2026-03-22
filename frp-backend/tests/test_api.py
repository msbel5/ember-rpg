"""
Ember RPG - API Layer Tests
ActionParser, GameSession, GameEngine
"""
import pytest
from engine.api.action_parser import ActionParser, ActionIntent, ParsedAction
from engine.api.game_session import GameSession
from engine.api.game_engine import GameEngine
from engine.core.character import Character
from engine.core.dm_agent import SceneType


class TestActionParser:
    """Test natural language → intent parsing."""

    def setup_method(self):
        self.parser = ActionParser()

    # Attack
    def test_attack_english(self):
        result = self.parser.parse("attack the goblin")
        assert result.intent == ActionIntent.ATTACK

    def test_attack_turkish(self):
        result = self.parser.parse("ejderhaya saldırıyorum")
        assert result.intent == ActionIntent.ATTACK

    def test_attack_short_turkish(self):
        result = self.parser.parse("orka saldır")
        assert result.intent == ActionIntent.ATTACK

    def test_attack_kill_keyword(self):
        result = self.parser.parse("goblin'i öldür")
        assert result.intent == ActionIntent.ATTACK

    # Spell
    def test_spell_turkish(self):
        result = self.parser.parse("ateş büyüsü atıyorum")
        assert result.intent == ActionIntent.CAST_SPELL

    def test_spell_english(self):
        result = self.parser.parse("cast fireball at the orc")
        assert result.intent == ActionIntent.CAST_SPELL

    def test_spell_heal(self):
        result = self.parser.parse("heal the warrior")
        assert result.intent == ActionIntent.CAST_SPELL

    # Talk
    def test_talk_turkish(self):
        result = self.parser.parse("tüccarla konuşuyorum")
        assert result.intent == ActionIntent.TALK

    def test_talk_english(self):
        result = self.parser.parse("talk to the merchant")
        assert result.intent == ActionIntent.TALK

    def test_talk_negotiate(self):
        result = self.parser.parse("pazarlık yapmak istiyorum")
        assert result.intent == ActionIntent.TALK

    # Examine
    def test_examine_turkish(self):
        result = self.parser.parse("odayı inceliyorum")
        assert result.intent == ActionIntent.EXAMINE

    def test_examine_english(self):
        result = self.parser.parse("look around the room")
        assert result.intent == ActionIntent.EXAMINE

    # Rest
    def test_rest_turkish(self):
        result = self.parser.parse("dinlenmek istiyorum")
        assert result.intent == ActionIntent.REST

    def test_rest_english(self):
        result = self.parser.parse("rest and recover")
        assert result.intent == ActionIntent.REST

    # Move
    def test_move_turkish(self):
        result = self.parser.parse("kuzey kapısına gidiyorum")
        assert result.intent == ActionIntent.MOVE

    def test_move_english(self):
        result = self.parser.parse("move to the north door")
        assert result.intent == ActionIntent.MOVE

    # Open
    def test_open_turkish(self):
        result = self.parser.parse("kapıyı açıyorum")
        assert result.intent == ActionIntent.OPEN

    def test_open_english(self):
        result = self.parser.parse("open the chest")
        assert result.intent == ActionIntent.OPEN

    # Unknown
    def test_unknown_gibberish(self):
        result = self.parser.parse("xyzzy plugh frobble")
        assert result.intent == ActionIntent.UNKNOWN

    def test_unknown_empty(self):
        result = self.parser.parse("")
        assert result.intent == ActionIntent.UNKNOWN

    # ParsedAction structure
    def test_returns_parsed_action(self):
        result = self.parser.parse("gobline saldır")
        assert isinstance(result, ParsedAction)
        assert result.raw_input == "gobline saldır"

    def test_target_extraction(self):
        result = self.parser.parse("gobline saldırıyorum")
        # Should extract some target
        assert result.target is not None


class TestGameSession:
    """Test GameSession creation and state."""

    def test_session_has_id(self):
        player = Character(name="Aria")
        from engine.core.dm_agent import DMContext, SceneType
        ctx = DMContext(scene_type=SceneType.EXPLORATION, location="Test", party=[player])
        session = GameSession(player=player, dm_context=ctx)
        assert session.session_id is not None
        assert len(session.session_id) == 36  # UUID format

    def test_session_not_in_combat(self):
        player = Character(name="Aria")
        from engine.core.dm_agent import DMContext
        ctx = DMContext(scene_type=SceneType.EXPLORATION, location="Test", party=[player])
        session = GameSession(player=player, dm_context=ctx)
        assert session.in_combat() is False

    def test_session_to_dict(self):
        player = Character(name="Aria", level=1, hp=20, max_hp=20)
        from engine.core.dm_agent import DMContext
        ctx = DMContext(scene_type=SceneType.EXPLORATION, location="Forest", party=[player])
        session = GameSession(player=player, dm_context=ctx)
        d = session.to_dict()
        assert d["player"]["name"] == "Aria"
        assert d["scene"] == "exploration"
        assert d["location"] == "Forest"

    def test_session_touch_updates_timestamp(self):
        player = Character(name="Aria")
        from engine.core.dm_agent import DMContext
        ctx = DMContext(scene_type=SceneType.EXPLORATION, location="Test", party=[player])
        session = GameSession(player=player, dm_context=ctx)
        old_ts = session.last_action
        import time; time.sleep(0.01)
        session.touch()
        assert session.last_action >= old_ts


class TestGameEngine:
    """Test GameEngine orchestration."""

    def setup_method(self):
        self.engine = GameEngine()

    def test_new_session_returns_session(self):
        session = self.engine.new_session("Aria")
        assert session is not None
        assert session.player.name == "Aria"

    def test_new_session_default_class(self):
        session = self.engine.new_session("Aria")
        assert "warrior" in session.player.classes

    def test_new_session_mage_class(self):
        session = self.engine.new_session("Kael", "mage")
        assert "mage" in session.player.classes
        assert session.player.max_spell_points > 0

    def test_new_session_exploration_scene(self):
        session = self.engine.new_session("Aria")
        assert session.dm_context.scene_type == SceneType.EXPLORATION

    def test_new_session_custom_location(self):
        session = self.engine.new_session("Aria", location="Dark Tower")
        assert session.dm_context.location == "Dark Tower"

    def test_process_examine_action(self):
        session = self.engine.new_session("Aria")
        result = self.engine.process_action(session, "odayı inceliyorum")
        assert isinstance(result.narrative, str)
        assert len(result.narrative) > 0

    def test_process_move_action(self):
        session = self.engine.new_session("Aria")
        result = self.engine.process_action(session, "kuzey kapısına gidiyorum")
        assert result.narrative

    def test_process_talk_action(self):
        session = self.engine.new_session("Aria")
        result = self.engine.process_action(session, "tüccarla konuş")
        assert result.narrative
        assert result.scene_type == SceneType.DIALOGUE

    def test_process_rest_action(self):
        session = self.engine.new_session("Aria")
        session.player.hp = 5  # Damage player first
        result = self.engine.process_action(session, "dinlenmek istiyorum")
        assert result.narrative
        assert session.player.hp > 5  # HP restored

    def test_process_attack_triggers_combat(self):
        session = self.engine.new_session("Aria", "warrior")
        result = self.engine.process_action(session, "goblina saldırıyorum")
        assert result.narrative
        # Combat starts or was already handled

    def test_process_unknown_action(self):
        session = self.engine.new_session("Aria")
        result = self.engine.process_action(session, "xyzzy plugh")
        assert result.narrative
        assert "anlayamadım" in result.narrative

    def test_turn_advances_on_action(self):
        session = self.engine.new_session("Aria")
        initial_turn = session.dm_context.turn
        self.engine.process_action(session, "odayı incele")
        assert session.dm_context.turn == initial_turn + 1

    def test_narrate_with_mock_llm(self):
        mock_responses = []

        def mock_llm(prompt):
            mock_responses.append(prompt)
            return "LLM yanıtı."

        engine = GameEngine(llm=mock_llm)
        session = engine.new_session("Aria")
        result = engine.process_action(session, "odayı incele")
        assert result.narrative == "LLM yanıtı."
        assert len(mock_responses) == 1

    def test_rest_restores_spell_points(self):
        session = self.engine.new_session("Kael", "mage")
        session.player.spell_points = 0  # Drain spell points
        self.engine.process_action(session, "dinlen")
        assert session.player.spell_points == session.player.max_spell_points

    def test_rest_not_allowed_in_combat(self):
        session = self.engine.new_session("Aria", "warrior")
        # Force combat state
        enemy = Character(name="Goblin", hp=10, max_hp=10)
        self.engine._start_combat(session, [enemy])
        result = self.engine.process_action(session, "dinlenmek istiyorum")
        assert "savaşın ortasında" in result.narrative.lower()
