"""
Ember RPG - API Layer
Action Parser: natural language → structured game intent
Supports Turkish and English input.
"""
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum
import re


class ActionIntent(Enum):
    """Player action intents."""
    ATTACK = "attack"
    CAST_SPELL = "cast_spell"
    USE_ITEM = "use_item"
    PICKUP = "pickup"
    MOVE = "move"
    TALK = "talk"
    LOOK = "look"
    EXAMINE = "examine"
    REST = "rest"
    OPEN = "open"
    INTERACT = "interact"
    INVENTORY = "inventory"
    FLEE = "flee"
    UNKNOWN = "unknown"


@dataclass
class ParsedAction:
    """
    Structured representation of a player's natural language input.

    Attributes:
        intent: What the player wants to do
        target: Target entity name (extracted from input)
        spell_name: Spell name if CAST_SPELL
        weapon: Weapon name if ATTACK with weapon
        direction: Direction/location if MOVE
        action_detail: Legacy field (weapon, spell name, or other detail)
        raw_input: Original player text (also accessible as raw_text)
    """
    intent: ActionIntent
    raw_input: str
    target: Optional[str] = None
    spell_name: Optional[str] = None
    weapon: Optional[str] = None
    direction: Optional[str] = None
    action_detail: Optional[str] = None

    @property
    def raw_text(self) -> str:
        """Alias for raw_input."""
        return self.raw_input


def _normalize(text: str) -> str:
    """Lowercase and strip punctuation."""
    return re.sub(r"[^\w\s]", " ", text.lower()).strip()


# ---------------------------------------------------------------------------
# Regex-based patterns (priority order: most specific first)
# Named capture groups: target, spell, weapon, direction
# ---------------------------------------------------------------------------

