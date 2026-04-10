#!/usr/bin/env python3
"""
Ember RPG — Data-driven asset pipeline

This script has two responsibilities:
1. Build deterministic asset jobs from game data and handwritten families.
2. Generate assets either with a local SDXL pipeline or the legacy HF API path.

Typical usage:
    python tools/asset_pipeline.py --plan all
    python tools/asset_pipeline.py --plan items --limit 20
    python tools/asset_pipeline.py --generate items --backend local_sdxl --limit 10
    python tools/asset_pipeline.py --generate tiles --backend hf_api_flux
    python tools/asset_pipeline.py --list
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import os
import re
import time
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

import requests
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_ROOT = PROJECT_ROOT / "frp-backend" / "data"
ITEMS_FILE = DATA_ROOT / "items.json"

RAW_DIR = PROJECT_ROOT / "tools" / "asset_raw"
PLAN_DIR = PROJECT_ROOT / "tools" / "asset_jobs"

LEGACY_SPRITE_DIR = PROJECT_ROOT / "godot-client" / "assets" / "sprites"
LEGACY_TILE_DIR = PROJECT_ROOT / "godot-client" / "assets" / "tiles"
GENERATED_DIR = PROJECT_ROOT / "godot-client" / "assets" / "generated"
GENERATED_SPRITE_DIR = GENERATED_DIR / "sprites"
GENERATED_TILE_DIR = GENERATED_DIR / "tiles"
GENERATED_ITEM_DIR = GENERATED_DIR / "items"
MANIFEST_FILE = GENERATED_DIR / "manifest.json"
CACHE_FILE = PROJECT_ROOT / "tools" / "asset_cache.json"

STYLE_REF_DIR = PROJECT_ROOT / "tools" / "style_refs"
DEFAULT_STYLE_REF = STYLE_REF_DIR / "ember_style_anchor.png"
THIRD_PARTY_DIR = PROJECT_ROOT / "godot-client" / "assets" / "third_party"
PIXEL_CRAWLER_DIR = THIRD_PARTY_DIR / "pixel_crawler" / "extracted"
PIXEL_CRAWLER_SPRITE_DIR = PIXEL_CRAWLER_DIR / "sprites"
PIXEL_CRAWLER_TILE_DIR = PIXEL_CRAWLER_DIR / "tiles"
LPC_DIR = THIRD_PARTY_DIR / "lpc" / "extracted"
LPC_TILE_DIR = LPC_DIR / "tiles"

SPRITE_SIZE = (64, 64)
GENERATED_SIZE = (64, 64)
ITEM_SIZE = (64, 64)
RAW_SIZE = (1024, 1024)
UPSCALE_SIZE = (256, 256)  # intermediate step in the downscale chain: 1024 -> 256 -> 64
DOWNSAMPLE_RESAMPLE = Image.NEAREST  # flip to Image.LANCZOS if you want softer painted edges; NEAREST keeps pixel alignment crisp

LEGACY_HF_API_URL = (
    "https://router.huggingface.co/hf-inference/models/black-forest-labs/FLUX.1-schnell"
)
DEFAULT_LOCAL_MODEL_ID = "stabilityai/stable-diffusion-xl-base-1.0"
DEFAULT_IP_ADAPTER_REPO = "h94/IP-Adapter"
DEFAULT_IP_ADAPTER_WEIGHT = "ip-adapter_sdxl.bin"

# Painted CRPG multi-LoRA stack — Gerald Brom XL + Dark Fantasy XL + Dark Gothic + Fallout Art.
# LCM-LoRA enables ~8-step sampling (5x faster than base 50-step SDXL).
# Each entry: (adapter_name, absolute_path, scale).
# Order matters for set_adapters weight application; lcm should stay last.
DEFAULT_LORA_STACK: list[tuple[str, str, float]] = [
    ("brom",       r"D:\ember-models\Gerald Brom XL - Dark Fantasy Art\Gerald_Brom_XL_-_Dark_Fantasy_Art-mid_180346-vid_202421.safetensors", 0.70),
    ("darkfan",    r"D:\ember-models\DARK FANTASY XL\DarkFanXLGrain-mid_1223108-vid_1618369.safetensors", 0.40),
    ("darkgothic", r"D:\ember-models\Dark Gothic Fantasy\dark_gothic_fantasy_xl_3.01-mid_293532-vid_329901.safetensors", 0.30),
    ("fallout",    r"D:\ember-models\Fallout Art (SDXL)\fallout_sdxl_lora-mid_721383-vid_806630.safetensors", 0.20),
    ("lcm",        r"D:\ember-models\lcm-lora-sdxl\pytorch_lora_weights.safetensors", 1.00),
]
USE_LCM_BY_DEFAULT = True
LCM_STEPS = 8
LCM_GUIDANCE = 1.5
ROGUES_DIR = PROJECT_ROOT / "tmp" / "asset_probe" / "32rogues"
ROGUES_ITEMS_PNG = ROGUES_DIR / "items.png"
ROGUES_ITEMS_TXT = ROGUES_DIR / "items.txt"
ROGUES_ROGUES_PNG = PROJECT_ROOT / "tmp" / "asset_probe" / "rogues.png"
ROGUES_ROGUES_TXT = ROGUES_DIR / "rogues.txt"
ROGUES_MONSTERS_PNG = PROJECT_ROOT / "tmp" / "asset_probe" / "monsters.png"
ROGUES_MONSTERS_TXT = ROGUES_DIR / "monsters.txt"
ROGUES_TILES_PNG = PROJECT_ROOT / "tmp" / "asset_probe" / "tiles.png"
ROGUES_TILES_TXT = ROGUES_DIR / "tiles.txt"
ROGUES_CELL_SIZE = 32

SPRITE_STYLE_PREFIX = (
    "painted CRPG character sprite, 3/4 top-down view, single character centered, "
    "Baldur's Gate dark fantasy oil painting style, transparent background, no shadow, clean silhouette, "
    "Gerald Brom painterly palette, readable at 64x64, hand-painted infinity engine sprite, production game asset, "
)
ITEM_STYLE_PREFIX = (
    "painted CRPG inventory icon, top-down item render, single item centered, "
    "transparent background, dark fantasy oil painting, crisp readable silhouette, "
    "no text, no frame, painterly game-ready icon, Baldur's Gate style, readable at 64x64, "
)
TILE_STYLE_PREFIX = (
    "painted CRPG terrain tile, seamless tileable texture, top-down, "
    "consistent dark fantasy painterly palette, 64x64 readable structure, hand-painted brushwork, no text, "
)

NEGATIVE_PROMPT = (
    "text, watermark, label, logo, blurry, low contrast, photorealistic, "
    "deformed, noisy, cluttered background, frame, border, poster layout"
)

RARITY_STYLE = {
    "COMMON": "utilitarian, worn but serviceable",
    "UNCOMMON": "slightly embellished, crafted with care",
    "RARE": "striking materials, ornate trim, memorable silhouette",
    "EPIC": "heroic detailing, magical glow accents, prestigious craftsmanship",
    "LEGENDARY": "mythic centerpiece, iconic silhouette, elite artifact quality",
}

ITEM_TYPE_STYLE = {
    "weapon": "weapon icon, one hero prop, visible blade or head, combat-ready",
    "armor": "wearable armor piece icon, one clear equipment item",
    "shield": "shield icon, defensive gear, front-facing readable shape",
    "equipment": "adventuring gear icon, one practical equipment item",
    "tool": "tool icon, crafted utility object, one readable silhouette",
    "consumable": "consumable icon, potion, bomb, ration, or one-use utility",
    "potion": "potion icon in a glass vial, colored liquid, cork stopper",
    "scroll": "rolled parchment scroll with arcane seal",
    "currency": "small stack of coins, gems, shards, or trade token",
    "treasure": "valuable treasure icon, jewel, idol, relic, or luxury item",
    "crafting_material": "raw crafting material, ingot, herb bundle, hide, or reagent",
    "quest": "quest item icon, plot-significant object with memorable silhouette",
    "key": "ornate key icon, metal key with distinct teeth",
}

ITEM_KEYWORD_STYLE = {
    "sword": "long sword icon with readable blade and guard",
    "blade": "blade icon with dramatic edge silhouette",
    "dagger": "dagger icon with short stabbing blade",
    "spear": "spear icon with long shaft and pointed head",
    "axe": "axe icon with heavy crescent head",
    "bow": "bow icon with curved limbs and taut string",
    "staff": "staff icon with carved headpiece",
    "mace": "mace icon with blunt iron head",
    "hammer": "warhammer icon with heavy striking head",
    "shield": "shield icon with strong front profile",
    "helmet": "helmet icon with faceguard or crest",
    "helm": "helmet icon with faceguard or crest",
    "gauntlet": "gauntlet icon with plated glove form",
    "glove": "glove icon with wearable hand silhouette",
    "boots": "boots icon with paired footwear silhouette",
    "cloak": "cloak icon folded as wearable garment",
    "robe": "robe icon with draped cloth silhouette",
    "amulet": "amulet icon with pendant centerpiece",
    "ring": "ring icon with gemstone centerpiece",
    "potion": "potion vial icon with colored liquid",
    "elixir": "alchemical bottle icon with glowing liquid",
    "scroll": "rolled scroll icon with ribbon or seal",
    "tome": "book icon with arcane cover",
    "gem": "cut gemstone icon with luminous facets",
    "crystal": "crystal shard icon with magical glow",
    "ingot": "metal ingot icon with stamped edges",
    "ore": "ore chunk icon with rough mineral facets",
    "herb": "herb bundle icon tied with cord",
    "fang": "monster fang trophy icon",
    "claw": "monster claw trophy icon",
    "hide": "folded hide or pelt icon",
    "bone": "bone fragment trophy icon",
    "essence": "arcane essence vial or glowing mote icon",
    "flesh": "organic trophy icon, unsettling monster tissue",
    "key": "ornate key icon, metal key with distinct teeth",
    "coin": "coin stack icon with embossed face",
    "idol": "small relic idol icon",
}

VIEW_SUFFIX = {
    "topdown": "strict top-down icon presentation",
    "three_quarter": "three-quarter item presentation",
    "side": "side-facing presentation",
}

TEMPLATE_HINTS: list[tuple[list[str], str]] = [
    (["amulet", "pendant", "necklace", "talisman"], "crystal pendant"),
    (["ring", "band"], "gold band ring"),
    (["potion", "elixir", "vial", "phial"], "blue potion"),
    (["scroll"], "scroll"),
    (["tome", "book", "grimoire"], "tome"),
    (["key"], "ornate key"),
    (["arrow"], "arrows"),
    (["bolt"], "bolts"),
    (["coin", "gold", "silver"], "large stacks of coins"),
    (["purse"], "coin purse"),
    (["dagger", "dirk", "knife"], "dagger"),
    (["rapier"], "rapier"),
    (["scimitar", "sabre", "saber", "shotel", "kukri"], "scimitar"),
    (["flamberge", "greatsword", "great sword", "zweihander"], "great sword"),
    (["sword", "blade"], "long sword"),
    (["spear", "lance", "pike"], "spear"),
    (["trident"], "trident"),
    (["axe", "hatchet"], "battle axe"),
    (["halberd"], "halberd"),
    (["hammer", "maul"], "hammer"),
    (["mace"], "mace 1"),
    (["club"], "club"),
    (["flail"], "flail 2"),
    (["crossbow"], "crossbow"),
    (["bow"], "long bow"),
    (["staff", "wand", "rod"], "crystal staff"),
    (["shield", "buckler"], "kite shield"),
    (["breastplate", "plate armor", "plate"], "chest plate"),
    (["chain", "mail"], "chain mail"),
    (["scale"], "scale mail"),
    (["robe"], "robe"),
    (["armor", "armour"], "leather armor"),
    (["gauntlet"], "gauntlets"),
    (["gloves"], "leather gloves"),
    (["greaves"], "greaves"),
    (["boots"], "leather boots"),
    (["shoes"], "shoes"),
    (["helm", "helmet"], "plate helm 1"),
    (["hood"], "cloth hood"),
    (["hat"], "wide-brimmed hat"),
    (["ingot"], "gold bar"),
    (["ore"], "stone pendant"),
    (["crystal", "shard", "gem", "geode"], "crystal pendant"),
    (["essence", "orb"], "blue potion"),
    (["map", "fragment"], "page"),
    (["egg"], "stone pendant"),
    (["heart"], "ruby ring"),
    (["thread"], "scroll 2"),
    (["rune"], "page"),
    (["flesh"], "brown vial"),
]

COLOR_HINTS: list[tuple[list[str], tuple[int, int, int]]] = [
    (["abyss", "shadow", "void", "dark", "night", "onyx"], (96, 72, 150)),
    (["frost", "ice", "frozen", "winter"], (120, 210, 255)),
    (["flame", "fire", "inferno", "ember", "ash"], (255, 128, 52)),
    (["poison", "venom", "acid", "toxic"], (102, 220, 86)),
    (["holy", "sun", "radiant", "blessed"], (255, 220, 112)),
    (["storm", "lightning", "thunder"], (122, 160, 255)),
    (["blood", "crimson", "ruby", "dragon"], (222, 70, 76)),
    (["ethereal", "arcane", "astral", "mana"], (126, 122, 255)),
    (["emerald", "jade"], (70, 204, 136)),
    (["gold", "gilded"], (242, 193, 88)),
    (["silver"], (198, 208, 228)),
]

RARITY_GLOW = {
    "COMMON": 0,
    "UNCOMMON": 1,
    "RARE": 2,
    "EPIC": 3,
    "LEGENDARY": 4,
}

SPRITE_DEFS = {
    "warrior": "armored human warrior with sword and shield, steel plate armor, stoic expression",
    "mage": "robed human mage with glowing staff, blue mystical robes, wise expression",
    "rogue": "hooded human rogue with daggers, dark leather armor, cunning expression",
    "priest": "holy human priest with golden staff, white and gold robes, serene expression",
    "merchant": "portly merchant with bag of gold, colorful clothing, friendly smile",
    "quest_giver": "old wise man with scroll, long grey beard, mysterious aura",
    "innkeeper": "stout innkeeper with mug of ale, apron, welcoming expression",
    "guard": "town guard with spear and helmet, chain mail armor, alert stance",
    "blacksmith": "muscular blacksmith with hammer, leather apron, soot-covered",
    "healer": "gentle healer with herbs and potion, green robes, kind expression",
    "beggar": "ragged beggar with torn clothes, thin and hunched, pleading expression",
    "spy": "shadowy figure with hood and cloak, mysterious, half-hidden face",
    "sage": "ancient sage with book and crystal ball, long white beard, starry robes",
    "goblin": "small green goblin with crude weapon, yellow eyes, menacing grin",
    "skeleton": "undead skeleton warrior with rusty sword, glowing eye sockets",
    "wolf": "fierce grey wolf, bared teeth, wild fur, predatory stance",
    "orc": "large green orc warrior with battle axe, tribal war paint",
    "spider": "giant dark spider, multiple red eyes, hairy legs, venomous fangs",
    "bandit": "masked bandit with crossbow, ragged dark clothing",
    "dragon": "small dragon with wings spread, scales gleaming, fire breath",
    "zombie": "shambling undead zombie, torn clothes, decaying flesh, vacant eyes",
    "bard": "cheerful bard with lute, colorful feathered hat, performing stance",
    "witch": "old witch with pointed hat and black cat, green potion bubbling",
    "knight": "noble knight in shining full plate armor, blue cape, standing with sword raised, no horse",
    "thief": "nimble thief with lockpicks, dark mask, crouching position",
    "necromancer": "dark necromancer with skull staff, purple dark robes, ghostly aura",
    "troll": "large bridge troll with club, mossy skin, small angry eyes",
    "rat": "giant sewer rat, matted fur, red beady eyes, long tail",
    "ghost": "translucent white ghost floating, wispy ethereal body, glowing hollow eyes",
    "mimic": "wooden treasure chest monster with sharp teeth and long tongue, open lid reveals fangs",
    "fairy": "tiny glowing fairy with butterfly wings, magical sparkles",
}

TILE_DEFS = {
    "stone_floor": "dungeon stone floor, grey cobblestone, worn and cracked",
    "stone_wall": "dungeon stone wall, dark grey blocks, moss patches",
    "grass": "green grass field, short blades, few wildflowers",
    "dirt_path": "brown dirt path, footprints, packed earth",
    "water": "blue water surface, gentle ripples, reflective",
    "door": "wooden door with iron hinges, arched frame",
    "chest": "wooden treasure chest with gold lock, slightly open",
    "stairs": "stone staircase going down, torchlit",
    "cobblestone": "town cobblestone road, grey and tan stones",
    "wood_floor": "wooden plank floor, warm brown, polished",
    "sand": "desert sand, golden dunes, wind patterns",
    "dark_stone": "dark dungeon stone, obsidian-like, faint purple glow",
    "tavern_floor": "tavern wooden floor with spilled ale stains, warm",
    "lava": "molten lava flow, orange and red, glowing cracks",
    "ice": "frozen ice floor, blue-white, frost crystals",
    "swamp": "murky swamp water, green, lily pads and reeds",
    "marble": "polished marble floor, white with grey veins, elegant",
    "brick": "red brick wall, mortar lines, slightly weathered",
    "cave": "natural cave floor, rough brown stone, stalactite shadows",
    "bridge": "wooden bridge planks, rope sides, creaking",
}

SPRITE_PACK_MAP: dict[str, list[tuple[str, str]]] = {
    "warrior": [("rogues", "male fighter"), ("rogues", "dwarf"), ("pixel_sprite", "warrior")],
    "mage": [("rogues", "male wizard"), ("pixel_sprite", "mage")],
    "rogue": [("rogues", "rogue"), ("rogues", "fencer"), ("pixel_sprite", "rogue")],
    "priest": [("rogues", "priest"), ("rogues", "monk"), ("pixel_sprite", "priest")],
    "merchant": [("rogues", "baker"), ("pixel_sprite", "merchant")],
    "quest_giver": [("rogues", "desert sage"), ("rogues", "druid"), ("pixel_sprite", "quest_giver")],
    "innkeeper": [("rogues", "baker"), ("pixel_sprite", "innkeeper")],
    "guard": [("rogues", "shield knight"), ("rogues", "knight"), ("pixel_sprite", "guard")],
    "blacksmith": [("rogues", "blacksmith"), ("rogues", "male fighter"), ("pixel_sprite", "blacksmith")],
    "healer": [("rogues", "priest"), ("rogues", "druid"), ("pixel_sprite", "healer")],
    "beggar": [("rogues", "monk"), ("pixel_sprite", "beggar")],
    "spy": [("rogues", "rogue"), ("rogues", "bandit")],
    "sage": [("rogues", "desert sage"), ("rogues", "druid"), ("pixel_sprite", "sage")],
    "goblin": [("monsters", "goblin"), ("pixel_sprite", "orc")],
    "skeleton": [("monsters", "skeleton"), ("pixel_sprite", "skeleton")],
    "wolf": [("monsters", "warg_dire_wolf")],
    "orc": [("monsters", "orc"), ("pixel_sprite", "orc")],
    "spider": [("monsters", "giant_spider")],
    "bandit": [("rogues", "bandit"), ("pixel_sprite", "rogue")],
    "dragon": [("monsters", "dragon"), ("monsters", "drake_lesser_dragon")],
    "zombie": [("monsters", "zombie")],
    "bard": [("rogues", "fencer"), ("rogues", "baker"), ("pixel_sprite", "bard")],
    "witch": [("monsters", "hag_witch"), ("pixel_sprite", "wizard")],
    "knight": [("rogues", "knight"), ("rogues", "templar"), ("pixel_sprite", "knight")],
    "thief": [("rogues", "rogue"), ("pixel_sprite", "rogue")],
    "necromancer": [("rogues", "warlock"), ("monsters", "lich")],
    "troll": [("monsters", "troll")],
    "rat": [("monsters", "giant_rat")],
    "ghost": [("monsters", "wraith"), ("monsters", "banshee")],
    "mimic": [("tile_sheet", "chest_closed"), ("pixel_tile", "barrel")],
    "fairy": [("monsters", "forest_spirit"), ("monsters", "dryad")],
}

TILE_PACK_MAP: dict[str, list[tuple[str, str]]] = {
    "stone_floor": [("pixel_tile", "stone_floor"), ("lpc_tile", "stone_floor"), ("tile_sheet", "floor_stone_2_no_bg")],
    "stone_wall": [("tile_sheet", "stone_brick_wall_side_1"), ("pixel_tile", "dark_stone")],
    "grass": [("pixel_tile", "grass"), ("lpc_tile", "grass"), ("tile_sheet", "grass_2_no_bg")],
    "dirt_path": [("pixel_tile", "dirt_path"), ("lpc_tile", "dirt_path"), ("tile_sheet", "dirt_2_no_bg")],
    "water": [("pixel_tile", "water"), ("lpc_tile", "water")],
    "door": [("pixel_tile", "door"), ("lpc_tile", "door"), ("tile_sheet", "framed_door_1_shut")],
    "chest": [("tile_sheet", "chest_closed")],
    "stairs": [("tile_sheet", "staircase_down"), ("tile_sheet", "staircase_up")],
    "cobblestone": [("lpc_tile", "cobblestone"), ("tile_sheet", "floor_stone_1")],
    "wood_floor": [("lpc_tile", "wood_floor")],
    "sand": [("pixel_tile", "sand"), ("lpc_tile", "sand")],
    "dark_stone": [("pixel_tile", "dark_stone"), ("lpc_tile", "dark_stone"), ("tile_sheet", "igneous_wall_side")],
    "tavern_floor": [("lpc_tile", "tavern_floor"), ("lpc_tile", "wood_floor")],
    "lava": [("tile_sheet", "red_stone_floor_2_no_bg"), ("tile_sheet", "red_stone_floor_1_no_bg")],
    "ice": [("tile_sheet", "blue_stone_floor_2"), ("tile_sheet", "blue_stone_floor_1")],
    "swamp": [("lpc_tile", "swamp"), ("tile_sheet", "grass_1_green_bg")],
    "marble": [("pixel_tile", "marble"), ("lpc_tile", "marble")],
    "brick": [("pixel_tile", "brick"), ("tile_sheet", "stone_brick_wall_top")],
    "cave": [("tile_sheet", "dirt_2_no_bg"), ("tile_sheet", "rough_stone_wall_side")],
    "bridge": [("lpc_tile", "wood_floor"), ("pixel_tile", "table")],
}


@dataclass(slots=True)
class Job:
    key: str
    kind: str
    name: str
    prompt: str
    seed: int
    output_relative_path: str
    raw_relative_path: str
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "kind": self.kind,
            "name": self.name,
            "prompt": self.prompt,
            "negative_prompt": NEGATIVE_PROMPT,
            "seed": self.seed,
            "output_relative_path": self.output_relative_path,
            "raw_relative_path": self.raw_relative_path,
            "metadata": self.metadata,
        }


def get_hf_token() -> str:
    return os.environ.get("HF_TOKEN", "") or os.environ.get("HUGGINGFACE_API_KEY", "")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return slug or "asset"


def stable_seed(key: str) -> int:
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big")


def normalize_view(view: str) -> str:
    view = view.strip().lower()
    return view if view in VIEW_SUFFIX else "topdown"


def trim_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def compress_prompt(text: str, max_words: int = 40) -> str:
    words = trim_spaces(text).split(" ")
    if len(words) <= max_words:
        return " ".join(words)
    return " ".join(words[:max_words])


def choose_style_ref(path_or_dir: str | None) -> Path | None:
    if path_or_dir:
        if path_or_dir.strip().lower() in {"none", "off", "disable", "disabled"}:
            return None
        candidate = Path(path_or_dir)
        if candidate.is_file():
            return candidate
        if candidate.is_dir():
            files = sorted(
                p for p in candidate.iterdir() if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
            )
            return files[0] if files else None
    if DEFAULT_STYLE_REF.exists():
        return DEFAULT_STYLE_REF
    return None


def parse_32rogues_index(txt_path: Path) -> dict[str, tuple[int, int]]:
    if not txt_path.exists():
        return {}
    index: dict[str, tuple[int, int]] = {}
    pattern = re.compile(r"^\s*(\d+)\.([a-z])\.\s+(.+?)\s*$", re.IGNORECASE)
    for line in txt_path.read_text(encoding="utf-8").splitlines():
        match = pattern.match(line)
        if not match:
            continue
        row = int(match.group(1)) - 1
        col = ord(match.group(2).lower()) - ord("a")
        label = slugify(match.group(3))
        index[label] = (col, row)
    return index


ROGUES_TEMPLATE_INDEX = parse_32rogues_index(ROGUES_ITEMS_TXT)
ROGUES_ROGUE_INDEX = parse_32rogues_index(ROGUES_ROGUES_TXT)
ROGUES_MONSTER_INDEX = parse_32rogues_index(ROGUES_MONSTERS_TXT)
ROGUES_TILE_INDEX = parse_32rogues_index(ROGUES_TILES_TXT)


def load_name_filters(names: list[str] | None, names_file: str | None) -> set[str]:
    wanted: set[str] = set()
    for name in names or []:
        slug = slugify(name)
        if slug:
            wanted.add(slug)
    if names_file:
        path = Path(names_file)
        if path.exists():
            for raw_line in path.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                wanted.add(slugify(line))
    return wanted


def filter_jobs_by_name(jobs: list[Job], wanted: set[str]) -> list[Job]:
    if not wanted:
        return jobs
    return [
        job
        for job in jobs
        if slugify(job.name) in wanted
        or slugify(str(job.metadata.get("id", ""))) in wanted
        or slugify(job.key) in wanted
    ]


def summarize_effects(item: dict[str, Any]) -> str:
    effects = item.get("effects", [])
    if not isinstance(effects, list) or not effects:
        return ""
    chunks: list[str] = []
    for effect in effects[:3]:
        if not isinstance(effect, dict):
            continue
        effect_type = str(effect.get("type", "")).strip()
        damage_type = str(effect.get("damage_type", "")).strip()
        stat = str(effect.get("stat", "")).strip()
        if effect_type == "damage" and damage_type:
            chunks.append("%s damage accent" % damage_type)
        elif effect_type == "buff" and stat:
            chunks.append("%s buff aura" % stat.lower())
        elif effect_type:
            chunks.append(effect_type.replace("_", " "))
    return ", ".join(chunks)


def item_style_descriptor(item: dict[str, Any]) -> str:
    item_type = str(item.get("type", "equipment")).strip().lower()
    return ITEM_TYPE_STYLE.get(item_type, ITEM_TYPE_STYLE["equipment"])


def infer_item_subject(item: dict[str, Any]) -> str:
    haystack = " ".join(
        [
            str(item.get("name", "")),
            str(item.get("description", "")),
            str(item.get("type", "")),
        ]
    ).lower()
    for keyword, descriptor in ITEM_KEYWORD_STYLE.items():
        if keyword in haystack:
            return descriptor
    return item_style_descriptor(item)


def build_item_prompt(item: dict[str, Any], view: str = "topdown") -> str:
    item_type = str(item.get("type", "equipment")).upper()
    rarity = str(item.get("rarity", "COMMON")).upper()
    name = trim_spaces(str(item.get("name", item.get("id", "Unnamed Item"))))
    description = trim_spaces(str(item.get("description", "")))
    damage_type = trim_spaces(str(item.get("damage_type", "")))
    style = infer_item_subject(item)
    rarity_hint = RARITY_STYLE.get(rarity, RARITY_STYLE["COMMON"])
    effect_hint = summarize_effects(item)
    req_level = ""
    requirements = item.get("requirements", {})
    if isinstance(requirements, dict) and "level" in requirements:
        req_level = "adventurer tier %s quality" % requirements["level"]
    detail_bits = [description, damage_type, effect_hint, req_level]
    detail_text = ", ".join(bit for bit in detail_bits if bit)
    view_text = VIEW_SUFFIX[normalize_view(view)]
    return compress_prompt(
        f"{ITEM_STYLE_PREFIX}{style}, {rarity_hint}, {view_text}, {name}, {item_type.lower()} item, "
        f"{detail_text}"
    )


def build_sprite_prompt(_name: str, description: str) -> str:
    return compress_prompt(SPRITE_STYLE_PREFIX + description)


def build_tile_prompt(_name: str, description: str) -> str:
    return compress_prompt(TILE_STYLE_PREFIX + description + ", seamless edges")


def choose_template_label(item: dict[str, Any]) -> str:
    haystack = " ".join(
        [
            str(item.get("id", "")),
            str(item.get("name", "")),
            str(item.get("description", "")),
            str(item.get("type", "")),
        ]
    ).lower()
    if prefers_primitive_item_icon(haystack, str(item.get("type", "")).lower()):
        return ""
    for keywords, template_name in TEMPLATE_HINTS:
        if any(keyword in haystack for keyword in keywords):
            slug = slugify(template_name)
            if slug in ROGUES_TEMPLATE_INDEX:
                return slug
    item_type = str(item.get("type", "")).lower()
    defaults = {
        "weapon": "long_sword",
        "armor": "leather_armor",
        "shield": "kite_shield",
        "equipment": "ornate_key",
        "tool": "scroll",
        "consumable": "blue_potion",
        "potion": "blue_potion",
        "currency": "large_stacks_of_coins",
        "treasure": "crystal_pendant",
        "crafting_material": "crystal_pendant",
        "quest": "scroll",
    }
    default_label = defaults.get(item_type, "scroll")
    if default_label in ROGUES_TEMPLATE_INDEX:
        return default_label
    return next(iter(ROGUES_TEMPLATE_INDEX), "")


def choose_tint_color(item: dict[str, Any]) -> tuple[int, int, int]:
    haystack = " ".join(
        [
            str(item.get("id", "")),
            str(item.get("name", "")),
            str(item.get("description", "")),
            summarize_effects(item),
            str(item.get("damage_type", "")),
        ]
    ).lower()
    for keywords, color in COLOR_HINTS:
        if any(keyword in haystack for keyword in keywords):
            return color
    rarity = str(item.get("rarity", "COMMON")).upper()
    rarity_defaults = {
        "COMMON": (184, 180, 170),
        "UNCOMMON": (136, 198, 156),
        "RARE": (120, 160, 236),
        "EPIC": (176, 110, 236),
        "LEGENDARY": (248, 190, 84),
    }
    return rarity_defaults.get(rarity, rarity_defaults["COMMON"])


def apply_tint(img: Image.Image, color: tuple[int, int, int], strength: float) -> Image.Image:
    rgba = img.convert("RGBA")
    tint = Image.new("RGBA", rgba.size, (*color, 255))
    mixed = Image.blend(rgba, tint, max(0.0, min(1.0, strength)))
    mixed.putalpha(rgba.getchannel("A"))
    return mixed


def remove_matte_background(img: Image.Image, tolerance: int = 10) -> Image.Image:
    rgba = img.convert("RGBA")
    width, height = rgba.size
    pixels = rgba.load()
    starts = [(0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1)]
    visited: set[tuple[int, int]] = set()
    stack: list[tuple[int, int, tuple[int, int, int]]] = []
    for sx, sy in starts:
        r, g, b, _ = pixels[sx, sy]
        stack.append((sx, sy, (r, g, b)))
    while stack:
        x, y, ref = stack.pop()
        if (x, y) in visited:
            continue
        visited.add((x, y))
        r, g, b, a = pixels[x, y]
        if a == 0:
            continue
        if max(abs(r - ref[0]), abs(g - ref[1]), abs(b - ref[2])) > tolerance:
            continue
        pixels[x, y] = (r, g, b, 0)
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if 0 <= nx < width and 0 <= ny < height and (nx, ny) not in visited:
                stack.append((nx, ny, ref))
    return rgba


def crop_and_fit(img: Image.Image, target: int = 28) -> Image.Image:
    rgba = img.convert("RGBA")
    alpha = rgba.getchannel("A")
    bbox = alpha.getbbox()
    if bbox is None:
        return rgba
    cropped = rgba.crop(bbox)
    scale = min(target / max(1, cropped.width), target / max(1, cropped.height))
    new_size = (
        max(1, int(round(cropped.width * scale))),
        max(1, int(round(cropped.height * scale))),
    )
    resized = cropped.resize(new_size, Image.NEAREST)
    canvas = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    x = (32 - resized.width) // 2
    y = (32 - resized.height) // 2
    canvas.alpha_composite(resized, (x, y))
    return canvas


def add_glow(img: Image.Image, color: tuple[int, int, int], radius: int, alpha: int) -> Image.Image:
    rgba = img.convert("RGBA")
    mask = rgba.getchannel("A")
    glow = Image.new("RGBA", rgba.size, (*color, 0))
    expanded = mask.filter(ImageFilter.GaussianBlur(radius=radius))
    glow.putalpha(expanded.point(lambda value: min(alpha, value)))
    return Image.alpha_composite(glow, rgba)


def draw_corner_sigils(img: Image.Image, seed: int, color: tuple[int, int, int], count: int) -> Image.Image:
    rgba = img.convert("RGBA")
    draw = ImageDraw.Draw(rgba)
    positions = [(4, 4), (27, 5), (6, 27), (25, 25), (16, 4), (28, 16)]
    for index in range(min(count, len(positions))):
        x, y = positions[(seed + index) % len(positions)]
        draw.point((x, y), fill=(*color, 255))
        draw.point((x + 1, y), fill=(*color, 180))
        draw.point((x, y + 1), fill=(*color, 180))
    return rgba


def prefers_primitive_item_icon(haystack: str, item_type: str) -> bool:
    if item_type in {"crafting_material"}:
        return True
    primitive_words = [
        "ingot", "ore", "heart", "egg", "flesh", "hide", "pelt",
        "fragment", "shard", "rune", "essence", "seal", "diamond",
        "emerald", "ruby", "sapphire", "pearl", "opal", "geode",
        "thread", "scale", "fang", "claw", "brain",
        "compass", "backpack", "rucksack", "ring", "amulet", "pendant",
    ]
    return any(word in haystack for word in primitive_words)


def render_primitive_item(item: dict[str, Any], color: tuple[int, int, int], seed: int) -> Image.Image:
    canvas = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    haystack = " ".join([str(item.get("id", "")), str(item.get("name", ""))]).lower()
    if "compass" in haystack:
        draw.ellipse((6, 6, 26, 26), fill=(*color, 255), outline=(245, 235, 190, 255), width=2)
        draw.polygon([(16, 8), (19, 17), (16, 24), (13, 17)], fill=(220, 55, 60, 255))
        draw.line((8, 16, 24, 16), fill=(45, 35, 30, 180), width=1)
    elif any(word in haystack for word in ["backpack", "rucksack", "satchel"]):
        draw.rounded_rectangle((8, 7, 24, 28), radius=4, fill=(*color, 255))
        draw.rectangle((10, 14, 22, 24), outline=(60, 42, 32, 210), width=2)
        draw.arc((10, 3, 22, 15), 180, 360, fill=(225, 205, 170, 230), width=2)
    elif any(word in haystack for word in ["ring", "band"]):
        draw.ellipse((7, 8, 25, 26), outline=(*color, 255), width=5)
        draw.polygon([(16, 3), (21, 8), (16, 13), (11, 8)], fill=(255, 245, 210, 255))
    elif any(word in haystack for word in ["amulet", "pendant", "talisman"]):
        draw.line((10, 6, 16, 14, 22, 6), fill=(230, 220, 190, 230), width=2)
        draw.polygon([(16, 12), (25, 20), (16, 30), (7, 20)], fill=(*color, 255))
        draw.ellipse((13, 18, 19, 24), fill=(255, 250, 220, 180))
    elif "seal" in haystack:
        draw.rounded_rectangle((8, 7, 24, 26), radius=4, fill=(*color, 255))
        draw.rectangle((11, 5, 21, 10), fill=(250, 220, 120, 255))
        draw.line((11, 16, 21, 16), fill=(80, 48, 24, 190), width=1)
        draw.line((12, 20, 20, 20), fill=(80, 48, 24, 160), width=1)
    elif "rune" in haystack:
        draw.polygon([(16, 4), (25, 12), (22, 27), (10, 27), (7, 12)], fill=(*color, 255))
        draw.line((16, 8, 16, 24), fill=(245, 245, 255, 230), width=2)
        draw.line((11, 15, 21, 15), fill=(245, 245, 255, 220), width=1)
    elif any(word in haystack for word in ["essence", "mote"]):
        draw.ellipse((10, 8, 22, 22), fill=(*color, 230))
        draw.ellipse((13, 4, 19, 28), outline=(240, 245, 255, 190), width=2)
        draw.ellipse((4, 13, 28, 19), outline=(*color, 170), width=1)
    elif any(word in haystack for word in ["diamond", "emerald", "ruby", "sapphire", "gem"]):
        draw.polygon([(16, 4), (26, 13), (16, 29), (6, 13)], fill=(*color, 255))
        draw.line((16, 4, 16, 29), fill=(255, 255, 255, 120), width=1)
        draw.line((6, 13, 26, 13), fill=(255, 255, 255, 120), width=1)
    elif "heart" in haystack:
        draw.polygon([(16, 9), (22, 5), (27, 9), (27, 15), (16, 27), (5, 15), (5, 9), (10, 5)], fill=(*color, 255))
    elif "egg" in haystack:
        draw.ellipse((8, 5, 24, 27), fill=(*color, 255))
    elif "belt" in haystack:
        draw.rounded_rectangle((5, 12, 27, 20), radius=3, fill=(*color, 255))
        draw.rectangle((13, 11, 19, 21), outline=(240, 220, 180, 255), width=2)
    elif "ingot" in haystack:
        draw.polygon([(6, 12), (26, 12), (22, 22), (10, 22)], fill=(*color, 255))
        draw.line((10, 15, 23, 15), fill=(255, 245, 210, 130), width=1)
    elif any(word in haystack for word in ["ore", "stone", "fragment", "shard", "geode", "crystal"]):
        draw.polygon([(16, 3), (24, 10), (21, 25), (10, 28), (5, 13)], fill=(*color, 255))
    elif any(word in haystack for word in ["flesh", "hide"]):
        draw.polygon([(7, 8), (24, 6), (27, 18), (18, 26), (6, 21)], fill=(*color, 255))
    elif any(word in haystack for word in ["cloak", "robe"]):
        draw.polygon([(16, 4), (25, 28), (7, 28)], fill=(*color, 255))
        draw.ellipse((12, 4, 20, 12), fill=tuple(max(0, c - 48) for c in color) + (255,))
    elif any(word in haystack for word in ["bread", "loaf"]):
        draw.ellipse((6, 10, 27, 23), fill=(*color, 255))
        for x in (11, 16, 21):
            draw.line((x, 11, x - 2, 20), fill=(120, 72, 32, 170), width=1)
    elif "map" in haystack:
        draw.rectangle((7, 6, 25, 25), fill=(*color, 255))
        draw.line((10, 11, 21, 11), fill=(40, 28, 18, 180), width=1)
        draw.line((11, 16, 19, 19), fill=(40, 28, 18, 180), width=1)
    else:
        draw.ellipse((8, 8, 24, 24), fill=(*color, 255))
    return draw_corner_sigils(canvas, seed, (255, 245, 220), 2)


def apply_view_transform(img: Image.Image, view: str) -> Image.Image:
    rgba = img.convert("RGBA")
    if view == "three_quarter":
        scaled = rgba.resize((28, 32), Image.NEAREST)
        canvas = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
        canvas.alpha_composite(scaled, (2, 0))
        return canvas
    if view == "side":
        scaled = rgba.resize((24, 32), Image.NEAREST)
        canvas = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
        canvas.alpha_composite(scaled, (4, 0))
        return canvas
    return rgba


def render_template_item_icon(item: dict[str, Any], seed: int, view: str = "topdown") -> Image.Image:
    color = choose_tint_color(item)
    label = choose_template_label(item)
    if not ROGUES_ITEMS_PNG.exists() or label not in ROGUES_TEMPLATE_INDEX:
        return apply_view_transform(render_primitive_item(item, color, seed), view)

    source = Image.open(ROGUES_ITEMS_PNG).convert("RGBA")
    col, row = ROGUES_TEMPLATE_INDEX[label]
    cell = source.crop((
        col * ROGUES_CELL_SIZE,
        row * ROGUES_CELL_SIZE,
        (col + 1) * ROGUES_CELL_SIZE,
        (row + 1) * ROGUES_CELL_SIZE,
    )).convert("RGBA")
    cell = remove_matte_background(cell)
    cell = crop_and_fit(cell, target=28)
    if cell.getchannel("A").getbbox() is None:
        return apply_view_transform(render_primitive_item(item, color, seed), view)
    rarity = str(item.get("rarity", "COMMON")).upper()
    strength = {
        "COMMON": 0.10,
        "UNCOMMON": 0.18,
        "RARE": 0.26,
        "EPIC": 0.33,
        "LEGENDARY": 0.40,
    }.get(rarity, 0.15)
    tinted = apply_tint(cell, color, strength)
    glow_steps = RARITY_GLOW.get(rarity, 0)
    if glow_steps > 0:
        tinted = add_glow(tinted, color, radius=1 + glow_steps, alpha=44 + glow_steps * 18)
    sigils = 1 if rarity == "UNCOMMON" else 2 if rarity == "RARE" else 3 if rarity == "EPIC" else 4 if rarity == "LEGENDARY" else 0
    if sigils:
        tinted = draw_corner_sigils(tinted, seed, color, sigils)
    return apply_view_transform(tinted, view)


def _load_rgba(path: Path) -> Image.Image | None:
    if not path.exists():
        return None
    return Image.open(path).convert("RGBA")


def _crop_sheet_cell(sheet_path: Path, index: dict[str, tuple[int, int]], label: str) -> Image.Image | None:
    if not sheet_path.exists() or label not in index:
        return None
    source = Image.open(sheet_path).convert("RGBA")
    col, row = index[label]
    return source.crop((
        col * ROGUES_CELL_SIZE,
        row * ROGUES_CELL_SIZE,
        (col + 1) * ROGUES_CELL_SIZE,
        (row + 1) * ROGUES_CELL_SIZE,
    )).convert("RGBA")


def _normalize_sprite_canvas(img: Image.Image, target: int = 28) -> Image.Image:
    sprite = remove_matte_background(img)
    sprite = crop_and_fit(sprite, target=target)
    alpha = sprite.getchannel("A")
    bbox = alpha.getbbox()
    if bbox is None:
        return sprite
    cropped = sprite.crop(bbox)
    canvas = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    x = (32 - cropped.width) // 2
    y = 32 - cropped.height
    canvas.alpha_composite(cropped, (x, y))
    return canvas


def _make_mimic_sprite(seed: int) -> Image.Image:
    tile = _crop_sheet_cell(ROGUES_TILES_PNG, ROGUES_TILE_INDEX, "chest_closed")
    base = tile if tile is not None else Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    draw = ImageDraw.Draw(base)
    draw.rectangle((8, 13, 24, 16), fill=(35, 18, 16, 230))
    tooth_color = (240, 230, 215, 255)
    for x in range(9, 24, 4):
        draw.polygon([(x, 13), (x + 2, 17), (x + 4, 13)], fill=tooth_color)
    tongue_x = 14 + (seed % 4)
    draw.rectangle((tongue_x, 16, tongue_x + 4, 23), fill=(182, 54, 92, 255))
    draw.ellipse((10, 8, 14, 12), fill=(248, 230, 120, 255))
    draw.ellipse((18, 8, 22, 12), fill=(248, 230, 120, 255))
    return _normalize_sprite_canvas(base, target=26)


def render_pack_sprite(name: str, seed: int) -> Image.Image:
    for source_kind, label in SPRITE_PACK_MAP.get(name, []):
        candidate: Image.Image | None = None
        if source_kind == "pixel_sprite":
            candidate = _load_rgba(PIXEL_CRAWLER_SPRITE_DIR / f"{label}.png")
        elif source_kind == "rogues":
            candidate = _crop_sheet_cell(ROGUES_ROGUES_PNG, ROGUES_ROGUE_INDEX, slugify(label))
        elif source_kind == "monsters":
            candidate = _crop_sheet_cell(ROGUES_MONSTERS_PNG, ROGUES_MONSTER_INDEX, slugify(label))
        elif source_kind == "tile_sheet":
            candidate = _crop_sheet_cell(ROGUES_TILES_PNG, ROGUES_TILE_INDEX, slugify(label))
        elif source_kind == "pixel_tile":
            candidate = _load_rgba(PIXEL_CRAWLER_TILE_DIR / f"{label}.png")
        if candidate is not None:
            return _normalize_sprite_canvas(candidate, target=28 if name != "mimic" else 26)
    if name == "mimic":
        return _make_mimic_sprite(seed)
    fallback = legacy_output_path_for_job(Job("", "sprites", name, "", seed, "", "", {}))
    if fallback is not None and fallback.exists():
        return _normalize_sprite_canvas(Image.open(fallback).convert("RGBA"))
    return _normalize_sprite_canvas(Image.new("RGBA", (32, 32), (0, 0, 0, 0)))


def _tint_tile(img: Image.Image, color: tuple[int, int, int], strength: float) -> Image.Image:
    return apply_tint(img.convert("RGBA"), color, strength)


def _render_bridge_tile(seed: int) -> Image.Image:
    base = _load_rgba(LPC_TILE_DIR / "wood_floor.png") or Image.new("RGBA", (32, 32), (120, 90, 60, 255))
    base = crop_and_fit(base, target=32)
    draw = ImageDraw.Draw(base)
    rail_color = (58, 44, 31, 255)
    plank_color = (166, 122, 72, 190)
    for x in (4, 27):
        draw.line((x, 2, x, 29), fill=rail_color, width=2)
    for y in range(5, 29, 6):
        draw.line((2, y, 29, y), fill=plank_color, width=1)
    if seed % 2 == 0:
        draw.line((15, 2, 15, 29), fill=(90, 68, 48, 140), width=1)
    return base


def render_pack_tile(name: str, seed: int) -> Image.Image:
    for source_kind, label in TILE_PACK_MAP.get(name, []):
        candidate: Image.Image | None = None
        if source_kind == "pixel_tile":
            candidate = _load_rgba(PIXEL_CRAWLER_TILE_DIR / f"{label}.png")
        elif source_kind == "lpc_tile":
            candidate = _load_rgba(LPC_TILE_DIR / f"{label}.png")
        elif source_kind == "tile_sheet":
            candidate = _crop_sheet_cell(ROGUES_TILES_PNG, ROGUES_TILE_INDEX, slugify(label))
        if candidate is not None:
            tile = candidate.convert("RGBA").resize((32, 32), Image.NEAREST)
            if name == "lava":
                return _tint_tile(tile, (255, 118, 36), 0.28)
            if name == "ice":
                return _tint_tile(tile, (152, 214, 255), 0.18)
            if name == "swamp":
                return _tint_tile(tile, (82, 132, 84), 0.16)
            if name == "cave":
                return _tint_tile(tile, (122, 98, 76), 0.12)
            return tile
    if name == "bridge":
        return _render_bridge_tile(seed)
    fallback = legacy_output_path_for_job(Job("", "tiles", name, "", seed, "", "", {}))
    if fallback is not None and fallback.exists():
        return Image.open(fallback).convert("RGBA").resize((32, 32), Image.NEAREST)
    return Image.new("RGBA", (32, 32), (24, 20, 28, 255))


def build_item_jobs(
    limit: int | None = None,
    views: list[str] | None = None,
    variants: int = 1,
) -> list[Job]:
    payload = load_json(ITEMS_FILE)
    items = payload.get("items", [])
    if not isinstance(items, list):
        return []

    normalized_views = [normalize_view(v) for v in (views or ["topdown"])]
    jobs: list[Job] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        item_id = trim_spaces(str(item.get("id", "")))
        if not item_id:
            continue
        item_name = trim_spaces(str(item.get("name", item_id)))
        for view in normalized_views:
            for variant_index in range(variants):
                key = f"item_{item_id}_{view}_v{variant_index + 1:02d}"
                view_suffix = "" if view == "topdown" else f"_{view}"
                variant_suffix = "" if variants == 1 else f"_v{variant_index + 1:02d}"
                jobs.append(
                    Job(
                        key=key,
                        kind="items",
                        name=item_name,
                        prompt=build_item_prompt(item, view=view),
                        seed=stable_seed(key),
                        output_relative_path=f"items/{slugify(item_id)}{view_suffix}{variant_suffix}.png",
                        raw_relative_path=f"asset_raw/{key}_raw.png",
                        metadata={
                            "id": item_id,
                            "type": str(item.get("type", "equipment")),
                            "rarity": str(item.get("rarity", "COMMON")),
                            "description": str(item.get("description", "")),
                            "damage_type": str(item.get("damage_type", "")),
                            "view": view,
                            "variant": variant_index + 1,
                        },
                    )
                )
                if limit is not None and len(jobs) >= limit:
                    return jobs
    return jobs


def build_sprite_jobs(limit: int | None = None, variants: int = 1) -> list[Job]:
    jobs: list[Job] = []
    count = 0
    for name, description in SPRITE_DEFS.items():
        for variant_index in range(variants):
            key = f"sprite_{name}_v{variant_index + 1:02d}"
            variant_suffix = "" if variants == 1 else f"_v{variant_index + 1:02d}"
            jobs.append(
                Job(
                    key=key,
                    kind="sprites",
                    name=name,
                    prompt=build_sprite_prompt(name, description),
                    seed=stable_seed(key),
                    output_relative_path=f"sprites/{name}{variant_suffix}.png",
                    raw_relative_path=f"asset_raw/{key}_raw.png",
                    metadata={"family": "sprite", "variant": variant_index + 1},
                )
            )
            count += 1
            if limit is not None and count >= limit:
                return jobs
    return jobs


def build_tile_jobs(limit: int | None = None, variants: int = 1) -> list[Job]:
    jobs: list[Job] = []
    count = 0
    for name, description in TILE_DEFS.items():
        for variant_index in range(variants):
            key = f"tile_{name}_v{variant_index + 1:02d}"
            variant_suffix = "" if variants == 1 else f"_v{variant_index + 1:02d}"
            jobs.append(
                Job(
                    key=key,
                    kind="tiles",
                    name=name,
                    prompt=build_tile_prompt(name, description),
                    seed=stable_seed(key),
                    output_relative_path=f"tiles/{name}{variant_suffix}.png",
                    raw_relative_path=f"asset_raw/{key}_raw.png",
                    metadata={"family": "tile", "variant": variant_index + 1},
                )
            )
            count += 1
            if limit is not None and count >= limit:
                return jobs
    return jobs


def build_jobs(
    kind: str,
    limit: int | None = None,
    views: list[str] | None = None,
    variants: int = 1,
) -> list[Job]:
    if kind == "items":
        return build_item_jobs(limit=limit, views=views, variants=variants)
    if kind == "sprites":
        return build_sprite_jobs(limit=limit, variants=variants)
    if kind == "tiles":
        return build_tile_jobs(limit=limit, variants=variants)
    if kind == "all":
        jobs: list[Job] = []
        jobs.extend(build_sprite_jobs(variants=variants))
        jobs.extend(build_tile_jobs(variants=variants))
        jobs.extend(build_item_jobs(views=views, variants=variants))
        return jobs[:limit] if limit is not None else jobs
    raise ValueError("Unsupported kind: %s" % kind)


def plan_path(kind: str) -> Path:
    PLAN_DIR.mkdir(parents=True, exist_ok=True)
    return PLAN_DIR / f"{kind}_plan.json"


def write_plan(kind: str, jobs: list[Job]) -> Path:
    path = plan_path(kind)
    payload = {
        "kind": kind,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "count": len(jobs),
        "jobs": [job.to_dict() for job in jobs],
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def generate_image_hf_api(prompt: str, retries: int = 3) -> Image.Image | None:
    token = get_hf_token()
    if not token:
        print("[ERROR] HF_TOKEN/HUGGINGFACE_API_KEY not set.")
        return None

    headers = {"Authorization": f"Bearer {token}"}
    payload = {"inputs": prompt}
    for _attempt in range(retries):
        try:
            resp = requests.post(LEGACY_HF_API_URL, headers=headers, json=payload, timeout=60)
            if resp.status_code == 200:
                return Image.open(BytesIO(resp.content))
            if resp.status_code == 503:
                wait = resp.json().get("estimated_time", 30)
                print("  Model loading, waiting %.0fs..." % wait)
                time.sleep(min(wait, 60))
                continue
            if resp.status_code == 429:
                print("  Rate limited, waiting 10s...")
                time.sleep(10)
                continue
            print("  API error %s: %s" % (resp.status_code, resp.text[:200]))
        except Exception as exc:  # pragma: no cover - network path
            print("  Request failed: %s" % exc)
        time.sleep(5)
    return None


class LocalSDXLGenerator:
    def __init__(
        self,
        model_id: str,
        style_ref: Path | None,
        lora_stack: list[tuple[str, str, float]] | None = None,
        single_lora_path: str | None = None,
        single_lora_scale: float = 0.8,
        ip_adapter_repo: str = DEFAULT_IP_ADAPTER_REPO,
        ip_adapter_weight: str = DEFAULT_IP_ADAPTER_WEIGHT,
        ip_adapter_scale: float = 0.7,
        cpu_offload: bool = True,
        use_lcm: bool = USE_LCM_BY_DEFAULT,
    ) -> None:
        try:
            import torch
            from diffusers import AutoPipelineForText2Image, LCMScheduler
            from diffusers.utils import load_image
        except ImportError as exc:  # pragma: no cover - depends on local environment
            raise SystemExit(
                "Local SDXL backend requires torch, diffusers, and transformers. "
                "Install them before using --backend local_sdxl."
            ) from exc

        self.torch = torch
        self.load_image = load_image
        self.use_lcm = use_lcm
        self.pipeline = AutoPipelineForText2Image.from_pretrained(
            model_id,
            torch_dtype=torch.float16,
            use_safetensors=True,
            variant="fp16",
        )

        # IP-Adapter (style anchor image conditioning — runs alongside LoRA stack)
        self.style_image = None
        if style_ref and style_ref.exists():
            try:
                self.pipeline.load_ip_adapter(
                    ip_adapter_repo,
                    subfolder="sdxl_models",
                    weight_name=ip_adapter_weight,
                )
                self.pipeline.set_ip_adapter_scale(ip_adapter_scale)
                self.style_image = self.load_image(str(style_ref))
            except Exception as exc:  # pragma: no cover - model environment dependent
                print("[WARN] Could not load IP-Adapter style reference: %s" % exc)

        # LoRA stacking via set_adapters (multi-LoRA). single_lora_path takes precedence if supplied.
        # Do NOT call fuse_lora — it prevents per-adapter weight control and later unload/swap.
        loaded_adapters: list[str] = []
        loaded_weights: list[float] = []
        if single_lora_path:
            try:
                self.pipeline.load_lora_weights(single_lora_path, adapter_name="user_override")
                loaded_adapters.append("user_override")
                loaded_weights.append(float(single_lora_scale))
                print(f"[LoRA] single-override: {single_lora_path} scale={single_lora_scale}")
            except Exception as exc:  # pragma: no cover
                print("[WARN] Could not load override LoRA: %s" % exc)
        elif lora_stack:
            for adapter_name, path, scale in lora_stack:
                if not Path(path).exists():
                    print(f"[WARN] LoRA not found, skipping: {adapter_name} -> {path}")
                    continue
                try:
                    self.pipeline.load_lora_weights(path, adapter_name=adapter_name)
                    loaded_adapters.append(adapter_name)
                    loaded_weights.append(float(scale))
                    print(f"[LoRA] loaded: {adapter_name} scale={scale}")
                except Exception as exc:  # pragma: no cover
                    print(f"[WARN] Could not load LoRA {adapter_name}: {exc}")

        if loaded_adapters:
            try:
                self.pipeline.set_adapters(loaded_adapters, adapter_weights=loaded_weights)
                print(f"[LoRA] stack active: {loaded_adapters} weights={loaded_weights}")
            except Exception as exc:  # pragma: no cover
                print(f"[WARN] set_adapters failed: {exc}")

        # LCM scheduler swap — only when the lcm adapter is active (otherwise 8-step is bad)
        self._effective_lcm = bool(self.use_lcm and "lcm" in loaded_adapters)
        if self._effective_lcm:
            self.pipeline.scheduler = LCMScheduler.from_config(self.pipeline.scheduler.config)
            print("[LCM] scheduler swapped to LCMScheduler — sampling at 8 steps")
        elif self.use_lcm:
            print("[LCM] requested but lcm adapter not loaded; keeping default scheduler")

        self.pipeline.enable_attention_slicing()
        self.pipeline.vae.enable_slicing()
        if cpu_offload:
            self.pipeline.enable_model_cpu_offload()
        else:
            self.pipeline.to("cuda")

    def generate(
        self,
        prompt: str,
        seed: int,
        negative_prompt: str,
        width: int,
        height: int,
        steps: int,
        guidance_scale: float,
    ) -> Image.Image:
        # LCM override — 8 steps with CFG ~1.5 is the canonical sweet spot.
        if self._effective_lcm:
            steps = LCM_STEPS
            guidance_scale = LCM_GUIDANCE
        generator = self.torch.Generator(device="cpu").manual_seed(seed)
        kwargs: dict[str, Any] = {
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "num_inference_steps": steps,
            "guidance_scale": guidance_scale,
            "height": height,
            "width": width,
            "generator": generator,
        }
        if self.style_image is not None:
            kwargs["ip_adapter_image"] = self.style_image
        return self.pipeline(**kwargs).images[0]

    def cleanup(self) -> None:
        if self.torch.cuda.is_available():
            self.torch.cuda.empty_cache()


def remove_background(img: Image.Image) -> Image.Image:
    try:
        from rembg import remove

        buf = BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        result = remove(buf.read())
        return Image.open(BytesIO(result)).convert("RGBA")
    except ImportError:
        return img.convert("RGBA")


def quantize_pixel_art(img: Image.Image, colors: int = 32) -> Image.Image:
    rgba = img.convert("RGBA")
    alpha = rgba.getchannel("A")
    rgb = rgba.convert("RGB").quantize(colors=colors, method=Image.MEDIANCUT).convert("RGB")
    return Image.merge("RGBA", (*rgb.split(), alpha))


def postprocess_sprite(raw_img: Image.Image, final_size: tuple[int, int]) -> Image.Image:
    # Painted CRPG sprite pipeline: raw 1024 -> 256 NEAREST -> 64 NEAREST (power-of-2 chain, no LANCZOS blur)
    # Softer contrast/saturation boosts than old 32x32 path since painted 64x64 preserves natural brushwork.
    img = remove_background(raw_img)
    img = ImageEnhance.Contrast(img).enhance(1.08)
    img = ImageEnhance.Color(img).enhance(1.12)
    img = img.resize(UPSCALE_SIZE, DOWNSAMPLE_RESAMPLE)
    img = quantize_pixel_art(img, colors=64)
    return img.resize(final_size, DOWNSAMPLE_RESAMPLE)


def postprocess_tile(raw_img: Image.Image, final_size: tuple[int, int]) -> Image.Image:
    img = raw_img.convert("RGBA")
    img = ImageEnhance.Contrast(img).enhance(1.05)
    img = ImageEnhance.Color(img).enhance(1.08)
    img = img.resize(UPSCALE_SIZE, DOWNSAMPLE_RESAMPLE)
    img = quantize_pixel_art(img, colors=72)
    return img.resize(final_size, DOWNSAMPLE_RESAMPLE)


def postprocess_item(raw_img: Image.Image, final_size: tuple[int, int]) -> Image.Image:
    img = remove_background(raw_img)
    img = ImageEnhance.Contrast(img).enhance(1.08)
    img = ImageEnhance.Color(img).enhance(1.15)
    img = img.resize(UPSCALE_SIZE, DOWNSAMPLE_RESAMPLE)
    img = quantize_pixel_art(img, colors=56)
    return img.resize(final_size, DOWNSAMPLE_RESAMPLE)


def has_visible_pixels(img: Image.Image) -> bool:
    rgba = img.convert("RGBA")
    alpha = rgba.getchannel("A")
    return alpha.getbbox() is not None


def load_cache() -> dict[str, Any]:
    if CACHE_FILE.exists():
        return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    return {}


def save_cache(cache: dict[str, Any]) -> None:
    CACHE_FILE.write_text(json.dumps(cache, indent=2), encoding="utf-8")


def _manifest_entry(job: Job, cache: dict[str, Any], size: tuple[int, int]) -> dict[str, Any]:
    cached = cache.get(job.key, {})
    return {
        "relative_path": job.output_relative_path,
        "size": list(size),
        "cached_at": cached.get("cached_at", cached.get("generated", "")),
        "seed": job.seed,
        "metadata": job.metadata,
    }


def write_manifest(cache: dict[str, Any], jobs: list[Job] | None = None) -> None:
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, Any] = {
        "version": 2,
        "generated_at": time.strftime("%Y-%m-%d %H:%M"),
        "sprite_size": list(GENERATED_SIZE),
        "item_size": list(ITEM_SIZE),
        "tiles": {},
        "sprites": {},
        "items": {},
    }

    jobs_to_emit = jobs or build_jobs("all", views=["topdown"], variants=1)
    for job in jobs_to_emit:
        output_path = GENERATED_DIR / job.output_relative_path
        if not output_path.exists():
            continue
        if job.kind == "sprites":
            variant = int(job.metadata.get("variant", 1))
            key = slugify(job.name or job.key)
            if variant > 1:
                key = f"{key}_v{variant:02d}"
            manifest["sprites"][key] = _manifest_entry(job, cache, GENERATED_SIZE)
        elif job.kind == "tiles":
            variant = int(job.metadata.get("variant", 1))
            key = slugify(job.name or job.key)
            if variant > 1:
                key = f"{key}_v{variant:02d}"
            manifest["tiles"][key] = _manifest_entry(job, cache, GENERATED_SIZE)
        elif job.kind == "items":
            asset_id = str(job.metadata.get("id", slugify(job.name)))
            view = str(job.metadata.get("view", "topdown"))
            variant = int(job.metadata.get("variant", 1))
            key = asset_id if view == "topdown" else f"{asset_id}_{view}"
            if variant > 1:
                key = f"{key}_v{variant:02d}"
            manifest["items"][key] = _manifest_entry(job, cache, ITEM_SIZE)

    MANIFEST_FILE.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def ensure_output_dirs() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    LEGACY_SPRITE_DIR.mkdir(parents=True, exist_ok=True)
    LEGACY_TILE_DIR.mkdir(parents=True, exist_ok=True)
    GENERATED_SPRITE_DIR.mkdir(parents=True, exist_ok=True)
    GENERATED_TILE_DIR.mkdir(parents=True, exist_ok=True)
    GENERATED_ITEM_DIR.mkdir(parents=True, exist_ok=True)


def output_paths_for_job(job: Job) -> tuple[Path, Path]:
    raw_path = PROJECT_ROOT / "tools" / job.raw_relative_path
    output_path = GENERATED_DIR / job.output_relative_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    return raw_path, output_path


def legacy_output_path_for_job(job: Job) -> Path | None:
    if job.kind == "sprites":
        return LEGACY_SPRITE_DIR / f"{slugify(job.name)}.png"
    if job.kind == "tiles":
        return LEGACY_TILE_DIR / f"{slugify(job.name)}.png"
    return None


def generate_jobs(
    jobs: list[Job],
    backend: str,
    force: bool,
    model_id: str,
    style_ref_path: str | None,
    steps: int,
    guidance_scale: float,
    width: int,
    height: int,
    gc_every: int,
    pause_ms: int,
    lora_stack: list[tuple[str, str, float]] | None,
    single_lora_path: str | None,
    single_lora_scale: float,
    use_lcm: bool,
) -> None:
    ensure_output_dirs()
    cache = load_cache()
    style_ref = choose_style_ref(style_ref_path)

    local_backend = None
    if backend == "local_sdxl":
        local_backend = LocalSDXLGenerator(
            model_id=model_id,
            style_ref=style_ref,
            lora_stack=lora_stack,
            single_lora_path=single_lora_path,
            single_lora_scale=single_lora_scale,
            use_lcm=use_lcm,
        )

    total = len(jobs)
    for index, job in enumerate(jobs, 1):
        raw_path, output_path = output_paths_for_job(job)
        legacy_path = legacy_output_path_for_job(job)

        if not force and cache.get(job.key) and output_path.exists():
            print(f"[{index}/{total}] {job.key} — cached, skip")
            continue

        print(f"[{index}/{total}] Generating {job.key}...")
        if backend == "hf_api_flux":
            raw_img = generate_image_hf_api(job.prompt)
        elif backend == "local_sdxl":
            raw_img = local_backend.generate(
                prompt=job.prompt,
                seed=job.seed,
                negative_prompt=NEGATIVE_PROMPT,
                width=width,
                height=height,
                steps=steps,
                guidance_scale=guidance_scale,
            )
        elif backend == "template_32rogues":
            item_payload = {
                "id": str(job.metadata.get("id", job.key)),
                "name": job.name,
                "description": str(job.metadata.get("description", "")),
                "type": str(job.metadata.get("type", "")),
                "rarity": str(job.metadata.get("rarity", "COMMON")),
                "damage_type": str(job.metadata.get("damage_type", "")),
            }
            raw_img = render_template_item_icon(
                item_payload,
                seed=job.seed,
                view=str(job.metadata.get("view", "topdown")),
            )
        elif backend == "deterministic_pack":
            if job.kind == "sprites":
                raw_img = render_pack_sprite(slugify(job.name), job.seed)
            elif job.kind == "tiles":
                raw_img = render_pack_tile(slugify(job.name), job.seed)
            elif job.kind == "items":
                item_payload = {
                    "id": str(job.metadata.get("id", job.key)),
                    "name": job.name,
                    "description": str(job.metadata.get("description", "")),
                    "type": str(job.metadata.get("type", "")),
                    "rarity": str(job.metadata.get("rarity", "COMMON")),
                    "damage_type": str(job.metadata.get("damage_type", "")),
                }
                raw_img = render_template_item_icon(
                    item_payload,
                    seed=job.seed,
                    view=str(job.metadata.get("view", "topdown")),
                )
            else:
                raw_img = None
        else:
            raise SystemExit(f"Unsupported backend: {backend}")

        if raw_img is None:
            print(f"  [FAIL] Could not generate {job.key}")
            continue

        raw_img.save(str(raw_path))

        if job.kind == "sprites":
            final_img = postprocess_sprite(raw_img, SPRITE_SIZE)
            generated_img = postprocess_sprite(raw_img, GENERATED_SIZE)
        elif job.kind == "tiles":
            final_img = postprocess_tile(raw_img, SPRITE_SIZE)
            generated_img = postprocess_tile(raw_img, GENERATED_SIZE)
        elif job.kind == "items" and backend in {"template_32rogues", "deterministic_pack"}:
            final_img = raw_img.convert("RGBA")
            generated_img = final_img
        elif job.kind == "sprites" and backend == "deterministic_pack":
            final_img = raw_img.convert("RGBA").resize(SPRITE_SIZE, Image.NEAREST)
            generated_img = final_img.resize(GENERATED_SIZE, Image.NEAREST)
        elif job.kind == "tiles" and backend == "deterministic_pack":
            final_img = raw_img.convert("RGBA").resize(SPRITE_SIZE, Image.NEAREST)
            generated_img = final_img.resize(GENERATED_SIZE, Image.NEAREST)
        else:
            final_img = postprocess_item(raw_img, ITEM_SIZE)
            generated_img = final_img

        if job.kind in {"sprites", "items"} and not has_visible_pixels(generated_img):
            print(f"  [FAIL] {job.key} produced an empty transparent image")
            if raw_path.exists():
                raw_path.unlink(missing_ok=True)
            if output_path.exists():
                output_path.unlink(missing_ok=True)
            continue

        generated_img.save(str(output_path))
        if legacy_path is not None:
            legacy_path.parent.mkdir(parents=True, exist_ok=True)
            final_img.save(str(legacy_path))

        cache[job.key] = {
            "cached_at": time.strftime("%Y-%m-%d %H:%M"),
            "prompt": job.prompt[:240],
            "seed": job.seed,
            "raw": str(raw_path),
            "final": str(legacy_path) if legacy_path is not None else "",
            "generated_path": str(output_path),
            "metadata": job.metadata,
            "backend": backend,
            "model_id": (
                model_id
                if backend == "local_sdxl"
                else "deterministic_pack" if backend == "deterministic_pack"
                else "template_32rogues" if backend == "template_32rogues"
                else "black-forest-labs/FLUX.1-schnell"
            ),
        }
        save_cache(cache)
        write_manifest(cache)
        del raw_img
        del final_img
        del generated_img
        if local_backend is not None and gc_every > 0 and index % gc_every == 0:
            gc.collect()
            local_backend.cleanup()
        if pause_ms > 0:
            time.sleep(pause_ms / 1000.0)


def reprocess_all() -> None:
    ensure_output_dirs()
    for raw_file in sorted(RAW_DIR.glob("sprite_*_raw.png")):
        name = raw_file.stem.replace("sprite_", "").replace("_raw", "")
        raw_img = Image.open(raw_file)
        postprocess_sprite(raw_img, SPRITE_SIZE).save(str(LEGACY_SPRITE_DIR / f"{name}.png"))
        postprocess_sprite(raw_img, GENERATED_SIZE).save(str(GENERATED_SPRITE_DIR / f"{name}.png"))

    for raw_file in sorted(RAW_DIR.glob("tile_*_raw.png")):
        name = raw_file.stem.replace("tile_", "").replace("_raw", "")
        raw_img = Image.open(raw_file)
        postprocess_tile(raw_img, SPRITE_SIZE).save(str(LEGACY_TILE_DIR / f"{name}.png"))
        postprocess_tile(raw_img, GENERATED_SIZE).save(str(GENERATED_TILE_DIR / f"{name}.png"))

    for raw_file in sorted(RAW_DIR.glob("item_*_raw.png")):
        name = raw_file.stem.replace("item_", "").replace("_raw", "")
        raw_img = Image.open(raw_file)
        postprocess_item(raw_img, ITEM_SIZE).save(str(GENERATED_ITEM_DIR / f"{name}.png"))

    write_manifest(load_cache())


def list_assets() -> None:
    print("=== DATA-DRIVEN JOB COUNTS ===")
    print("sprites:", len(build_sprite_jobs()))
    print("tiles  :", len(build_tile_jobs()))
    print("items  :", len(build_item_jobs()))
    print("")
    print("=== GENERATED STATUS ===")
    for label, path in [
        ("manifest", MANIFEST_FILE),
        ("generated sprites", GENERATED_SPRITE_DIR),
        ("generated tiles", GENERATED_TILE_DIR),
        ("generated items", GENERATED_ITEM_DIR),
    ]:
        print(f"{label:18s} {'OK' if path.exists() else 'MISSING'}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ember RPG asset pipeline")
    parser.add_argument("--plan", choices=["sprites", "tiles", "items", "all"], help="Write deterministic job plan")
    parser.add_argument("--generate", choices=["sprites", "tiles", "items", "all"], help="Generate assets")
    parser.add_argument(
        "--backend",
        choices=["local_sdxl", "hf_api_flux", "template_32rogues", "deterministic_pack"],
        default="local_sdxl",
    )
    parser.add_argument("--model-id", default=DEFAULT_LOCAL_MODEL_ID)
    parser.add_argument("--style-ref", help="Style anchor image or folder")
    parser.add_argument("--views", nargs="+", default=["topdown"], help="Item views to generate")
    parser.add_argument("--variants", type=int, default=1, help="Variants per asset family for curation")
    parser.add_argument("--limit", type=int, help="Limit number of jobs")
    parser.add_argument("--names", nargs="+", help="Restrict to specific asset ids or names")
    parser.add_argument("--names-file", help="Text file with one asset id/name per line")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--steps", type=int, default=30)
    parser.add_argument("--guidance", type=float, default=6.0)
    parser.add_argument("--width", type=int, default=RAW_SIZE[0])
    parser.add_argument("--height", type=int, default=RAW_SIZE[1])
    parser.add_argument("--gc-every", type=int, default=1, help="Run gc and CUDA cache cleanup every N jobs")
    parser.add_argument("--pause-ms", type=int, default=250, help="Pause between jobs to reduce desktop stutter")
    parser.add_argument("--lora-path", help="Override: single LoRA weights file (bypass the default painted CRPG stack)")
    parser.add_argument("--lora-scale", type=float, default=0.8, help="LoRA strength when --lora-path override is used")
    parser.add_argument("--no-lora-stack", action="store_true", help="Disable the default painted CRPG LoRA stack (use base SDXL only)")
    parser.add_argument("--no-lcm", action="store_true", help="Disable LCM scheduler (fall back to 30-step sampling)")
    parser.add_argument("--postprocess", action="store_true")
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()

    if args.list:
        list_assets()
        return
    if args.postprocess:
        reprocess_all()
        return

    if args.plan:
        jobs = build_jobs(args.plan, limit=args.limit, views=args.views, variants=max(1, args.variants))
        wanted = load_name_filters(args.names, args.names_file)
        jobs = filter_jobs_by_name(jobs, wanted)
        path = write_plan(args.plan, jobs)
        print(f"Wrote {len(jobs)} jobs -> {path}")
        return

    if args.generate:
        jobs = build_jobs(args.generate, limit=args.limit, views=args.views, variants=max(1, args.variants))
        wanted = load_name_filters(args.names, args.names_file)
        jobs = filter_jobs_by_name(jobs, wanted)
        # Use default painted CRPG stack unless user explicitly opts out or supplies a single override.
        lora_stack: list[tuple[str, str, float]] | None = None if (args.no_lora_stack or args.lora_path) else DEFAULT_LORA_STACK
        use_lcm: bool = not args.no_lcm
        generate_jobs(
            jobs=jobs,
            backend=args.backend,
            force=args.force,
            model_id=args.model_id,
            style_ref_path=args.style_ref,
            steps=args.steps,
            guidance_scale=args.guidance,
            width=args.width,
            height=args.height,
            gc_every=max(1, args.gc_every),
            pause_ms=max(0, args.pause_ms),
            lora_stack=lora_stack,
            single_lora_path=args.lora_path,
            single_lora_scale=args.lora_scale,
            use_lcm=use_lcm,
        )
        return

    parser.print_help()


if __name__ == "__main__":
    main()
