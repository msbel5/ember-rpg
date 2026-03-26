"""
Tests for the Smart Action Parser (Deliverable 1)
"""
import pytest
from engine.api.action_parser import ActionParser, ActionIntent, ParsedAction


@pytest.fixture
def parser():
    return ActionParser()


# --- LOOK ---
def test_look_around(parser):
    result = parser.parse("look around")
    assert result.intent == ActionIntent.LOOK

def test_look_simple(parser):
    result = parser.parse("look")
    assert result.intent == ActionIntent.LOOK

def test_look_turkish(parser):
    result = parser.parse("etrafına bak")
    assert result.intent == ActionIntent.LOOK

def test_look_at_target(parser):
    result = parser.parse("look door")
    assert result.intent == ActionIntent.LOOK
    assert result.target == "door"


# --- OPEN / INTERACT ---
def test_open_chest(parser):
    result = parser.parse("open chest")
    assert result.intent == ActionIntent.OPEN
    assert result.target == "chest"

def test_open_door(parser):
    result = parser.parse("open door")
    assert result.intent == ActionIntent.OPEN
    assert result.target == "door"

def test_open_turkish(parser):
    result = parser.parse("aç sandığı")
    assert result.intent == ActionIntent.OPEN

def test_open_turkish_object_first(parser):
    result = parser.parse("kapıyı aç")
    assert result.intent == ActionIntent.OPEN
    assert result.target == "kapı"


# --- TALK ---
def test_talk_to_guard(parser):
    result = parser.parse("talk to guard")
    assert result.intent == ActionIntent.TALK
    assert result.target == "guard"

def test_speak_with_innkeeper(parser):
    result = parser.parse("speak with innkeeper")
    assert result.intent == ActionIntent.TALK
    assert result.target == "innkeeper"

def test_talk_turkish(parser):
    result = parser.parse("konuş muhafız")
    assert result.intent == ActionIntent.TALK

def test_talk_turkish_instrumental_target(parser):
    result = parser.parse("muhafızla konuş")
    assert result.intent == ActionIntent.TALK
    assert result.target == "muhafız"


# --- CAST_SPELL ---
def test_cast_fireball_at_goblin(parser):
    result = parser.parse("cast fireball at goblin")
    assert result.intent == ActionIntent.CAST_SPELL
    assert result.spell_name == "fireball"
    assert result.target == "goblin"

def test_cast_simple(parser):
    result = parser.parse("cast lightning bolt")
    assert result.intent == ActionIntent.CAST_SPELL
    assert result.spell_name == "lightning bolt"

def test_cast_turkish(parser):
    result = parser.parse("büyü yap ateş topu gobline")
    assert result.intent == ActionIntent.CAST_SPELL


# --- ATTACK ---
def test_attack_orc_with_sword(parser):
    result = parser.parse("attack orc with sword")
    assert result.intent == ActionIntent.ATTACK
    assert result.target == "orc"
    assert result.weapon == "sword"

def test_attack_simple(parser):
    result = parser.parse("attack goblin")
    assert result.intent == ActionIntent.ATTACK
    assert result.target == "goblin"

def test_attack_turkish(parser):
    result = parser.parse("saldır ork")
    assert result.intent == ActionIntent.ATTACK

def test_attack_turkish_inflected_target(parser):
    result = parser.parse("gobline saldırıyorum")
    assert result.intent == ActionIntent.ATTACK
    assert result.target == "goblin"


# --- PICKUP ---
def test_pick_up_health_potion(parser):
    result = parser.parse("pick up health potion")
    assert result.intent in (ActionIntent.PICKUP, ActionIntent.PICK_UP)
    assert "potion" in result.target

def test_take_potion(parser):
    result = parser.parse("take potion")
    assert result.intent in (ActionIntent.PICKUP, ActionIntent.PICK_UP)
    assert result.target == "potion"

def test_pickup_turkish(parser):
    result = parser.parse("al iksir")
    assert result.intent in (ActionIntent.PICKUP, ActionIntent.PICK_UP)


# --- USE_ITEM ---
def test_use_healing_potion(parser):
    result = parser.parse("use healing potion")
    assert result.intent == ActionIntent.USE_ITEM
    assert "potion" in result.target

def test_drink_potion(parser):
    result = parser.parse("drink potion")
    assert result.intent == ActionIntent.USE_ITEM
    assert result.target == "potion"

def test_use_item_turkish(parser):
    result = parser.parse("kullan iksir")
    assert result.intent == ActionIntent.USE_ITEM

def test_iç_turkish(parser):
    result = parser.parse("iç iksiri")
    assert result.intent == ActionIntent.USE_ITEM


# --- MOVE ---
def test_go_north(parser):
    result = parser.parse("go north")
    assert result.intent == ActionIntent.MOVE
    assert result.direction == "north"