_PATTERNS: list[tuple[ActionIntent, list[re.Pattern]]] = [
    # CAST_SPELL: "cast fireball at goblin" / "büyü ateş topu gobline"
    (ActionIntent.CAST_SPELL, [
        re.compile(
            r"^(?:cast|use spell|büyü yap|büyü at)\s+(?P<spell>[\w\s]+?)\s+(?:at|on|üzerinde|üstüne|hedef)\s+(?P<target>[\w\s]+)$",
            re.IGNORECASE
        ),
        re.compile(
            r"^(?:cast|sihir|büyü)\s+(?P<spell>[\w\s]+)$",
            re.IGNORECASE
        ),
        re.compile(
            r"^(?P<spell>fireball|lightning bolt|heal|icebolt|şimşek|ateş topu|buz oku)\s+(?:at|on|üzerinde)?\s*(?P<target>[\w\s]*)$",
            re.IGNORECASE
        ),
    ]),

    # ATTACK with weapon: "attack orc with sword"
    (ActionIntent.ATTACK, [
        re.compile(
            r"^(?:attack|saldır|vur|hit|strike|slash|stab|fight)\s+(?P<target>[\w\s]+?)\s+(?:with|using|ile)\s+(?P<weapon>[\w\s]+)$",
            re.IGNORECASE
        ),
        re.compile(
            r"^(?:attack|saldır|vur|hit|strike|slash|stab|fight|öldür|kesivur|çarp|hücum)\s+(?P<target>[\w\s]+)$",
            re.IGNORECASE
        ),
    ]),

    # TALK: "talk to guard" / "speak with innkeeper" / "konuş muhafızla"
    (ActionIntent.TALK, [
        re.compile(
            r"^(?:talk\s+to|speak\s+(?:to|with)|chat\s+with|greet|konuş|selamla|söyle|sor|pazarlık)\s+(?P<target>[\w\s]+)$",
            re.IGNORECASE
        ),
    ]),

    # PICKUP: "pick up health potion" / "take potion" / "al iksiri"
    (ActionIntent.PICKUP, [
        re.compile(
            r"^(?:pick\s+up|take|grab|collect|al|topla|kaldır)\s+(?P<target>[\w\s]+)$",
            re.IGNORECASE
        ),
    ]),

    # USE_ITEM: "use healing potion" / "drink potion" / "eat food" / "içtim iksiri"
    (ActionIntent.USE_ITEM, [
        re.compile(
            r"^(?:use|drink|eat|consume|apply|kullan|iç|ye|uygula)\s+(?P<target>[\w\s]+)$",
            re.IGNORECASE
        ),
    ]),

    # LOOK: "look around" / "look" / "etrafına bak"
    (ActionIntent.LOOK, [
        re.compile(
            r"^(?:look(?:\s+around)?|gaze|survey|etrafına?\s+bak|bak(?:\s+etraf)?|çevreye\s+bak)$",
            re.IGNORECASE
        ),
    ]),

    # EXAMINE: "look around the room" / "examine door" / "inspect chest" / "search room" / "incele"
    (ActionIntent.EXAMINE, [
        re.compile(
            r"^(?:look\s+around\s+the)\s+(?P<target>[\w\s]+)$",
            re.IGNORECASE
        ),
        re.compile(
            r"^(?:examine|inspect|study|check\s+out|search|investigate|incele|ara|kontrol\s+et|gözlemle)\s+(?P<target>[\w\s]+)$",
            re.IGNORECASE
        ),
        re.compile(
            r"^(?:[\w\s]+\s+)?(?:inceliyorum|bakıyorum|arıyorum)\s*(?P<target>[\w\s]*)$",
            re.IGNORECASE
        ),
    ]),

    # OPEN: "open chest" / "unlock door" / "aç sandığı"
    (ActionIntent.OPEN, [
        re.compile(
            r"^(?:open|unlock|force\s+open|break\s+open|aç|kır|zorla|sök)\s+(?P<target>[\w\s]+)$",
            re.IGNORECASE
        ),
    ]),

    # INTERACT: "interact with lever" / "use lever" (generic interaction)
    (ActionIntent.INTERACT, [
        re.compile(
            r"^(?:interact\s+with|use|push|pull|turn|activate|press|etkileş|kullan|it|çek|çevir|aktive)\s+(?P<target>[\w\s]+)$",
            re.IGNORECASE
        ),
    ]),

    # FLEE: "run away" / "flee" / "escape" / "kaç"
    (ActionIntent.FLEE, [
        re.compile(
            r"^(?:run\s+away|flee|escape|retreat|withdraw|bolt|kaç|geri\s+çekil|çekil|kaçmak)$",
            re.IGNORECASE
        ),
    ]),

    # INVENTORY: "check inventory" / "show items" / "eşyalarım"
    (ActionIntent.INVENTORY, [
        re.compile(
            r"^(?:check\s+inventory|show\s+inventory|open\s+inventory|inventory|show\s+items|list\s+items|my\s+items|eşyalarım|çantam|envanterim)$",
            re.IGNORECASE
        ),
    ]),

    # REST: "rest" / "sleep" / "camp" / "dinlen"
    (ActionIntent.REST, [
        re.compile(
            r"^(?:rest(?:\s+and\s+recover)?|sleep|camp|make\s+camp|wait|dinlen|uyu|kamp\s+kur|mola\s+ver)$",
            re.IGNORECASE
        ),
        re.compile(
            r"^(?:[\w\s]+\s+)?(?:dinlenmek|uyumak)\s+(?:istiyorum|istiyom)?$",
            re.IGNORECASE
        ),
        re.compile(
            r"^rest\s+and\s+[\w\s]+$",
            re.IGNORECASE
        ),
    ]),

    # MOVE: "go north" / "move to dungeon" / "enter cave" / "git kuzey"
    (ActionIntent.MOVE, [
        re.compile(
            r"^(?:go|move\s+to|travel\s+to|head\s+to|enter|walk\s+to|git|gidin|ilerle|gidiyorum|yürü)\s+(?P<direction>[\w\s]+)$",
            re.IGNORECASE
        ),
        re.compile(
            r"^(?:[\w\s]+\s+)?(?:gidiyorum|gidelim|gidecek)\s*(?P<direction>[\w\s]*)$",
            re.IGNORECASE
        ),
        re.compile(
            r"^(?P<direction>north|south|east|west|up|down|kuzey|güney|doğu|batı|yukarı|aşağı)$",
            re.IGNORECASE
        ),
    ]),
]

