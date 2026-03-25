# PRD: First-Person POV System + Storyboard Moments
**Project:** Ember RPG  
**Phase:** 8  
**Author:** Alcyone (CAPTAIN)  
**Date:** 2026-03-23  
**Status:** Draft

---

## Vision

> "DM sana anlatır, sen aklında hayal edersin — biz onu gözünün önünde canlandırırız."

Ember RPG'nin görsel dili Monkey Island'ın ruhunu taşır ama First-Person POV ile. Oyuncu her zaman ileri bakar. Dünya onun etrafında inşa edilir — tile by tile, entity by entity, DM anlatırken sahne canlanır.

**Mühendislik çözümü:** Her varlık bir kere render edilir, pozisyon + yön kombinasyonuna göre yerleştirilir. Oyuncu aşağı bakarken sadece "aşağı bakış vücudu" katmanı değişir. Canavarlar bir kere generate edilir, invisible'dan fade-in ile girer sahneye — tıpkı DM'in bahsettiği an gibi.

---

## Part 1: Player Position & Direction Tracking

### 1.1 Data Model

```python
class PlayerPosition:
    x: int          # grid X
    y: int          # grid Y
    facing: str     # "north" | "south" | "east" | "west"
    floor: int      # dungeon floor / area level (0 = ground)
    area_id: str    # "harbor_town_market", "thornwood_path_1", etc.
```

GameSession'a eklenir. Persist edilir (save/load ile).

### 1.2 Movement Rules

`"move forward"` → facing yönünde X/Y değişir  
`"move north/south/east/west"` → facing güncellenir + X/Y değişir  
`"turn left/right"` → sadece facing değişir, pozisyon değişmez  
`"look up"` → storyboard moment (aşağıda)  
`"go to tavern"` → named destination, pozisyon hesaplanır  

Grid boyutu: 1 tile = 1 birim. Default harita: 32x32 tile.

### 1.3 API Changes

`POST /game/session/{id}/action` response'una eklenir:
```json
{
  "narrative": "...",
  "player_position": {
    "x": 5, "y": 8,
    "facing": "north",
    "area_id": "harbor_town_docks"
  }
}
```

---

## Part 2: Field of View (FOV) Calculation

### 2.1 FOV Parametreleri

```
Depth:      3-5 tile (configurable per scene: dungeon=3, outdoors=5)
Width:      90° viewing angle (±45° from facing direction)
Algorithm:  Shadowcasting (roguelike standard, O(n²) for small grids)
```

### 2.2 Facing → Tile Grid Mapping

Oyuncu `facing: north` ise görüş alanı:

```
    [NW-2] [N-2] [NE-2]      ← depth 2
       [NW-1] [N-1] [NE-1]   ← depth 1
            [Player]          ← 0,0
```

Her tile için:
- `tile_type`: floor, wall, water, door, stairs
- `entities`: NPC list, item list, enemy list
- `visibility`: `visible | foggy | hidden`
- `revealed_by_dm`: DM narrative'de bahsedildikten sonra `true`

### 2.3 FOV Endpoint

```
GET /game/session/{id}/pov
```

Response:
```json
{
  "player_position": {"x": 5, "y": 8, "facing": "north", "area_id": "harbor_town_docks"},
  "fov_tiles": [
    {
      "x": 5, "y": 7, "relative": "forward_1",
      "tile_type": "floor",
      "visibility": "visible",
      "entities": [
        {"type": "npc", "id": "innkeeper_bram", "revealed": true, "context_actions": ["talk", "trade"]}
      ]
    },
    {
      "x": 5, "y": 6, "relative": "forward_2",
      "tile_type": "door",
      "visibility": "foggy",
      "entities": []
    }
  ],
  "ambient": {
    "light_level": "dim",
    "sound_hints": ["distant_voices", "fire_crackling"],
    "weather": "fog"
  }
}
```

### 2.4 `revealed_by_dm` Flag

DM bir entity'den bahsettiğinde (`[REVEAL:entity_id]` marker ile) o entity `revealed: true` olur. Godot bu sinyali alınca entity'yi invisible'dan fade-in yapar.