def test_move_to_dungeon(parser):
    result = parser.parse("move to dungeon")
    assert result.intent == ActionIntent.MOVE

def test_enter_cave(parser):
    result = parser.parse("enter cave")
    assert result.intent == ActionIntent.MOVE

def test_move_turkish(parser):
    result = parser.parse("git kuzey")
    assert result.intent == ActionIntent.MOVE

def test_direction_only(parser):
    result = parser.parse("north")
    assert result.intent == ActionIntent.MOVE
    assert result.direction == "north"


# --- INVENTORY ---
def test_check_inventory(parser):
    result = parser.parse("check inventory")
    assert result.intent == ActionIntent.INVENTORY

def test_show_items(parser):
    result = parser.parse("show items")
    assert result.intent == ActionIntent.INVENTORY

def test_inventory_turkish(parser):
    result = parser.parse("eşyalarım")
    assert result.intent == ActionIntent.INVENTORY


# --- FLEE ---
def test_run_away(parser):
    result = parser.parse("run away")
    assert result.intent == ActionIntent.FLEE

def test_flee(parser):
    result = parser.parse("flee")
    assert result.intent == ActionIntent.FLEE

def test_escape(parser):
    result = parser.parse("escape")
    assert result.intent == ActionIntent.FLEE

def test_flee_turkish(parser):
    result = parser.parse("kaç")
    assert result.intent == ActionIntent.FLEE


# --- REST ---
def test_rest(parser):
    result = parser.parse("rest")
    assert result.intent == ActionIntent.REST

def test_sleep(parser):
    result = parser.parse("sleep")
    assert result.intent == ActionIntent.LONG_REST

def test_short_rest(parser):
    result = parser.parse("short rest")
    assert result.intent == ActionIntent.SHORT_REST

def test_disengage(parser):
    result = parser.parse("disengage")
    assert result.intent == ActionIntent.DISENGAGE

def test_bribe_guard(parser):
    result = parser.parse("bribe guard")
    assert result.intent == ActionIntent.BRIBE
    assert result.target == "guard"

def test_deceive_merchant(parser):
    result = parser.parse("deceive merchant")
    assert result.intent == ActionIntent.DECEIVE
    assert result.target == "merchant"

def test_think_history(parser):
    result = parser.parse("what do i know about this town")
    assert result.intent == ActionIntent.THINK

def test_address_target(parser):
    result = parser.parse("say to merchant keep this quiet")
    assert result.intent == ActionIntent.ADDRESS
    assert result.target == "merchant"


# --- QUESTS ---
def test_accept_quest_with_title(parser):
    result = parser.parse("accept quest bread shortage")
    assert result.intent == ActionIntent.ACCEPT_QUEST
    assert result.target == "bread shortage"

def test_accept_quest_turkish(parser):
    result = parser.parse("görevi kabul et ekmek kıtlığı")
    assert result.intent == ActionIntent.ACCEPT_QUEST

def test_turn_in_quest_with_title(parser):
    result = parser.parse("turn in quest bread shortage")
    assert result.intent == ActionIntent.TURN_IN_QUEST
    assert result.target == "bread shortage"

def test_turn_in_quest_turkish(parser):
    result = parser.parse("görevi teslim et ekmek kıtlığı")
    assert result.intent == ActionIntent.TURN_IN_QUEST


# --- UNKNOWN ---
def test_unknown(parser):
    result = parser.parse("xyzzy plugh foo bar")
    assert result.intent == ActionIntent.UNKNOWN

def test_examine_turkish_object_first(parser):
    result = parser.parse("sandığı incele")
    assert result.intent == ActionIntent.EXAMINE
    assert result.target == "sandık"

def test_steal_turkish_ablative_target(parser):
    result = parser.parse("merchanttan çal")
    assert result.intent == ActionIntent.STEAL
    assert result.target == "merchant"

def test_raw_input_preserved(parser):
    result = parser.parse("Attack the Orc!")
    assert result.raw_input == "Attack the Orc!"
    assert result.raw_text == "Attack the Orc!"

def test_parsed_action_fields(parser):
    result = parser.parse("cast fireball at goblin")
    assert isinstance(result, ParsedAction)
    assert result.spell_name is not None
    assert result.target is not None
    assert result.raw_input is not None


# --- Legacy _detect_intent ---
def test_detect_intent_legacy(parser):
    """Legacy _detect_intent method should still work."""
    result = parser._detect_intent("attack the goblin")
    assert result == ActionIntent.ATTACK

def test_detect_intent_unknown_legacy(parser):
    """Legacy _detect_intent returns UNKNOWN for unrecognized text."""
    result = parser._detect_intent("xyzzy plugh")
    assert result == ActionIntent.UNKNOWN

def test_extract_after_keyword_not_found(parser):
    """_extract_after_keyword returns None if keyword not in string."""
    result = parser._extract_after_keyword("attack goblin", "cast")
    assert result is None
