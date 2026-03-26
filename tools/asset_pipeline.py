#!/usr/bin/env python3
"""
Ember RPG — AI Asset Pipeline
Generates billboard-style sprites using HuggingFace Flux Schnell.
Post-processes: background removal, resize, pixel-art downscale.

Usage:
    python tools/asset_pipeline.py --generate sprites
    python tools/asset_pipeline.py --generate tiles
    python tools/asset_pipeline.py --generate all
    python tools/asset_pipeline.py --list          # show what needs generating
    python tools/asset_pipeline.py --postprocess   # re-process raw/ → final
"""

import argparse
import json
import os
import sys
import time
from io import BytesIO
from pathlib import Path

import requests
from PIL import Image, ImageFilter, ImageEnhance

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
HF_API_URL = "https://router.huggingface.co/hf-inference/models/black-forest-labs/FLUX.1-schnell"


def get_hf_token() -> str:
    return os.environ.get("HF_TOKEN", "") or os.environ.get("HUGGINGFACE_API_KEY", "")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "tools" / "asset_raw"          # AI output (512x512)
SPRITE_DIR = PROJECT_ROOT / "godot-client" / "assets" / "sprites"
TILE_DIR = PROJECT_ROOT / "godot-client" / "assets" / "tiles"
CACHE_FILE = PROJECT_ROOT / "tools" / "asset_cache.json"

SPRITE_SIZE = (32, 32)     # final game size
RAW_SIZE = (512, 512)      # AI generation size
UPSCALE_SIZE = (64, 64)    # intermediate for better downscale

# ---------------------------------------------------------------------------
# Sprite Definitions — billboard ¾ view, consistent style
# ---------------------------------------------------------------------------
STYLE_PREFIX = (
    "pixel art RPG character sprite, 3/4 top-down view, "
    "single character centered, dark fantasy style, "
    "transparent background, no shadow, clean edges, "
    "16-bit SNES era style, "
)

SPRITE_DEFS = {
    # Player classes
    "warrior": "armored human warrior with sword and shield, steel plate armor, stoic expression",
    "mage": "robed human mage with glowing staff, blue mystical robes, wise expression",
    "rogue": "hooded human rogue with daggers, dark leather armor, cunning expression",
    "priest": "holy human priest with golden staff, white and gold robes, serene expression",

    # NPCs
    "merchant": "portly merchant with bag of gold, colorful clothing, friendly smile",
    "quest_giver": "old wise man with scroll, long grey beard, mysterious aura",
    "innkeeper": "stout innkeeper with mug of ale, apron, welcoming expression",
    "guard": "town guard with spear and helmet, chain mail armor, alert stance",
    "blacksmith": "muscular blacksmith with hammer, leather apron, soot-covered",
    "healer": "gentle healer with herbs and potion, green robes, kind expression",
    "beggar": "ragged beggar with torn clothes, thin and hunched, pleading expression",
    "spy": "shadowy figure with hood and cloak, mysterious, half-hidden face",
    "sage": "ancient sage with book and crystal ball, long white beard, starry robes",

    # Enemies
    "goblin": "small green goblin with crude weapon, yellow eyes, menacing grin",
    "skeleton": "undead skeleton warrior with rusty sword, glowing eye sockets",
    "wolf": "fierce grey wolf, bared teeth, wild fur, predatory stance",
    "orc": "large green orc warrior with battle axe, tribal war paint",
    "spider": "giant dark spider, multiple red eyes, hairy legs, venomous fangs",
    "bandit": "masked bandit with crossbow, ragged dark clothing",
    "dragon": "small dragon with wings spread, scales gleaming, fire breath",
    "zombie": "shambling undead zombie, torn clothes, decaying flesh, vacant eyes",

    # New entities (not yet in game)
    "bard": "cheerful bard with lute, colorful feathered hat, performing stance",
    "witch": "old witch with pointed hat and black cat, green potion bubbling",
    "knight": "noble knight in shining full plate armor, blue cape, standing with sword raised, no horse",
    "thief": "nimble thief with lockpicks, dark mask, crouching position",
    "necromancer": "dark necromancer with skull staff, purple dark robes, ghostly aura",
    "troll": "large bridge troll with club, mossy skin, small angry eyes",
    "rat": "giant sewer rat, matted fur, red beady eyes, long tail",
    "ghost": "classic translucent white ghost floating, wispy ethereal body, glowing hollow eyes, spooky aura",
    "mimic": "wooden treasure chest monster with sharp teeth and long tongue, open lid reveals fangs, monster disguised as chest",
    "fairy": "tiny glowing fairy with butterfly wings, magical sparkles",
}

