"""
Ember RPG - Core Engine
AI DM Agent tests
"""
import pytest
from engine.core.dm_agent import (
    DMAIAgent, DMContext, DMEvent, SceneType, EventType
)
from engine.core.character import Character


@pytest.fixture
def party():
    return [
        Character(name="Aria", level=3, hp=28, max_hp=28, classes={"warrior": 3}),
        Character(name="Kael", level=3, hp=18, max_hp=18, spell_points=12,
                  max_spell_points=12, classes={"mage": 3}),
    ]


@pytest.fixture
def exploration_context(party):
    return DMContext(
        scene_type=SceneType.EXPLORATION,
        location="Dark Forest",
        party=party,
    )


class TestDMContext:
    """Test DMContext creation and management."""

    def test_context_creation(self, exploration_context, party):
        ctx = exploration_context
        assert ctx.scene_type == SceneType.EXPLORATION
        assert ctx.location == "Dark Forest"
        assert len(ctx.party) == 2
        assert ctx.turn == 0
        assert ctx.history == []

    def test_add_event(self, exploration_context):
        ctx = exploration_context
        event = DMEvent(type=EventType.DISCOVERY, description="You find ancient ruins.")
        ctx.add_event(event)

        assert len(ctx.history) == 1
        assert ctx.history[0].description == "You find ancient ruins."

    def test_history_trimmed_to_max(self, exploration_context):
        ctx = exploration_context
        ctx.max_history = 3

        for i in range(5):
            ctx.add_event(DMEvent(type=EventType.DISCOVERY, description=f"Event {i}"))

        assert len(ctx.history) == 3
        # Most recent events kept
        assert ctx.history[-1].description == "Event 4"

    def test_turn_increments(self, exploration_context):
        ctx = exploration_context
        ctx.advance_turn()
        assert ctx.turn == 1
        ctx.advance_turn()
        assert ctx.turn == 2

    def test_party_summary(self, exploration_context):
        summary = exploration_context.party_summary()
        assert "Aria" in summary
        assert "Kael" in summary


class TestSceneTransitions:
    """Test scene state machine."""

    def test_valid_transition_exploration_to_combat(self, exploration_context):
        agent = DMAIAgent()
        result = agent.transition(exploration_context, SceneType.COMBAT)
        assert result is True
        assert exploration_context.scene_type == SceneType.COMBAT

    def test_valid_transition_combat_to_exploration(self, party):
        ctx = DMContext(scene_type=SceneType.COMBAT, location="Dungeon", party=party)
        agent = DMAIAgent()
        result = agent.transition(ctx, SceneType.EXPLORATION)
        assert result is True

    def test_valid_transition_exploration_to_rest(self, exploration_context):
        agent = DMAIAgent()
        result = agent.transition(exploration_context, SceneType.REST)
        assert result is True

    def test_invalid_transition_rest_to_combat(self, party):
        ctx = DMContext(scene_type=SceneType.REST, location="Camp", party=party)
        agent = DMAIAgent()
        with pytest.raises(ValueError, match="Invalid transition"):
            agent.transition(ctx, SceneType.COMBAT)

    def test_invalid_transition_combat_to_rest(self, party):
        ctx = DMContext(scene_type=SceneType.COMBAT, location="Dungeon", party=party)
        agent = DMAIAgent()
        with pytest.raises(ValueError, match="Invalid transition"):
            agent.transition(ctx, SceneType.REST)

    def test_same_state_transition_is_valid(self, exploration_context):
        """Transitioning to the same state is always allowed."""
        agent = DMAIAgent()
        result = agent.transition(exploration_context, SceneType.EXPLORATION)
        assert result is True


class TestPromptBuilder:
    """Test LLM prompt construction."""

    def test_prompt_is_string(self, exploration_context):
        agent = DMAIAgent()
        event = DMEvent(type=EventType.ENCOUNTER, description="A goblin steps out of the shadows.")
        prompt = agent.build_prompt(event, exploration_context)
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_prompt_contains_location(self, exploration_context):
        agent = DMAIAgent()
        event = DMEvent(type=EventType.ENCOUNTER, description="Wolves howl nearby.")
        prompt = agent.build_prompt(event, exploration_context)
        assert "Dark Forest" in prompt

    def test_prompt_contains_party_names(self, exploration_context):
        agent = DMAIAgent()
        event = DMEvent(type=EventType.DISCOVERY, description="You find a chest.")
        prompt = agent.build_prompt(event, exploration_context)
        assert "Aria" in prompt
        assert "Kael" in prompt

    def test_prompt_contains_event_description(self, exploration_context):
        agent = DMAIAgent()
        event = DMEvent(type=EventType.COMBAT_END, description="The orc falls dead.")
        prompt = agent.build_prompt(event, exploration_context)
        assert "The orc falls dead." in prompt

    def test_prompt_includes_history(self, exploration_context):
        agent = DMAIAgent()
        exploration_context.add_event(
            DMEvent(type=EventType.DISCOVERY, description="Ancient inscription found.")
        )
        event = DMEvent(type=EventType.ENCOUNTER, description="A shadow moves.")
        prompt = agent.build_prompt(event, exploration_context)
        assert "Ancient inscription found." in prompt


class TestNarrate:
    """Test narrative generation."""

    def test_narrate_without_llm_returns_string(self, exploration_context):
        agent = DMAIAgent()
        event = DMEvent(type=EventType.ENCOUNTER, description="A goblin appears.")
        result = agent.narrate(event, exploration_context)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_narrate_with_mock_llm(self, exploration_context):
        agent = DMAIAgent()
        event = DMEvent(type=EventType.COMBAT_END, description="Victory!")

        def mock_llm(prompt: str) -> str:
            return "The battle is won. Your party stands victorious."

        result = agent.narrate(event, exploration_context, llm=mock_llm)
        assert result == "The battle is won. Your party stands victorious."

    def test_narrate_adds_to_history(self, exploration_context):
        agent = DMAIAgent()
        event = DMEvent(type=EventType.ITEM_FOUND, description="A glowing sword.")
        agent.narrate(event, exploration_context)
        assert len(exploration_context.history) == 1

    def test_narrate_combat_end_event(self, party):
        ctx = DMContext(scene_type=SceneType.COMBAT, location="Arena", party=party)
        agent = DMAIAgent()
        event = DMEvent(
            type=EventType.COMBAT_END,
            description="The dragon collapses.",
            data={"winner": "party", "rounds": 5}
        )
        result = agent.narrate(event, ctx)
        assert isinstance(result, str)


class TestDMEvent:
    """Test DMEvent creation."""

    def test_event_creation(self):
        event = DMEvent(type=EventType.ENCOUNTER, description="Wolves appear.")
        assert event.type == EventType.ENCOUNTER
        assert event.description == "Wolves appear."
        assert event.data == {}

    def test_event_with_data(self):
        event = DMEvent(
            type=EventType.LEVEL_UP,
            description="Aria reaches level 4!",
            data={"character": "Aria", "new_level": 4}
        )
        assert event.data["new_level"] == 4