DM bahsetmeden önce entity şeffaf / yoktur. Bu Monkey Island ruhunu taşır: "Bir köşede garip bir adam oturuyor..." → adam o anda belirir.

---

## Part 3: Storyboard Moments

Bazı aksiyonlar kamera/POV geçişi tetikler. Bunlar sinematik beat'ler — DM anlatısını görselleştirir.

### 3.1 Storyboard Action Types

| Oyuncu Yazısı | Storyboard Tipi | Görsel Değişim |
|---|---|---|
| `"look up"` | sky_reveal | Gökyüzü/tavan görünümü, yıldızlar/duvarlar |
| `"look down"` | floor_view | Zemin tile'ları, gölgeler, ayak izleri |
| `"examine sword"` | item_closeup | Kılıca yakın çekim, rune detayları |
| `"pat yourself down"` | self_inventory | Kendi vücuduna bakış, cepler |
| `"peek around corner"` | corner_peek | Açı değişimi, yarım görüş |
| `"look in mirror"` | reflection | Karakter yüzü/zırhı görünür |
| `"read scroll"` | document_view | Parşömen yakın çekim, metin |
| `"look through keyhole"` | keyhole_view | Dairesel dar görüş açısı |

### 3.2 Storyboard API Response

```json
{
  "narrative": "You tilt your sword and see faint runes etched into the blade...",
  "storyboard_moment": {
    "type": "item_closeup",
    "target_entity": "iron_shortsword",
    "duration_ms": 3000,
    "return_to": "default_forward_pov",
    "render_hint": {
      "zoom_level": "closeup",
      "angle": "oblique_45",
      "layer": "item_detail"
    }
  }
}
```

`duration_ms` sonrası Godot otomatik default POV'a döner — ya da oyuncu herhangi bir aksiyon yaparsa hemen döner.

### 3.3 Storyboard Detection

`action_parser.py`'de yeni intent: `ActionIntent.STORYBOARD`

Patterns:
- `"look up/down/left/right"` → direction-based storyboard
- `"examine {wearable}"` → self_inventory
- `"examine {item}"` → item_closeup
- `"peek/glance"` → corner_peek
- `"read {document}"` → document_view

`_handle_storyboard()` in game_engine.py:
- LLM'e storyboard tipi + hedef entity context'i ile narrative üret
- Response'a `storyboard_moment` field'ı ekle

---

## Part 4: Render Architecture (Godot Tarafı — Notlar)

Bu kısım backend spesifikasyonu değil, Godot tasarım notları. Backend bu mimariyi bilmeli çünkü doğru render_hint'leri döndürmesi gerekiyor.

### 4.1 Katmanlar (Layers)

```
Layer 0: Background (sky, walls, floor)
Layer 1: World tiles (ground, objects)
Layer 2: Entities (NPCs, enemies, items) ← fade-in buraya
Layer 3: Player hands/weapon (always visible)
Layer 4: Player body (looking down / self-examine)
Layer 5: UI overlay (HP, hotkeys, map)
```

### 4.2 Entity Render Principle

> "Her varlık bir kere render edilir."

**UPDATED (2026-03-24):** Asset rendering upgraded from pixel art sprites to **AI-generated layered compositing**. See `PRD_asset_pipeline.md` for full details.

- **Phase 5b Asset Pipeline** replaces sprite atlas with AI-generated PNGs
- 5 compositing layers: Far BG → Mid BG → Items → Entities → FX
- Assets generated once per type, cached with content-addressable storage
- Color palette swapping for variations (no API call needed)
- Procedural silhouettes remain as fallback while AI assets load
- `invisible → fade-in` geçişi sadece alpha değeridir (same as before)

### 4.3 POV Body Rendering

Oyuncu her zaman ileri bakar. Body render:

```
Forward (default): Hands + weapon in frame
Look down:        Feet + ground tiles visible, hands lower
Look up:          Ceiling/sky tiles, head tilt implied
Self-examine:     Full body visible (like looking in mirror)
```

