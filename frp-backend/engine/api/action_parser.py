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
    TRADE = "trade"
    LOOK = "look"
    EXAMINE = "examine"
    REST = "rest"
    OPEN = "open"
    INTERACT = "interact"
    INVENTORY = "inventory"
    FLEE = "flee"
    # --- New intents (Sprint 5) ---
    PICK_UP = "pick_up"
    DROP = "drop"
    EQUIP = "equip"
    UNEQUIP = "unequip"
    CRAFT = "craft"
    SEARCH = "search"
    STEAL = "steal"
    PERSUADE = "persuade"
    INTIMIDATE = "intimidate"
    SNEAK = "sneak"
    CLIMB = "climb"
    LOCKPICK = "lockpick"
    PRAY = "pray"
    READ_ITEM = "read"
    PUSH = "push"
    FISH = "fish"
    MINE = "mine"
    CHOP = "chop"
    # --- Save/Load intents ---
    SAVE_GAME = "save_game"
    LOAD_GAME = "load_game"
    LIST_SAVES = "list_saves"
    DELETE_SAVE = "delete_save"
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

    # TALK: "talk to guard" / "speak with innkeeper" / "hey merchant" / "konuş muhafızla"
    (ActionIntent.TALK, [
        re.compile(
            r"^(?:talk\s+to|talk|speak\s+(?:to|with)|chat\s+with|greet|konuş|selamla|söyle|sor|pazarlık|hey|excuse\s+me|what\s+does)\s+(?P<target>[\w\s]+)$",
            re.IGNORECASE
        ),
        re.compile(
            r"^(?:innkeeper|merchant|guard|blacksmith|priest|wizard|elder|captain|barkeep|tavernkeeper)(?:\s+[\w\s]*)?$",
            re.IGNORECASE
        ),
    ]),

    # TRADE: "trade with merchant" / "barter" / "buy something" / "show me your wares"
    (ActionIntent.TRADE, [
        re.compile(
            r"^(?:trade\s+(?:with\s+)?|barter\s+(?:with\s+)?|buy\s+from\s+|shop\s+(?:with\s+)?)(?P<target>[\w\s]+)$",
            re.IGNORECASE
        ),
        re.compile(
            r"^(?:show\s+me\s+(?:your\s+)?wares|what\s+do\s+you\s+have|what\s+are\s+you\s+selling|buy\s+something|i\s+want\s+to\s+buy|alışveriş|satın\s+al)$",
            re.IGNORECASE
        ),
    ]),

    # PICKUP / PICK_UP: "pick up health potion" / "take potion" / "al iksiri"
    (ActionIntent.PICK_UP, [
        re.compile(
            r"^(?:pick\s+up|grab|take|loot|collect|get|al|topla|kaldır)\s+(?P<target>[\w\s]+)$",
            re.IGNORECASE
        ),
    ]),

    # DROP: "drop sword" / "discard potion" / "throw away shield"
    (ActionIntent.DROP, [
        re.compile(
            r"^(?:drop|discard|throw\s+away|toss|at|bırak)\s+(?P<target>[\w\s]+)$",
            re.IGNORECASE
        ),
    ]),

    # EQUIP: "equip iron sword" / "wear leather armor" / "wield staff"
    (ActionIntent.EQUIP, [
        re.compile(
            r"^(?:equip|wear|wield|put\s+on|don|kuşan|giy)\s+(?P<target>[\w\s]+)$",
            re.IGNORECASE
        ),
    ]),

    # UNEQUIP: "unequip sword" / "remove helmet" / "take off armor"
    (ActionIntent.UNEQUIP, [
        re.compile(
            r"^(?:unequip|remove|take\s+off|doff|çıkar|çıkart)\s+(?P<target>[\w\s]+)$",
            re.IGNORECASE
        ),
    ]),

    # CRAFT: "craft iron sword" / "forge steel bar" / "brew potion" / "cook stew"
    (ActionIntent.CRAFT, [
        re.compile(
            r"^(?:craft|make|forge|brew|cook|build|create|smith|üret|yap|pişir|dök)\s+(?P<target>[\w\s]+)$",
            re.IGNORECASE
        ),
    ]),

    # SEARCH: "search the room" / "look for traps" / "investigate area"
    (ActionIntent.SEARCH, [
        re.compile(
            r"^(?:search|look\s+for|investigate|rummage)\s+(?P<target>[\w\s]+)$",
            re.IGNORECASE
        ),
    ]),

    # STEAL: "steal from merchant" / "pickpocket guard" / "swipe ring"
    (ActionIntent.STEAL, [
        re.compile(
            r"^(?:steal\s+(?:from\s+)?|pickpocket|swipe|pilfer|çal)\s*(?P<target>[\w\s]+)$",
            re.IGNORECASE
        ),
    ]),

    # PERSUADE: "persuade guard" / "convince merchant" / "negotiate with innkeeper"
    (ActionIntent.PERSUADE, [
        re.compile(
            r"^(?:persuade|convince|negotiate\s+(?:with\s+)?|diplomat|ikna\s+et)\s+(?P<target>[\w\s]+)$",
            re.IGNORECASE
        ),
    ]),

    # INTIMIDATE: "intimidate guard" / "threaten bandit" / "scare merchant"
    (ActionIntent.INTIMIDATE, [
        re.compile(
            r"^(?:intimidate|threaten|scare|bully|korkut|tehdit\s+et)\s+(?P<target>[\w\s]+)$",
            re.IGNORECASE
        ),
    ]),

    # SNEAK: "sneak past guards" / "stealth" / "hide" / "creep"
    (ActionIntent.SNEAK, [
        re.compile(
            r"^(?:sneak(?:\s+past)?|stealth|hide|creep|skulk|gizlen|sızıl|sinsi)\s*(?P<target>[\w\s]*)$",
            re.IGNORECASE
        ),
    ]),

    # CLIMB: "climb wall" / "scale cliff" / "ascend ladder"
    (ActionIntent.CLIMB, [
        re.compile(
            r"^(?:climb|scale|ascend|tırman)\s+(?P<target>[\w\s]+)$",
            re.IGNORECASE
        ),
    ]),

    # LOCKPICK: "lockpick the door" / "pick lock" / "pick the lock"
    (ActionIntent.LOCKPICK, [
        re.compile(
            r"^(?:lockpick|pick\s+(?:the\s+)?lock|maymuncuk)\s*(?:on\s+|of\s+)?(?P<target>[\w\s]*)$",
            re.IGNORECASE
        ),
    ]),

    # PRAY: "pray" / "worship at altar" / "meditate"
    (ActionIntent.PRAY, [
        re.compile(
            r"^(?:pray|worship|meditate|dua\s+et|ibadet)\s*(?:at\s+|in\s+)?(?P<target>[\w\s]*)$",
            re.IGNORECASE
        ),
    ]),

    # READ_ITEM: "read scroll" / "decipher runes" / "study book"
    (ActionIntent.READ_ITEM, [
        re.compile(
            r"^(?:read|decipher|study|oku|çöz)\s+(?P<target>[\w\s]+)$",
            re.IGNORECASE
        ),
    ]),

    # PUSH: "push boulder" / "shove crate" (NOT "move X" — that's handled by MOVE)
    (ActionIntent.PUSH, [
        re.compile(
            r"^(?:push|shove)\s+(?P<target>[\w\s]+)$",
            re.IGNORECASE
        ),
    ]),

    # FISH: "fish" / "cast line" / "go fishing"
    (ActionIntent.FISH, [
        re.compile(
            r"^(?:fish|cast\s+line|go\s+fishing|balık\s+tut)(?:\s+(?:in\s+|at\s+)?(?P<target>[\w\s]*))?$",
            re.IGNORECASE
        ),
    ]),

    # MINE: "mine ore" / "dig" / "excavate"
    (ActionIntent.MINE, [
        re.compile(
            r"^(?:mine|dig|excavate|kaz|maden\s+kaz)\s*(?P<target>[\w\s]*)$",
            re.IGNORECASE
        ),
    ]),

    # SAVE_GAME: "save" / "save game" / "save as mysave" / "kaydet"
    (ActionIntent.SAVE_GAME, [
        re.compile(
            r"^(?:save\s+(?:game\s+)?as|save\s+as)\s+(?P<target>[\w\s]+)$",
            re.IGNORECASE
        ),
        re.compile(
            r"^(?:save\s+game|save|quick\s*save|kaydet|oyunu\s+kaydet)$",
            re.IGNORECASE
        ),
    ]),

    # LOAD_GAME: "load" / "load game" / "load mysave" / "yükle"
    (ActionIntent.LOAD_GAME, [
        re.compile(
            r"^(?:load\s+game|load|restore|yükle|oyunu\s+yükle)$",
            re.IGNORECASE
        ),
        re.compile(
            r"^(?:load\s+game|load|restore)\s+(?P<target>[\w\s]+)$",
            re.IGNORECASE
        ),
    ]),

    # LIST_SAVES: "saves" / "list saves" / "show saves"
    (ActionIntent.LIST_SAVES, [
        re.compile(
            r"^(?:saves|list\s+saves|show\s+saves|kayıtlar|kayıtları\s+göster)$",
            re.IGNORECASE
        ),
    ]),

    # DELETE_SAVE: "delete save mysave"
    (ActionIntent.DELETE_SAVE, [
        re.compile(
            r"^(?:delete\s+save|remove\s+save|kayıt\s+sil)\s+(?P<target>[\w\s]+)$",
            re.IGNORECASE
        ),
    ]),

    # CHOP: "chop tree" / "cut wood" / "fell tree"
    (ActionIntent.CHOP, [
        re.compile(
            r"^(?:chop|cut|fell|kes|doğra|balta)\s+(?P<target>[\w\s]+)$",
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
            r"^(?:check\s+inventory|show\s+inventory|open\s+inventory|inventory|i|show\s+items|list\s+items|my\s+items|items|bag|backpack|equipment|gear|eşyalarım|çantam|envanterim)$",
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

    # MOVE: "go north" / "move north" / "move to dungeon" / "enter cave" / "git kuzey"
    (ActionIntent.MOVE, [
        re.compile(
            r"^(?:go|move|move\s+to|travel\s+to|head\s+to|enter|walk\s+to|walk|git|gidin|ilerle|gidiyorum|yürü)\s+(?P<direction>[\w\s]+)$",
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
    (ActionIntent.SAVE_GAME, ["save", "save game", "quick save", "kaydet"]),
    (ActionIntent.LOAD_GAME, ["load", "load game", "restore", "yükle"]),
    (ActionIntent.LIST_SAVES, ["saves", "list saves", "show saves", "kayıtlar"]),
    (ActionIntent.DELETE_SAVE, ["delete save", "remove save", "kayıt sil"]),
    (ActionIntent.FLEE, ["run away", "flee", "escape", "retreat", "kaç", "geri çekil"]),
    (ActionIntent.INVENTORY, ["inventory", "items", "bag", "backpack", "equipment", "gear",
                               "eşya", "envanter", "çanta"]),
    (ActionIntent.CRAFT, ["craft", "make", "forge", "brew", "cook", "build", "create", "smith",
                           "üret", "yap", "pişir"]),
    (ActionIntent.LOCKPICK, ["lockpick", "pick lock", "pick the lock", "maymuncuk"]),
    (ActionIntent.STEAL, ["steal", "pickpocket", "swipe", "pilfer", "çal"]),
    (ActionIntent.PERSUADE, ["persuade", "convince", "negotiate", "diplomat", "ikna"]),
    (ActionIntent.INTIMIDATE, ["intimidate", "threaten", "scare", "bully", "korkut", "tehdit"]),
    (ActionIntent.SNEAK, ["sneak", "stealth", "hide", "creep", "skulk", "gizlen", "sinsi"]),
    (ActionIntent.CLIMB, ["climb", "scale", "ascend", "tırman"]),
    (ActionIntent.PRAY, ["pray", "worship", "meditate", "dua", "ibadet"]),
    (ActionIntent.READ_ITEM, ["read", "decipher", "study", "oku"]),
    (ActionIntent.FISH, ["fish", "cast line", "go fishing", "balık"]),
    (ActionIntent.MINE, ["mine", "dig", "excavate", "kaz", "maden"]),
    (ActionIntent.CHOP, ["chop", "cut", "fell", "kes", "balta"]),
    (ActionIntent.SEARCH, ["search", "look for", "investigate", "rummage"]),
    (ActionIntent.DROP, ["drop", "discard", "throw away", "toss", "bırak"]),
    (ActionIntent.EQUIP, ["equip", "wear", "wield", "put on", "don", "kuşan", "giy"]),
    (ActionIntent.UNEQUIP, ["unequip", "remove", "take off", "doff", "çıkar"]),
    (ActionIntent.PUSH, ["push", "shove"]),
    (ActionIntent.PICK_UP, ["pick up", "grab", "take", "loot", "collect", "get", "al", "topla"]),
    (ActionIntent.LOOK, ["look", "bak", "etraf"]),
    (ActionIntent.ATTACK, ["saldır", "vur", "öldür", "attack", "strike", "hit", "kill"]),
    (ActionIntent.CAST_SPELL, ["büyü", "sihir", "cast", "spell", "magic", "fireball", "heal"]),
    (ActionIntent.USE_ITEM, ["kullan", "iç", "ye", "use", "drink", "eat", "consume", "potion"]),
    (ActionIntent.TRADE, ["trade", "barter", "buy", "sell", "wares", "shop", "alışveriş"]),
    (ActionIntent.TALK, ["konuş", "söyle", "talk", "speak", "greet"]),
    (ActionIntent.REST, ["dinlen", "uyu", "rest", "sleep", "camp"]),
    (ActionIntent.OPEN, ["aç", "kır", "open", "unlock"]),
    (ActionIntent.MOVE, ["git", "go", "move", "walk", "enter", "travel"]),
    (ActionIntent.EXAMINE, ["incele", "examine", "inspect", "check"]),
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

        # Fallback: keyword matching (word-boundary aware)
        for intent, keywords in _KEYWORD_FALLBACK:
            for kw in keywords:
                # Short ASCII keywords (<=4 chars) use word-boundary to avoid
                # substring false positives (e.g. "mine" in "examine").
                # Longer/Turkish keywords use substring match (Turkish is
                # agglutinative: "saldır" appears in "saldırıyorum").
                if " " not in kw and len(kw) <= 4 and kw.isascii():
                    matched = bool(re.search(r'(?:^|\s)' + re.escape(kw) + r'(?:\s|$)', normalized))
                else:
                    matched = kw in normalized
                if matched:
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
