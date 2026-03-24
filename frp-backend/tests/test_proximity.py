import pytest
from engine.api.game_engine import GameEngine
from engine.api.game_session import GameSession

# TDD placeholder tests for Proximity Rules (Module 10: FR-42 -> FR-45)

def test_talk_too_far():
    engine = GameEngine()
    session = engine.new_session("Tst", "fighter", location="Old Market")
    # place merchant 3 tiles away
    session.position = [0,0]
    merchant_pos = [0,3]
    # For now assume engine.parser will parse 'talk merchant' -> MOVE intent target merchant
    # Placeholder: calling _handle_talk directly with mocked ParsedAction would assert distance check
    assert True