Body katmanı background'ın önünde, entity'lerin arkasında. Yakın entity'ler (depth 1) vücudun önünde render edilir — parallax efekti.

---

## Part 5: Implementation Plan

### Phase 8a: Player Position Tracking (Backend)
- `PlayerPosition` dataclass → `GameSession`
- Movement handlers güncelleme (`_handle_move`, `_handle_look`)
- `action` response'a `player_position` field ekleme
- Save/load'a position persist etme
- Tests: 10+ unit test

### Phase 8b: FOV Calculation (Backend)
- `FOVCalculator` engine (`engine/map/fov.py`) — shadowcasting
- `GET /game/session/{id}/pov` endpoint
- `revealed_by_dm` flag — DM marker'lardan otomatik güncelleme
- Tests: 15+ unit test

### Phase 8c: Storyboard Moments (Backend)
- `ActionIntent.STORYBOARD` parser
- `_handle_storyboard()` with LLM narrative + render hint
- `storyboard_moment` field in ActionResponse
- Tests: 10+ unit test

### Phase 8d: Godot POV Integration
- Poll `/game/session/{id}/pov` on every action
- Render tile grid based on FOV response
- Handle fade-in on `revealed: true` entity transitions
- Handle `storyboard_moment` with camera transitions

---

## Open Questions

1. **Grid size**: 32x32 yeterli mi? Büyük outdoor area'lar için dinamik boyut?
2. **FOV algorithm**: Shadowcasting mi, raycasting mi? Pi 5'te perf?
3. **Storyboard duration**: 3000ms sabit mi, narrative uzunluğuna göre mi?
4. **POV polling**: Her action'da mı, sadece move/look'ta mı?
5. **Area transitions**: "go to tavern" aynı haritada mı yoksa yeni area_id mi yükler?

---

## Acceptance Criteria

- [ ] `move forward` → `player_position.facing` + `x/y` değişiyor
- [ ] `GET /pov` → 3-5 tile derinlik, 90° açı, entity listesi
- [ ] `examine sword` → `storyboard_moment.type == "item_closeup"` response'da
- [ ] `revealed_by_dm: true` entity'ler DM [REVEAL:id] marker'ından geliyor
- [ ] Position save/load round-trip çalışıyor
- [ ] 25+ new tests, all passing

---

*Bu PRD Phase 8 implementation başlamadan önce Mami ile review edilmeli.*
*Godot render architecture notları informational — implementation Mami'nin sorumluluğu.*

---

## Standardized Sections

**Project:** Ember RPG
**Phase:** 8
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-03-23
**Status:** Draft

---

## Functional Requirements

**FR-01:** `PlayerPosition` must track x, y, facing direction (north/south/east/west), floor level, and area_id. It must be stored in `GameSession` and included in save/load.

**FR-02:** Movement commands (`"move forward"`, `"move north"`, `"turn left"`) must update `PlayerPosition` fields: facing changes for turns, x/y changes for movement.

**FR-03:** `POST /game/session/{id}/action` response must include a `player_position` field whenever the action causes a position change.

**FR-04:** `GET /game/session/{id}/pov` must return FOV tiles for 3-5 tile depth at 90° viewing angle, each tile including type, visibility, and entity list.

**FR-05:** Each entity in FOV tiles must have a `revealed` boolean. An entity's `revealed` flag must be set to `True` when the DM narrative includes a `[REVEAL:entity_id]` marker.

**FR-06:** Storyboard-triggering actions (`"look up"`, `"examine sword"`, `"peek around corner"`) must return an `ActionResult` containing a `storyboard_moment` field with type, target_entity, duration_ms, and render_hint.

**FR-07:** The FOV algorithm must guarantee that tiles behind walls are NOT included (shadowcasting/raycasting occlusion).

**FR-08:** `PlayerPosition` must survive save/load round-trip with identical values.

**FR-09:** Two calls to the FOV calculation with the same position and map must produce identical results (determinism).

**FR-10:** Unrevealed entities must NOT appear in the FOV response (client only sees revealed entities unless entity has `always_visible=True`).