TILE_STYLE_PREFIX = (
    "pixel art RPG tile texture, seamless tileable, top-down view, "
    "16-bit SNES era style, 32x32 tile, "
)

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
    # New tiles
    "lava": "molten lava flow, orange and red, glowing cracks",
    "ice": "frozen ice floor, blue-white, frost crystals",
    "swamp": "murky swamp water, green, lily pads and reeds",
    "marble": "polished marble floor, white with grey veins, elegant",
    "brick": "red brick wall, mortar lines, slightly weathered",
    "cave": "natural cave floor, rough brown stone, stalactite shadows",
    "bridge": "wooden bridge planks, rope sides, creaking",
}


# ---------------------------------------------------------------------------
# HuggingFace API
# ---------------------------------------------------------------------------
def generate_image(prompt: str, retries: int = 3) -> Image.Image | None:
    """Call HF Flux Schnell to generate an image."""
    token = get_hf_token()
    if not token:
        print("[ERROR] HF_TOKEN/HUGGINGFACE_API_KEY not set. Export one of them or pass via env.")
        return None

    headers = {"Authorization": f"Bearer {token}"}
    payload = {"inputs": prompt}

    for attempt in range(retries):
        try:
            resp = requests.post(HF_API_URL, headers=headers, json=payload, timeout=60)
            if resp.status_code == 200:
                img = Image.open(BytesIO(resp.content))
                return img
            elif resp.status_code == 503:
                # Model loading
                wait = resp.json().get("estimated_time", 30)
                print(f"  Model loading, waiting {wait:.0f}s...")
                time.sleep(min(wait, 60))
            elif resp.status_code == 429:
                print(f"  Rate limited, waiting 10s...")
                time.sleep(10)
            else:
                print(f"  API error {resp.status_code}: {resp.text[:200]}")
                time.sleep(5)
        except Exception as e:
            print(f"  Request failed: {e}")
            time.sleep(5)

    return None


# ---------------------------------------------------------------------------
# Post-processing
# ---------------------------------------------------------------------------
def remove_background(img: Image.Image) -> Image.Image:
    """Remove background using rembg."""
    try:
        from rembg import remove
        # Convert to bytes, process, convert back
        buf = BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        result = remove(buf.read())
        return Image.open(BytesIO(result)).convert("RGBA")
    except ImportError:
        print("  [WARN] rembg not installed, skipping bg removal")
        return img.convert("RGBA")


def postprocess_sprite(raw_img: Image.Image) -> Image.Image:
    """Full sprite postprocess pipeline: bg remove → enhance → resize."""
    # 1. Remove background
    img = remove_background(raw_img)

    # 2. Enhance contrast slightly for pixel art look
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(1.2)

    # 3. Enhance color saturation
    enhancer = ImageEnhance.Color(img)
    img = enhancer.enhance(1.3)

    # 4. Resize to intermediate (64x64) with LANCZOS for quality
    img = img.resize(UPSCALE_SIZE, Image.LANCZOS)

    # 5. Final resize to 32x32 with NEAREST for crisp pixel art
    img = img.resize(SPRITE_SIZE, Image.NEAREST)

    return img


def postprocess_tile(raw_img: Image.Image) -> Image.Image:
    """Tile postprocess: no bg removal, just enhance + resize."""
    img = raw_img.convert("RGBA")

    # Enhance for pixel art look
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(1.1)

    enhancer = ImageEnhance.Color(img)
    img = enhancer.enhance(1.2)

    # Resize to 32x32 — LANCZOS then NEAREST for crisp tiles
    img = img.resize(UPSCALE_SIZE, Image.LANCZOS)
    img = img.resize(SPRITE_SIZE, Image.NEAREST)

    return img


# ---------------------------------------------------------------------------
# Cache management
# ---------------------------------------------------------------------------
def load_cache() -> dict:
    if CACHE_FILE.exists():
        return json.loads(CACHE_FILE.read_text())
    return {}


def save_cache(cache: dict):
    CACHE_FILE.write_text(json.dumps(cache, indent=2))


# ---------------------------------------------------------------------------
# Generation commands
# ---------------------------------------------------------------------------
def generate_sprites(names: list[str] | None = None, force: bool = False):
    """Generate sprite images for specified entities (or all)."""
    cache = load_cache()
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    SPRITE_DIR.mkdir(parents=True, exist_ok=True)

    targets = names or list(SPRITE_DEFS.keys())
    total = len(targets)

    for i, name in enumerate(targets, 1):
        if name not in SPRITE_DEFS:
            print(f"[SKIP] Unknown sprite: {name}")
            continue

        raw_path = RAW_DIR / f"sprite_{name}_raw.png"
        final_path = SPRITE_DIR / f"{name}.png"

        # Skip if cached and not forced
        if not force and cache.get(f"sprite_{name}") and final_path.exists():
            print(f"[{i}/{total}] {name} — cached, skip")
            continue

        print(f"[{i}/{total}] Generating {name}...")
        prompt = STYLE_PREFIX + SPRITE_DEFS[name]

        raw_img = generate_image(prompt)
        if raw_img is None:
            print(f"  [FAIL] Could not generate {name}")
            continue

        # Save raw
        raw_img.save(str(raw_path))
        print(f"  Raw saved: {raw_path.name}")

        # Postprocess
        final_img = postprocess_sprite(raw_img)
        final_img.save(str(final_path))
        print(f"  Final saved: {final_path.name} ({final_img.size})")

        # Update cache
        cache[f"sprite_{name}"] = {
            "generated": time.strftime("%Y-%m-%d %H:%M"),
            "prompt": prompt[:100],
            "raw": str(raw_path),
            "final": str(final_path),
        }
        save_cache(cache)

        # Rate limiting — be nice to free API
        time.sleep(2)

    print(f"\nDone! {total} sprites processed.")


