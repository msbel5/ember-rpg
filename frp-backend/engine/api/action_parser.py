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
    MOVE = "move"
    TALK = "talk"
    EXAMINE = "examine"
    REST = "rest"
    OPEN = "open"
    UNKNOWN = "unknown"


@dataclass
class ParsedAction:
    """
    Structured representation of a player's natural language input.

    Attributes:
        intent: What the player wants to do
        target: Target entity name (extracted from input)
        action_detail: Weapon, spell name, or other detail
        raw_input: Original player text
    """
    intent: ActionIntent
    raw_input: str
    target: Optional[str] = None
    action_detail: Optional[str] = None


# Keyword → intent mapping (Turkish + English).
# ORDER MATTERS: checked top to bottom; more specific intents first.
_INTENT_KEYWORDS: list[tuple[ActionIntent, list[str]]] = [
    (ActionIntent.ATTACK, [
        "saldır", "vur", "öldür", "kesivur", "çarp", "hücum",
        "attack", "strike", "hit", "kill", "slash", "stab", "fight",
    ]),
    (ActionIntent.CAST_SPELL, [
        "büyü", "sihir", "büyüsü atıyorum", "büyü atıyorum",
        "spell", "cast", "magic", "fireball", "lightning", "iyileştir",
        "ateş büyü", "şimşek büyü", "heal",
    ]),
    (ActionIntent.USE_ITEM, [
        "kullan", "iç", "ye", "iksir", "potion", "use", "drink", "eat", "consume",
    ]),
    (ActionIntent.TALK, [
        "konuş", "söyle", "sor", "selamla", "bağır", "pazarlık",
        "talk", "say", "ask", "speak", "greet", "negotiate", "shout",
    ]),
    (ActionIntent.REST, [
        "dinlen", "dinlenmek", "dinleniyor", "uyu", "kamp kur", "mola ver",
        "rest", "sleep", "camp", "wait",
    ]),
    (ActionIntent.OPEN, [
        "aç", "kır", "zorla", "sök",
        "open", "unlock", "break", "force",
    ]),
    (ActionIntent.MOVE, [
        "git", "yürü", "koş", "kaç", "geç", "çekil", "ilerle", "gidiyorum",
        "go ", "run", "flee", "retreat", "walk", "advance", "move to",
    ]),
    (ActionIntent.EXAMINE, [
        "bak", "incele", "inceliyorum", "ara", "kontrol", "dinle",
        "look", "examine", "search", "inspect", "check", "listen",
    ]),
]


def _normalize(text: str) -> str:
    """Lowercase and strip punctuation."""
    return re.sub(r"[^\w\s]", " ", text.lower()).strip()


def _extract_target(text: str) -> Optional[str]:
    """
    Heuristic target extraction.
    Returns the first noun-like token that isn't a known keyword.
    """
    normalized = _normalize(text)

    # All known keywords flat set
    all_keywords: set[str] = set()
    for _, kws in _INTENT_KEYWORDS:
        for kw in kws:
            all_keywords.update(kw.split())

    tokens = normalized.split()
    candidates = []
    for token in tokens:
        # Strip Turkish suffixes from object-case forms
        base = re.sub(
            r"(ya|ye|yı|yi|yu|yü|a|e|ı|i|u|ü|ın|in|un|ün|na|ne|da|de|dan|den|nın|nin|yla|yle)$",
            "", token
        )
        if base not in all_keywords and token not in all_keywords and len(base) > 2:
            candidates.append(base)

    return candidates[0] if candidates else None


class ActionParser:
    """
    Parse natural language player input into structured game actions.

    Supports Turkish and English. Uses keyword matching for MVP.
    Unknown inputs return ActionIntent.UNKNOWN for DM fallback handling.

    Usage:
        parser = ActionParser()
        action = parser.parse("ejderhaya saldırıyorum")
        # action.intent == ActionIntent.ATTACK
        # action.target == "ejderha"
    """

    def parse(self, text: str) -> ParsedAction:
        """
        Parse player input into a ParsedAction.

        Args:
            text: Raw player input string

        Returns:
            ParsedAction with intent, target, and detail
        """
        normalized = _normalize(text)
        intent = self._detect_intent(normalized)
        target = _extract_target(text)

        return ParsedAction(
            intent=intent,
            raw_input=text,
            target=target,
        )

    def _detect_intent(self, normalized_text: str) -> ActionIntent:
        """
        Detect intent from normalized text using keyword matching.
        First match in priority order wins.
        """
        for intent, keywords in _INTENT_KEYWORDS:
            for kw in keywords:
                if kw in normalized_text:
                    return intent
        return ActionIntent.UNKNOWN
