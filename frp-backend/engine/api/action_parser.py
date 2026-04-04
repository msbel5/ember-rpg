"""
Ember RPG - API Layer
Action Parser: natural language -> structured game intent.
Supports Turkish and English input.
"""
from dataclasses import dataclass
from enum import Enum
from typing import Optional
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
    PICK_UP = "pick_up"
    DROP = "drop"
    EQUIP = "equip"
    UNEQUIP = "unequip"
    CRAFT = "craft"
    SEARCH = "search"
    STEAL = "steal"
    PERSUADE = "persuade"
    INTIMIDATE = "intimidate"
    BRIBE = "bribe"
    DECEIVE = "deceive"
    THINK = "think"
    ADDRESS = "address"
    SNEAK = "sneak"
    CLIMB = "climb"
    LOCKPICK = "lockpick"
    PRAY = "pray"
    READ_ITEM = "read"
    PUSH = "push"
    FISH = "fish"
    MINE = "mine"
    CHOP = "chop"
    SAVE_GAME = "save_game"
    LOAD_GAME = "load_game"
    LIST_SAVES = "list_saves"
    DELETE_SAVE = "delete_save"
    ACCEPT_QUEST = "accept_quest"
    TURN_IN_QUEST = "turn_in_quest"
    FILL = "fill"
    POUR = "pour"
    EMPTY = "empty"
    STASH = "stash"
    ROTATE_ITEM = "rotate_item"
    GO_TO = "go_to"
    SHORT_REST = "short_rest"
    LONG_REST = "long_rest"
    DISENGAGE = "disengage"
    UNKNOWN = "unknown"


@dataclass
class ParsedAction:
    intent: ActionIntent
    raw_input: str
    target: Optional[str] = None
    spell_name: Optional[str] = None
    weapon: Optional[str] = None
    direction: Optional[str] = None
    action_detail: Optional[str] = None

    @property
    def raw_text(self) -> str:
        return self.raw_input


def _normalize(text: str) -> str:
    normalized = re.sub(r"[^\w\s]", " ", text.lower()).strip()
    return re.sub(r"\s+", " ", normalized)


def _looks_turkish(text: str) -> bool:
    lowered = (text or "").lower()
    return (
        any(ch in lowered for ch in "çğıöşü")
        or any(keyword in lowered for keyword in (
            "konuş", "saldır", "incele", "aç", "çal", "görev", "git",
            "bak", "dinlen", "düşün", "hatırla", "rüşvet", "kandır",
        ))
    )


def _restore_turkish_final_consonant(stem: str) -> str:
    if stem.endswith("ğ"):
        return stem[:-1] + "k"
    if stem.endswith("d"):
        return stem[:-1] + "t"
    if stem.endswith("b"):
        return stem[:-1] + "p"
    if stem.endswith("c"):
        return stem[:-1] + "ç"
    return stem


def _strip_turkish_case_suffix(token: str) -> str:
    lowered = token.lower().strip()
    suffixes = (
        "lardan", "lerden", "ların", "lerin",
        "yla", "yle", "dan", "den", "tan", "ten", "la", "le",
        "yı", "yi", "yu", "yü", "ya", "ye", "nı", "ni", "nu", "nü",
        "ı", "i", "u", "ü", "a", "e",
    )
    for suffix in suffixes:
        if len(lowered) > len(suffix) + 2 and lowered.endswith(suffix):
            stem = lowered[:-len(suffix)]
            return _restore_turkish_final_consonant(stem)
    return lowered


def _normalize_turkish_target(target: str) -> str:
    tokens = [token for token in re.split(r"\s+", (target or "").strip()) if token]
    if not tokens:
        return ""
    return " ".join(_strip_turkish_case_suffix(token) for token in tokens)


def _compile(*patterns: str) -> list[re.Pattern]:
    return [re.compile(pattern, re.IGNORECASE) for pattern in patterns]