def generate_tiles(names: list[str] | None = None, force: bool = False):
    """Generate tile textures."""
    cache = load_cache()
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    TILE_DIR.mkdir(parents=True, exist_ok=True)

    targets = names or list(TILE_DEFS.keys())
    total = len(targets)

    for i, name in enumerate(targets, 1):
        if name not in TILE_DEFS:
            print(f"[SKIP] Unknown tile: {name}")
            continue

        raw_path = RAW_DIR / f"tile_{name}_raw.png"
        final_path = TILE_DIR / f"{name}.png"

        if not force and cache.get(f"tile_{name}") and final_path.exists():
            print(f"[{i}/{total}] {name} — cached, skip")
            continue

        print(f"[{i}/{total}] Generating tile {name}...")
        prompt = TILE_STYLE_PREFIX + TILE_DEFS[name]

        raw_img = generate_image(prompt)
        if raw_img is None:
            print(f"  [FAIL] Could not generate {name}")
            continue

        raw_img.save(str(raw_path))
        print(f"  Raw saved: {raw_path.name}")

        final_img = postprocess_tile(raw_img)
        final_img.save(str(final_path))
        print(f"  Final saved: {final_path.name} ({final_img.size})")

        cache[f"tile_{name}"] = {
            "generated": time.strftime("%Y-%m-%d %H:%M"),
            "prompt": prompt[:100],
        }
        save_cache(cache)
        time.sleep(2)

    print(f"\nDone! {total} tiles processed.")


def reprocess_all():
    """Re-postprocess all raw images without regenerating."""
    print("Re-processing raw sprites...")
    for raw_file in sorted(RAW_DIR.glob("sprite_*_raw.png")):
        name = raw_file.stem.replace("sprite_", "").replace("_raw", "")
        final_path = SPRITE_DIR / f"{name}.png"
        raw_img = Image.open(raw_file)
        final_img = postprocess_sprite(raw_img)
        final_img.save(str(final_path))
        print(f"  {name}: {final_img.size}")

    print("Re-processing raw tiles...")
    for raw_file in sorted(RAW_DIR.glob("tile_*_raw.png")):
        name = raw_file.stem.replace("tile_", "").replace("_raw", "")
        final_path = TILE_DIR / f"{name}.png"
        raw_img = Image.open(raw_file)
        final_img = postprocess_tile(raw_img)
        final_img.save(str(final_path))
        print(f"  {name}: {final_img.size}")


def list_assets():
    """Show what exists and what's missing."""
    print("=== SPRITES ===")
    for name in sorted(SPRITE_DEFS.keys()):
        exists = (SPRITE_DIR / f"{name}.png").exists()
        raw_exists = (RAW_DIR / f"sprite_{name}_raw.png").exists()
        status = "OK" if exists else ("RAW ONLY" if raw_exists else "MISSING")
        marker = "  " if exists else ">>"
        print(f"  {marker} {name:20s} [{status}]")

    print("\n=== TILES ===")
    for name in sorted(TILE_DEFS.keys()):
        exists = (TILE_DIR / f"{name}.png").exists()
        raw_exists = (RAW_DIR / f"tile_{name}_raw.png").exists()
        status = "OK" if exists else ("RAW ONLY" if raw_exists else "MISSING")
        marker = "  " if exists else ">>"
        print(f"  {marker} {name:20s} [{status}]")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Ember RPG AI Asset Pipeline")
    parser.add_argument("--generate", choices=["sprites", "tiles", "all"],
                        help="Generate assets")
    parser.add_argument("--names", nargs="+", help="Specific asset names to generate")
    parser.add_argument("--force", action="store_true", help="Regenerate even if cached")
    parser.add_argument("--postprocess", action="store_true",
                        help="Re-postprocess raw images")
    parser.add_argument("--list", action="store_true", help="List asset status")

    args = parser.parse_args()

    if args.list:
        list_assets()
    elif args.postprocess:
        reprocess_all()
    elif args.generate:
        if args.generate in ("sprites", "all"):
            generate_sprites(args.names, args.force)
        if args.generate in ("tiles", "all"):
            generate_tiles(args.names, args.force)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