# Fallback keyword map (used when no regex matches)
_KEYWORD_FALLBACK: list[tuple[ActionIntent, list[str]]] = [
    (ActionIntent.FLEE, ["run away", "flee", "escape", "retreat", "kaç", "geri çekil"]),
    (ActionIntent.INVENTORY, ["inventory", "items", "pack", "bag", "eşya", "envanter", "çanta"]),
    (ActionIntent.LOOK, ["look", "bak", "etraf"]),
    (ActionIntent.ATTACK, ["saldır", "vur", "öldür", "attack", "strike", "hit", "kill"]),
    (ActionIntent.CAST_SPELL, ["büyü", "sihir", "cast", "spell", "magic", "fireball", "heal"]),
    (ActionIntent.USE_ITEM, ["kullan", "iç", "ye", "use", "drink", "eat", "consume", "potion"]),
    (ActionIntent.TALK, ["konuş", "söyle", "talk", "speak", "greet"]),
    (ActionIntent.REST, ["dinlen", "uyu", "rest", "sleep", "camp"]),
    (ActionIntent.OPEN, ["aç", "kır", "open", "unlock"]),
    (ActionIntent.MOVE, ["git", "go", "move", "walk", "enter", "travel"]),
    (ActionIntent.EXAMINE, ["incele", "ara", "examine", "inspect", "search", "check"]),
    (ActionIntent.PICKUP, ["al", "topla", "take", "pick up", "grab"]),
]


class ActionParser:
    """
    Parse natural language player input into structured game actions.

    Supports Turkish and English. Uses regex patterns with named capture groups.
    Unknown inputs return ActionIntent.UNKNOWN for DM fallback handling.

    Usage:
        parser = ActionParser()
        action = parser.parse("attack orc with sword")
        # action.intent == ActionIntent.ATTACK
        # action.target == "orc"
        # action.weapon == "sword"
    """

    def parse(self, text: str) -> ParsedAction:
        """
        Parse player input into a ParsedAction.

        Args:
            text: Raw player input string

        Returns:
            ParsedAction with intent, target, spell_name, weapon, direction, raw_input
        """
        stripped = text.strip()
        normalized = _normalize(stripped)

        # Try regex patterns in priority order
        for intent, patterns in _PATTERNS:
            for pattern in patterns:
                m = pattern.match(normalized)
                if m:
                    groups = m.groupdict()
                    target = groups.get("target") or None
                    spell_name = groups.get("spell") or None
                    weapon = groups.get("weapon") or None
                    direction = groups.get("direction") or None

                    # Clean up captured groups
                    if target:
                        target = target.strip()
                    if spell_name:
                        spell_name = spell_name.strip()
                    if weapon:
                        weapon = weapon.strip()
                    if direction:
                        direction = direction.strip()

                    return ParsedAction(
                        intent=intent,
                        raw_input=stripped,
                        target=target if target else None,
                        spell_name=spell_name,
                        weapon=weapon,
                        direction=direction,
                        action_detail=spell_name or weapon or direction,
                    )

        # Fallback: keyword matching
        for intent, keywords in _KEYWORD_FALLBACK:
            for kw in keywords:
                if kw in normalized:
                    # Try simple target extraction after keyword
                    target = self._extract_after_keyword(normalized, kw)
                    return ParsedAction(
                        intent=intent,
                        raw_input=stripped,
                        target=target,
                        action_detail=target,
                    )

        return ParsedAction(intent=ActionIntent.UNKNOWN, raw_input=stripped)

    def _extract_after_keyword(self, normalized: str, keyword: str) -> Optional[str]:
        """Extract the word(s) after a keyword as target."""
        idx = normalized.find(keyword)
        if idx == -1:
            return None
        after = normalized[idx + len(keyword):].strip()
        # Remove common prepositions
        after = re.sub(r"^(the|a|an|to|at|on|with|bir|bu|şu|o)\s+", "", after)
        return after if after else None

    def _detect_intent(self, normalized_text: str) -> ActionIntent:
        """
        Legacy method: detect intent from normalized text using keyword matching.
        Kept for backward compatibility.
        """
        for intent, keywords in _KEYWORD_FALLBACK:
            for kw in keywords:
                if kw in normalized_text:
                    return intent
        return ActionIntent.UNKNOWN