_PATTERNS: list[tuple[ActionIntent, list[re.Pattern]]] = [
    (ActionIntent.ACCEPT_QUEST, _compile(
        r"^(?:accept|start|begin|take)\s+(?:(?:the|a)\s+)?quest(?:\s+(?P<target>[\w\s]+))?$",
        r"^(?:görevi?\s+kabul\s+et|görev\s+al)\s*(?P<target>[\w\s]*)$",
    )),
    (ActionIntent.TURN_IN_QUEST, _compile(
        r"^(?:turn\s+in|hand\s+in|deliver|submit)\s+(?:(?:the|a)\s+)?quest(?:\s+(?P<target>[\w\s]+))?$",
        r"^(?:görevi?\s+teslim\s+et|görevi?\s+bitir)\s*(?P<target>[\w\s]*)$",
    )),
    (ActionIntent.SHORT_REST, _compile(
        r"^(?:short\s+rest|take\s+a\s+breather|kısa\s+dinlenme)$",
    )),
    (ActionIntent.LONG_REST, _compile(
        r"^(?:long\s+rest|sleep|camp|make\s+camp|full\s+rest|uzun\s+dinlenme|uyu|kamp\s+kur)$",
        r"^(?:[\w\s]+\s+)?uyumak\s+(?:istiyorum|istiyom)?$",
    )),
    (ActionIntent.REST, _compile(
        r"^(?:rest|dinlen)$",
        r"^(?:[\w\s]+\s+)?dinlenmek\s+(?:istiyorum|istiyom)?$",
        r"^(?:rest\s+and\s+recover)$",
    )),
    (ActionIntent.DISENGAGE, _compile(
        r"^(?:disengage|withdraw\s+carefully|defensive\s+retreat|temkinli\s+çekil|ayrıl)$",
    )),
    (ActionIntent.SAVE_GAME, _compile(
        r"^(?:save\s+(?:game\s+)?as|save\s+as)\s+(?P<target>[\w\s]+)$",
        r"^(?:save\s+game|save)\s+(?P<target>[\w\s]+)$",
        r"^(?:save\s+game|save|quick\s*save|kaydet|oyunu\s+kaydet)$",
    )),
    (ActionIntent.LOAD_GAME, _compile(
        r"^(?:load\s+game|load|restore)\s+(?P<target>[\w\s]+)$",
        r"^(?:load\s+game|load|restore|yükle|oyunu\s+yükle)$",
    )),
    (ActionIntent.LIST_SAVES, _compile(
        r"^(?:saves|list\s+saves|show\s+saves|kayıtlar|kayıtları\s+göster)$",
    )),
    (ActionIntent.DELETE_SAVE, _compile(
        r"^(?:delete\s+save|remove\s+save|kayıt\s+sil)\s+(?P<target>[\w\s]+)$",
    )),
    (ActionIntent.FISH, _compile(
        r"^(?:fish|cast\s+line|go\s+fishing|balık\s+tut)(?:\s+(?:in\s+|at\s+)?(?P<target>[\w\s]*))?$",
    )),
    (ActionIntent.CAST_SPELL, _compile(
        r"^(?:cast|use\s+spell|büyü\s+yap|büyü\s+at)\s+(?P<spell>[\w\s]+?)\s+(?:at|on|üzerinde|üstüne|hedef)\s+(?P<target>[\w\s]+)$",
        r"^(?:cast|sihir|büyü)\s+(?P<spell>[\w\s]+)$",
        r"^(?P<spell>fireball|lightning bolt|heal|icebolt|şimşek|ateş topu|buz oku)\s+(?:at|on|üzerinde)?\s*(?P<target>[\w\s]*)$",
    )),
    (ActionIntent.ATTACK, _compile(
        r"^(?:attack|saldır|vur|hit|strike|slash|stab|fight)\s+(?P<target>[\w\s]+?)\s+(?:with|using|ile)\s+(?P<weapon>[\w\s]+)$",
        r"^(?P<target>[\w\s]+?)\s+(?:saldır(?:ıyorum|iyorum|uyorum|yorum|ıyom|iyom)?|vur|öldür)$",
        r"^(?:attack|saldır|vur|hit|strike|slash|stab|fight|öldür|kesivur|çarp|hücum)\s+(?P<target>[\w\s]+)$",
    )),
    (ActionIntent.ADDRESS, _compile(
        r"^(?:say\s+to|tell|ask)\s+(?P<target>[\w\s]+?)\s+(?P<direction>.+)$",
    )),
    (ActionIntent.THINK, _compile(
        r"^(?:think(?:\s+about)?|recall|remember|what\s+do\s+i\s+know(?:\s+about)?|to\s+self|düşün|hatırla)\s*(?P<target>[\w\s]*)$",
    )),
    (ActionIntent.TALK, _compile(
        r"^(?:talk\s+to|talk|speak\s+(?:to|with)|chat\s+with|greet|konuş|selamla|söyle|sor|pazarlık|hey|excuse\s+me|what\s+does)\s+(?P<target>[\w\s]+)$",
        r"^(?P<target>[\w\s]+?)\s+konuş(?:uyorum|uyom|urum|uruz|)$",
        r"^(?:innkeeper|merchant|guard|blacksmith|priest|mage|elder|captain|barkeep|tavernkeeper)(?:\s+[\w\s]*)?$",
    )),
    (ActionIntent.TRADE, _compile(
        r"^(?:trade\s+(?:with\s+)?|barter\s+(?:with\s+)?|buy\s+from\s+|shop\s+(?:with\s+)?)(?P<target>[\w\s]+)$",
        r"^(?:show\s+me\s+(?:your\s+)?wares|what\s+do\s+you\s+have|what\s+are\s+you\s+selling|buy\s+something|i\s+want\s+to\s+buy|alışveriş|satın\s+al)$",
    )),
    (ActionIntent.PICK_UP, _compile(
        r"^(?:pick\s+up|grab|take|loot|collect|get|al|topla|kaldır)\s+(?P<target>[\w\s]+)$",
    )),
    (ActionIntent.DROP, _compile(
        r"^(?:drop|discard|throw\s+away|toss|at|bırak)\s+(?P<target>[\w\s]+)$",
    )),
    (ActionIntent.EQUIP, _compile(
        r"^(?:equip|wear|wield|put\s+on|don|kuşan|giy)\s+(?P<target>[\w\s]+)$",
    )),
    (ActionIntent.UNEQUIP, _compile(
        r"^(?:unequip|remove|take\s+off|doff|çıkar|çıkart)\s+(?P<target>[\w\s]+)$",
    )),
    (ActionIntent.CRAFT, _compile(
        r"^(?:craft|make|forge|brew|cook|build|create|smith|üret|yap|pişir|dök)\s+(?P<target>[\w\s]+)$",
    )),
    (ActionIntent.SEARCH, _compile(
        r"^(?:search|look\s+for|investigate|rummage)\s+(?P<target>[\w\s]+)$",
    )),
    (ActionIntent.STEAL, _compile(
        r"^(?:steal\s+(?:from\s+)?|pickpocket|swipe|pilfer|çal)\s*(?P<target>[\w\s]+)$",
        r"^(?P<target>[\w\s]+?)\s+çal$",
    )),
    (ActionIntent.PERSUADE, _compile(
        r"^(?:persuade|convince|negotiate\s+(?:with\s+)?|diplomat|ikna\s+et)\s+(?P<target>[\w\s]+)$",
    )),
    (ActionIntent.INTIMIDATE, _compile(
        r"^(?:intimidate|threaten|scare|bully|korkut|tehdit\s+et)\s+(?P<target>[\w\s]+)$",
    )),
    (ActionIntent.BRIBE, _compile(
        r"^(?:bribe|pay\s+off|slip\s+coin\s+to|rüşvet\s+ver)\s+(?P<target>[\w\s]+)$",
    )),
    (ActionIntent.DECEIVE, _compile(
        r"^(?:deceive|lie\s+to|bluff|trick|kandır|yalan\s+söyle)\s+(?P<target>[\w\s]+)$",
    )),
    (ActionIntent.STASH, _compile(
        r"^(?:stash|hide|conceal|sakla|gizle)\s+(?P<target>[\w\s]+?)(?:\s+(?:in|inside|into|içine)\s+(?P<direction>[\w\s]+))$",
    )),
    (ActionIntent.SNEAK, _compile(
        r"^(?:sneak(?:\s+past)?|stealth|creep|skulk|gizlen|sızıl|sinsi)\s*(?P<target>[\w\s]*)$",
        r"^hide$",
    )),
    (ActionIntent.CLIMB, _compile(
        r"^(?:climb|scale|ascend|tırman)\s+(?P<target>[\w\s]+)$",
    )),
    (ActionIntent.LOCKPICK, _compile(
        r"^(?:lockpick|pick\s+(?:the\s+)?lock|maymuncuk)\s*(?:on\s+|of\s+)?(?P<target>[\w\s]*)$",
    )),
    (ActionIntent.PRAY, _compile(
        r"^(?:pray|worship|meditate|dua\s+et|ibadet)\s*(?:at\s+|in\s+)?(?P<target>[\w\s]*)$",
    )),
    (ActionIntent.READ_ITEM, _compile(
        r"^(?:read|decipher|study|oku|çöz)\s+(?P<target>[\w\s]+)$",
    )),
    (ActionIntent.PUSH, _compile(
        r"^(?:push|shove)\s+(?P<target>[\w\s]+)$",
    )),
    (ActionIntent.MINE, _compile(
        r"^(?:mine|dig|excavate|kaz|maden\s+kaz)\s*(?P<target>[\w\s]*)$",
    )),
    (ActionIntent.FILL, _compile(
        r"^(?:fill|refill|doldur)\s+(?P<target>[\w\s]+?)(?:\s+(?:at|from|in|with|dan|den)\s+(?P<direction>[\w\s]+))?$",
    )),
    (ActionIntent.POUR, _compile(
        r"^(?:pour|dump|dök|boşalt)\s+(?P<target>[\w\s]+?)(?:\s+(?:into|on|onto|in|to|içine)\s+(?P<direction>[\w\s]+))?$",
    )),
    (ActionIntent.EMPTY, _compile(
        r"^(?:empty|drain|boşalt)\s+(?P<target>[\w\s]+)$",
    )),
    (ActionIntent.ROTATE_ITEM, _compile(
        r"^(?:rotate|flip)\s+(?P<target>[\w\s]+)$",
    )),
    (ActionIntent.CHOP, _compile(
        r"^(?:chop|cut|fell|kes|doğra|balta)\s+(?P<target>[\w\s]+)$",
    )),
    (ActionIntent.INTERACT, _compile(
        r"^(?:interact\s+with|push|pull|turn|activate|press|etkileş|it|çek|çevir|aktive)\s+(?P<target>[\w\s]+)$",
        r"^(?:use|kullan)\s+(?P<target>(?:lever|switch|button|handle|crank|wheel|altar|well|fountain|gate|portal|mechanism|statue|shrine|pedestal|rope|chain|pulley|valve|dial|panel|door|hatch|trap|bridge)[\w\s]*)$",
    )),
    (ActionIntent.USE_ITEM, _compile(
        r"^(?:use|drink|eat|consume|apply|kullan|iç|ye|uygula)\s+(?P<target>[\w\s]+)$",
    )),
    (ActionIntent.LOOK, _compile(
        r"^(?:look(?:\s+around)?|gaze|survey|etrafına?\s+bak|bak(?:\s+etraf)?|çevreye\s+bak)$",
    )),
    (ActionIntent.EXAMINE, _compile(
        r"^(?:look\s+around\s+the)\s+(?P<target>[\w\s]+)$",
        r"^(?:examine|inspect|study|check\s+out|search|investigate|incele|ara|kontrol\s+et|gözlemle)\s+(?P<target>[\w\s]+)$",
        r"^(?:[\w\s]+\s+)?(?:inceliyorum|bakıyorum|arıyorum)\s*(?P<target>[\w\s]*)$",
        r"^(?P<target>[\w\s]+?)\s+incele$",
    )),
    (ActionIntent.OPEN, _compile(
        r"^(?:open|unlock|force\s+open|break\s+open|aç|kır|zorla|sök)\s+(?P<target>[\w\s]+)$",
        r"^(?P<target>[\w\s]+?)\s+aç(?:ıyorum|iyorum|ar\s+mısın|)$",
    )),
    (ActionIntent.FLEE, _compile(
        r"^(?:run\s+away|flee|escape|retreat|withdraw|bolt|kaç|geri\s+çekil|çekil|kaçmak)$",
    )),
    (ActionIntent.INVENTORY, _compile(
        r"^(?:check\s+inventory|show\s+inventory|open\s+inventory|inventory|i|show\s+items|list\s+items|my\s+items|items|bag|backpack|equipment|gear|eşyalarım|çantam|envanterim)$",
    )),
    (ActionIntent.GO_TO, _compile(
        r"^approach\s+(?:the\s+)?(?P<target>[\w\s]+)$",
    )),
    (ActionIntent.MOVE, _compile(
        r"^(?:go|move|move\s+to|travel\s+to|head\s+to|enter|walk\s+to|walk|git|gidin|ilerle|gidiyorum|yürü)\s+(?P<direction>[\w\s]+)$",
        r"^(?:[\w\s]+\s+)?(?:gidiyorum|gidelim|gidecek)\s*(?P<direction>[\w\s]*)$",
        r"^(?P<direction>north|south|east|west|up|down|kuzey|güney|doğu|batı|yukarı|aşağı)$",
    )),
]