---

## Data Structures

```python
@dataclass
class PlayerPosition:
    x: int
    y: int
    facing: str          # "north" | "south" | "east" | "west"
    floor: int = 0       # dungeon floor
    area_id: str = ""

@dataclass
class FOVTile:
    x: int
    y: int
    relative: str        # "forward_1", "left_1", etc.
    tile_type: str
    visibility: str      # "visible" | "foggy" | "hidden"
    entities: List[dict] # [{"type", "id", "revealed", "context_actions"}]

@dataclass
class StoryboardMoment:
    type: str            # "item_closeup", "sky_reveal", etc.
    target_entity: str
    duration_ms: int
    return_to: str
    render_hint: dict    # {"zoom_level", "angle", "layer"}
```

---

## Public API

```python
# Position update (called by action handlers)
def update_position(session: GameSession, command: str) -> PlayerPosition:
    """Parses movement/turn command, updates session.player_position, returns new position."""

# FOV endpoint
GET /game/session/{id}/pov
Returns: {
    "player_position": PlayerPosition,
    "fov_tiles": List[FOVTile],
    "ambient": {"light_level": str, "sound_hints": List[str], "weather": str}
}

# Storyboard detection (in action_parser.py)
def detect_storyboard(text: str) -> Optional[str]:
    """Returns storyboard type if action triggers one, else None."""

# Storyboard handler (in game_engine.py)
def _handle_storyboard(session, action) -> ActionResult:
    """Generates narrative with LLM, returns ActionResult with storyboard_moment field."""
```

---

## Acceptance Criteria (Standard Format)

AC-01 [FR-01]: Given a GameSession, when it is saved and reloaded, then `session.player_position` has identical x, y, facing, floor, and area_id values.

AC-02 [FR-02]: Given `player_position.facing = "north"` and `player_position.x = 5, y = 5`, when action `"move forward"` is processed, then `player_position.y == 4` (moved north) and `facing` remains "north".

AC-03 [FR-03]: Given any action that moves the player, when the action response is received, then `response.player_position` reflects the updated position.

AC-04 [FR-04]: Given `GET /game/session/{id}/pov` with player facing north at (5,8), when the response is received, then `fov_tiles` contains tiles at forward_1, forward_2, and side tiles — none behind walls.

AC-05 [FR-05]: Given DM narrative containing `[REVEAL:guard_01]`, when processed, then `guard_01` entity in subsequent `/pov` response has `revealed=true`.

AC-06 [FR-06]: Given action `"examine sword"`, when processed, then `ActionResult.storyboard_moment.type == "item_closeup"` and `duration_ms > 0`.

AC-07 [FR-09]: Given identical player position and map, when `/pov` is called twice, then both responses have identical `fov_tiles` content.

---

## Performance Requirements

- FOV calculation (32x32 grid, depth 5): < 20ms
- `update_position()`: < 1ms
- `/pov` endpoint total response: < 50ms (no LLM call)
- Storyboard LLM narrative: < 3 seconds (Haiku model)

---

## Error Handling

| Condition | Behavior |
|---|---|
| Movement out of map bounds | Position clamped to map edges; narrative notes obstacle |
| Movement into wall tile | Position unchanged; narrative notes wall |
| Unknown storyboard action | Falls through to default action handler |
| Area ID not found in map registry | Returns empty FOV with error flag |

---

## Integration Points

- **Map Generator (Phase 4):** FOV reads tile grid from MapData
- **Entity Placer (Phase 4):** Entity positions from scene_data used in FOV entity lists
- **DM Agent (Module 6):** `[REVEAL:entity_id]` markers parsed from DM narrative
- **Godot Client (Phase 1):** Polls `/pov` after each action; triggers fade-in on `revealed=true`
- **Save/Load:** `player_position` serialized in GameSession

---

## Test Coverage Target

- **Target:** ≥ 90% line coverage
- **Must cover:** all 4 facing directions + movement, FOV wall occlusion, REVEAL marker parsing, storyboard type detection, save/load position round-trip, bounds clamping
