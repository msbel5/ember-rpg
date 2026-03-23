# PRD: Layered AI Asset Generation Pipeline
**Project:** Ember RPG
**Phase:** 5b
**Author:** Mami + Claude Code
**Date:** 2026-03-24
**Status:** Draft

---

## 1. Purpose

Generate unique, AI-created visual assets for the first-person POV renderer using a **layered compositing system with aggressive caching**. Every scene looks hand-illustrated (Hitchhiker's Guide / comic book style) but is composed from reusable layers. Assets are generated once and cached — same tile + same direction = same image. This solves the token/cost problem while producing infinite visual variety.

**Inspiration:** BBC Hitchhiker's Guide to the Galaxy 30th Anniversary Edition — text adventure with illustrated side panel. Our difference: illustrations are AI-generated, so every playthrough has unique art.

**Core Principle:** Generate once, composite many. Like Mario's memory optimization — smart reuse of tile-based assets across scenes, campaigns, and playthroughs.

---

## 2. Scope

**In scope:**
- AI image generation pipeline (HuggingFace Inference API / DALL-E / SDXL / Flux)
- Layered asset compositing system (background → buildings → entities → items)
- Asset caching with content-addressable storage
- Color palette swapping for NPC/item variations
- POV scene compositor (assembles layers into final frame)
- Asset manifest per campaign/location

**Out of scope:**
- Animation (Phase 7+)
- 3D rendering
- Real-time generation during gameplay (pre-generate or async)
- Audio/music generation

---

## 3. Functional Requirements (FR)

### Layer Architecture

**FR-01:** The POV scene must be composed of exactly 5 render layers, back to front:
```
Layer 0: Far Background    — sky, mountains, distant landscape (per map + per direction)
Layer 1: Mid Background    — buildings, streets, walls, ceiling (per area + per direction)
Layer 2: Near Environment  — furniture, objects, interactive items (per item type)
Layer 3: Entities          — NPCs, monsters, quest givers (per entity template)
Layer 4: Foreground/FX     — weather effects, fog, lighting overlays
```

**FR-02:** Each layer must be a PNG with transparency (alpha channel). The compositor overlays layers in order, producing the final POV frame.

**FR-03:** Layer 0 (Far Background) must be generated once per map per cardinal direction (4 images per map). Example: Harbor Town facing North = mountains + lighthouse. Harbor Town facing South = open sea + distant ships. Reused for ALL tiles looking in that direction within the map.

**FR-04:** Layer 1 (Mid Background) must be generated per area zone + direction. A zone is a cluster of tiles (e.g., "market_square", "docks", "tavern_interior"). Typically 4-8 zones per map × 4 directions = 16-32 images per map.

**FR-05:** Layer 2 (Near Environment) must be generated per item/object type. A "barrel" asset works everywhere barrels appear. A "notice_board" is one image. These are position-independent — the compositor places them based on tile position relative to player.

**FR-06:** Layer 3 (Entities) must be generated per entity template. "guard" = one image. "merchant" = one image. Variations (different guards) use color palette swapping (FR-10). Each entity has 4 facing variants (facing player, away, left profile, right profile).

**FR-07:** The compositor must scale and position Layer 2-3 assets based on distance from player (perspective scaling: closer = larger, farther = smaller, using the same depth formula as the current POV renderer).

### Asset Generation

**FR-08:** Assets must be generated using HuggingFace Inference API (SDXL/Flux) with structured prompts:
```
Style: "fantasy illustration, comic book style, detailed ink lines,
        watercolor palette, {location_atmosphere}"
Subject: "{entity_description}, {pose}, {facing_direction}"
Negative: "photorealistic, 3D render, blurry, low quality"
```

**FR-09:** Each generated asset must be stored with a content-addressable key:
```
asset_key = hash(layer_type + subject + style + direction + palette)
path: assets/{campaign_id}/{layer}/{asset_key}.png
```
If the asset already exists at this key, skip generation entirely.

**FR-10:** Color palette swapping must support creating variations without regeneration:
- Base guard (blue armor) → Red guard (HSV shift) → Gold guard (HSV shift)
- Base merchant (brown robes) → Rich merchant (purple shift)
- Implementation: PIL/Pillow HSV channel manipulation on the base asset

**FR-11:** Asset generation must be async and non-blocking. The POV renderer shows the current procedural view (colored shapes) while AI assets load. When an asset is ready, it replaces the procedural placeholder with a smooth crossfade.

### Caching & Reuse

**FR-12:** All generated assets must persist to disk in the campaign asset folder. Assets survive game restarts, save/load cycles, and session changes.

**FR-13:** Asset manifest file (`assets/{campaign_id}/manifest.json`) tracks all generated assets:
```json
{
  "campaign_id": "harbor_town_quest",
  "generated_at": "2026-03-24T01:00:00Z",
  "layers": {
    "far_bg": {
      "harbor_town_north": {"path": "far_bg/abc123.png", "prompt": "...", "model": "sdxl"},
      "harbor_town_south": {"path": "far_bg/def456.png", "prompt": "...", "model": "sdxl"}
    },
    "mid_bg": { ... },
    "items": { ... },
    "entities": { ... }
  },
  "palette_variants": {
    "guard_red": {"base": "guard", "hue_shift": 120}
  }
}
```

**FR-14:** Cross-campaign asset reuse: Generic assets (barrel, chest, torch, generic_guard) can be shared across campaigns via a `shared_assets/` folder. Campaign-specific assets (named NPCs, unique locations) stay in campaign folder.

**FR-15:** Asset budget per location: Maximum 20 unique generations per new location entered. This limits API costs. Breakdown:
- 4× far background (one per direction)
- 4-8× mid background (zones × key directions)
- 4-6× unique items/objects
- 2-4× unique entities
- Rest: reuse shared assets + palette swaps

---

## 4. Compositing Algorithm

```
func compose_pov_frame(player_pos, facing, fov_data, asset_cache):
    frame = new_canvas(viewport_width, viewport_height)

    # Layer 0: Far background (full frame)
    bg_key = f"{map_id}_{facing}"
    frame.draw(asset_cache.get("far_bg", bg_key), fill=True)

    # Layer 1: Mid background (area zone)
    zone = get_zone(player_pos)
    mid_key = f"{zone}_{facing}"
    frame.draw(asset_cache.get("mid_bg", mid_key), fill=True)

    # Layer 2-3: Items and entities (sorted by distance, far first)
    visible = get_fov_entities(player_pos, facing, fov_data)
    visible.sort(by=distance, descending=True)  # far objects first (painter's algorithm)

    for entity in visible:
        asset = asset_cache.get(entity.layer, entity.template)
        if asset == null:
            asset = procedural_silhouette(entity)  # fallback

        # Perspective transform
        scale = 1.0 - (entity.distance / max_depth) * 0.7
        x_pos = viewport_center_x + entity.lateral_offset * scale
        y_pos = horizon_y + entity.distance_below_horizon * scale

        frame.draw(asset, x=x_pos, y=y_pos, scale=scale, alpha=entity.reveal_alpha)

    # Layer 4: Weather/FX overlay
    if weather != "clear":
        frame.draw(asset_cache.get("fx", weather), blend=ADDITIVE)

    return frame
```

---

## 5. Generation Pipeline

### 5.1 Pre-generation (on scene enter)

When player enters a new location:
1. Check manifest — which assets already exist?
2. Queue missing assets for generation (async)
3. Immediately show procedural POV (current system)
4. As assets arrive, crossfade them in

### 5.2 On-demand generation (examine/storyboard)

When player examines an item or triggers a storyboard moment:
1. Check cache for item closeup asset
2. If missing, generate with high-priority queue
3. Show "The details become clearer..." loading narrative
4. Display generated closeup

### 5.3 Background worker

A background process/thread that:
1. Monitors the generation queue
2. Calls HuggingFace API (rate limited: 1 req/3 seconds)
3. Post-processes (resize, alpha extraction, palette adjustment)
4. Saves to disk + updates manifest
5. Emits signal to Godot for crossfade

---

## 6. Cost Analysis

### HuggingFace (Free tier with API key)
- SDXL: ~10 seconds/image, free with HF Pro ($9/mo) or pay-per-use
- Flux Schnell: ~3 seconds/image, free tier available
- Budget: ~20 images per new location = ~60 seconds generation time

### Per-campaign estimate
- 5 locations × 20 assets = 100 images
- At 512×512 resolution: ~50MB disk space
- Generation time: ~15 minutes total (can be spread across gameplay)

### Token savings vs full LLM image description
- Without asset cache: Every action → LLM describes scene → expensive
- With asset cache: Generate once → reuse 100+ times → near-zero marginal cost

---

## 7. Data Structures

```python
@dataclass
class AssetRequest:
    layer: str           # "far_bg", "mid_bg", "item", "entity", "fx"
    key: str             # content-addressable hash
    prompt: str          # generation prompt
    style: str           # "fantasy_comic", "dark_dungeon", etc.
    priority: int        # 0=highest (storyboard), 1=entity, 2=background
    palette: str = ""    # optional palette override
    size: tuple = (512, 512)

@dataclass
class AssetEntry:
    key: str
    path: str            # relative path to PNG file
    layer: str
    prompt: str
    model: str           # "sdxl", "flux-schnell", "dalle3"
    generated_at: str
    dimensions: tuple
    palette_base: str = ""  # if this is a palette variant, reference base key

@dataclass
class AssetManifest:
    campaign_id: str
    version: int
    entries: Dict[str, AssetEntry]  # key → entry
    palette_variants: Dict[str, dict]  # variant_name → {base, hue_shift, ...}
```

---

## 8. Public API

```python
# Asset Manager (Godot-side or shared)
class AssetManager:
    def get_asset(layer: str, key: str) -> Image or null
    def request_generation(req: AssetRequest) -> void  # async
    def get_manifest() -> AssetManifest
    def create_palette_variant(base_key: str, hue_shift: int) -> str  # returns new key

# POV Compositor (Godot-side)
class POVCompositor:
    func compose_frame(player_pos, facing, entities, asset_mgr) -> Image
    func crossfade_asset(old_frame, new_asset, duration: float) -> void

# Generation Worker (Backend or local)
class GenerationWorker:
    func generate(req: AssetRequest) -> AssetEntry
    func process_queue() -> void  # background loop
```

---

## 9. Acceptance Criteria

AC-01 [FR-01]: Given a POV scene, when rendered, then exactly 5 layers are composited in order (far_bg → mid_bg → items → entities → fx).

AC-02 [FR-03]: Given a map "harbor_town", when all 4 far backgrounds are generated, then subsequent views in any direction reuse cached images (0 new API calls).

AC-03 [FR-09]: Given the same entity template + style + direction, when `get_asset()` is called twice, then the same file path is returned (no regeneration).

AC-04 [FR-10]: Given a "guard" base asset, when `create_palette_variant("guard", hue_shift=120)` is called, then a red-tinted variant PNG is created without API call.

AC-05 [FR-11]: Given a new location with no cached assets, when the player enters, then the procedural POV is shown immediately and AI assets crossfade in as they generate.

AC-06 [FR-14]: Given a "barrel" asset in `shared_assets/`, when a new campaign has barrels, then the shared asset is used (0 new API calls for barrels).

AC-07 [FR-15]: Given a new location, when assets are generated, then no more than 20 API calls are made.

---

## 10. Performance Requirements

- Compositing 5 layers at 720p: < 16ms (60fps capable)
- Asset lookup from cache: < 1ms
- Palette swap generation: < 100ms (CPU-only, no API)
- Background generation queue: non-blocking, max 1 concurrent API call
- Disk cache: < 200MB per campaign

---

## 11. Integration Points

- **POV System (Phase 8):** Compositor replaces procedural renderer when assets available
- **DM Agent:** Scene descriptions inform generation prompts
- **Map Generator:** Zone definitions drive mid_bg asset keys
- **Campaign Generator:** Campaign ID scopes asset storage
- **Save/Load:** Asset manifest persists with campaign data

---

## 12. Migration Path

### Phase 5b-1: Foundation (Week 1)
- AssetManager + manifest system
- Content-addressable cache
- Procedural fallback (current system stays as default)

### Phase 5b-2: Generation Pipeline (Week 2)
- HuggingFace API integration
- Background worker queue
- Far background + mid background generation

### Phase 5b-3: Entity Assets (Week 3)
- Entity/item generation with structured prompts
- Palette swap system
- Crossfade integration in Godot

### Phase 5b-4: Polish (Week 4)
- Storyboard moment closeups
- Shared asset library
- Cost monitoring dashboard

---

*This PRD must be reviewed by Mami before implementation.*
*Alcyone implements backend generation worker; Mami+Claude Code implement Godot compositor.*