_KEYWORD_FALLBACK: list[tuple[ActionIntent, list[str]]] = [
    (ActionIntent.ACCEPT_QUEST, ["accept quest", "start quest", "take quest", "görevi kabul et", "görev al"]),
    (ActionIntent.TURN_IN_QUEST, ["turn in quest", "hand in quest", "deliver quest", "görevi teslim et"]),
    (ActionIntent.SHORT_REST, ["short rest", "kısa dinlenme"]),
    (ActionIntent.LONG_REST, ["long rest", "sleep", "camp", "uyu", "kamp kur", "uzun dinlenme"]),
    (ActionIntent.REST, ["rest", "dinlen"]),
    (ActionIntent.DISENGAGE, ["disengage", "withdraw carefully", "temkinli çekil"]),
    (ActionIntent.SAVE_GAME, ["save", "quick save", "kaydet"]),
    (ActionIntent.LOAD_GAME, ["load", "restore", "yükle"]),
    (ActionIntent.LIST_SAVES, ["saves", "list saves", "show saves", "kayıtlar"]),
    (ActionIntent.DELETE_SAVE, ["delete save", "remove save", "kayıt sil"]),
    (ActionIntent.FLEE, ["run away", "flee", "escape", "retreat", "kaç"]),
    (ActionIntent.INVENTORY, ["inventory", "items", "bag", "backpack", "equipment", "gear", "eşya", "envanter", "çanta"]),
    (ActionIntent.CRAFT, ["craft", "make", "forge", "brew", "cook", "üret", "yap", "pişir"]),
    (ActionIntent.LOCKPICK, ["lockpick", "pick lock", "maymuncuk"]),
    (ActionIntent.STEAL, ["steal", "pickpocket", "swipe", "çal"]),
    (ActionIntent.PERSUADE, ["persuade", "convince", "negotiate", "ikna"]),
    (ActionIntent.INTIMIDATE, ["intimidate", "threaten", "scare", "korkut", "tehdit"]),
    (ActionIntent.BRIBE, ["bribe", "pay off", "rüşvet"]),
    (ActionIntent.DECEIVE, ["deceive", "bluff", "lie", "trick", "kandır"]),
    (ActionIntent.THINK, ["think", "recall", "remember", "what do i know", "düşün", "hatırla", "to self"]),
    (ActionIntent.ADDRESS, ["say to", "tell", "ask"]),
    (ActionIntent.SNEAK, ["sneak", "stealth", "hide", "creep", "gizlen", "sinsi"]),
    (ActionIntent.CLIMB, ["climb", "scale", "ascend", "tırman"]),
    (ActionIntent.PRAY, ["pray", "worship", "meditate", "dua", "ibadet"]),
    (ActionIntent.READ_ITEM, ["read", "decipher", "study", "oku"]),
    (ActionIntent.FISH, ["fish", "cast line", "go fishing", "balık"]),
    (ActionIntent.MINE, ["mine", "dig", "excavate", "kaz", "maden"]),
    (ActionIntent.FILL, ["fill", "refill", "doldur"]),
    (ActionIntent.POUR, ["pour", "dump", "dök"]),
    (ActionIntent.EMPTY, ["empty", "drain", "boşalt"]),
    (ActionIntent.STASH, ["stash", "hide", "conceal", "sakla", "gizle"]),
    (ActionIntent.ROTATE_ITEM, ["rotate", "flip"]),
    (ActionIntent.GO_TO, ["approach"]),
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
    (ActionIntent.OPEN, ["aç", "kır", "open", "unlock"]),
    (ActionIntent.MOVE, ["git", "go", "move", "walk", "enter", "travel"]),
    (ActionIntent.EXAMINE, ["incele", "examine", "inspect", "check"]),
]


class ActionParser:
    """Parse player input into a structured action."""

    def parse(self, text: str) -> ParsedAction:
        stripped = text.strip()
        normalized = _normalize(stripped)

        for intent, patterns in _PATTERNS:
            for pattern in patterns:
                match = pattern.match(normalized)
                if not match:
                    continue
                groups = match.groupdict()
                target = groups.get("target") or None
                spell_name = groups.get("spell") or None
                weapon = groups.get("weapon") or None
                direction = groups.get("direction") or None

                if target:
                    target = target.strip()
                    if _looks_turkish(stripped):
                        target = _normalize_turkish_target(target)
                if spell_name:
                    spell_name = spell_name.strip()
                if weapon:
                    weapon = weapon.strip()
                if direction:
                    direction = direction.strip()

                return ParsedAction(
                    intent=intent,
                    raw_input=stripped,
                    target=target or None,
                    spell_name=spell_name,
                    weapon=weapon,
                    direction=direction,
                    action_detail=spell_name or weapon or direction,
                )

        for intent, keywords in _KEYWORD_FALLBACK:
            for keyword in keywords:
                if " " not in keyword and len(keyword) <= 4 and keyword.isascii():
                    matched = bool(re.search(r"(?:^|\s)" + re.escape(keyword) + r"(?:\s|$)", normalized))
                else:
                    matched = keyword in normalized
                if not matched:
                    continue
                target = self._extract_after_keyword(normalized, keyword)
                if target and _looks_turkish(stripped):
                    target = _normalize_turkish_target(target)
                return ParsedAction(
                    intent=intent,
                    raw_input=stripped,
                    target=target,
                    action_detail=target,
                )

        return ParsedAction(intent=ActionIntent.UNKNOWN, raw_input=stripped)

    def _extract_after_keyword(self, normalized: str, keyword: str) -> Optional[str]:
        idx = normalized.find(keyword)
        if idx == -1:
            return None
        after = normalized[idx + len(keyword):].strip()
        after = re.sub(r"^(the|a|an|to|at|on|with|from|bir|bu|şu|o)\s+", "", after)
        return after if after else None

    def _detect_intent(self, normalized_text: str) -> ActionIntent:
        for intent, keywords in _KEYWORD_FALLBACK:
            for keyword in keywords:
                if keyword in normalized_text:
                    return intent
        return ActionIntent.UNKNOWN
