# PRD: Asset Category Expansion — Spells, Portraits, Status Icons, Combat UI, Body Silhouettes, Status Bars, Banners
**Project:** Ember RPG
**Phase:** 2 — Playable Shell
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-04-11
**Status:** Draft

---

## 1. Purpose
The current asset pipeline at `tools/asset_pipeline.py` generates painted CRPG content for three families: `items`, `sprites`, `tiles`. The playable shell needs seven additional families to render a BG1/Fallout 1-class combat and exploration experience: spell icons, dialogue portraits, status effect icons, aimed-shot body silhouettes, combat action badges, HP/MP/SP/AC bar assets, and UI banners. This PRD defines the schema, prompts, sizes, and verification for all seven new categories so Claude can extend the pipeline without ambiguity.

## 2. Scope
**In scope:**
- New category definitions (name → painted-prompt descriptor) for: `spells`, `portraits`, `status_icons`, `body_silhouettes`, `combat_ui`, `status_bars`, `ui_banners`.
- Per-category style prefix and SDXL-native image dimensions.
- Per-category postprocess policy (background removal vs. preserve).
- Wiring into the existing `build_jobs(kind, ...)` dispatcher, argparse `--plan` / `--generate` choices, output directory structure, and manifest.
- Smoke test that generates at least one asset per new category at hi-res.

**Out of scope:**
- Changing or renaming any existing `items`/`sprites`/`tiles` logic.
- Consumer wiring in Godot (`modal_host.tscn`, `instrument_rail.gd`, portrait panels, etc.) — that is Copilot's lane and lands in a follow-up PRD.
- Per-adapter prompt prefix injection (handled by `PRD_multi_universe_item_prompts_v1.md` in Wave 2 of the Copilot handoff).
- Spell cast animation spritesheets (static icons only for v1; animations are a future PRD).
- Portrait face sculpting or character creator integration (catalog-only).

## 3. Functional Requirements (FR)

**FR-01:** The pipeline MUST accept `spells`, `portraits`, `status_icons`, `body_silhouettes`, `combat_ui`, `status_bars`, `ui_banners` as valid `--plan` and `--generate` kinds.

**FR-02:** Each new kind MUST dispatch through a dedicated `build_<kind>_jobs()` function returning a list of `Job` objects with stable seeds and kind-specific output paths under `godot-client/assets/generated/<kind>/<slug>.png`.

**FR-03:** Each new kind MUST use SDXL-native dimensions that fit RTX 3070 8 GB VRAM in a single `pipeline.__call__`:
| Kind | Width × Height |
|---|---|
| `spells` | 1024 × 1024 |
| `portraits` | 1024 × 1024 |
| `status_icons` | 1024 × 1024 |
| `body_silhouettes` | 832 × 1216 (portrait 2:3) |
| `combat_ui` | 1024 × 1024 |
| `status_bars` | 1344 × 768 (landscape ~16:9) |
| `ui_banners` | 1536 × 640 (wide ~2.4:1) |

**FR-04:** Postprocess policy per kind:
| Kind | Background removal | Reason |
|---|---|---|
| `spells` | YES (rembg isnet) | Icon composited over arbitrary backgrounds |
| `portraits` | NO | Painted backgrounds are part of the portrait |
| `status_icons` | YES | Overlaid on status bars |
| `body_silhouettes` | YES | Overlaid with hit-zone rectangles in Godot |
| `combat_ui` | YES | Overlaid on combat scene |
| `status_bars` | NO | Frame + fill are the bar |
| `ui_banners` | YES | Banner floats over scene chrome |

**FR-05:** The `build_jobs("all", ...)` dispatch MUST include all seven new kinds so `--plan all` and `--generate all` cover the full catalog.

**FR-06:** `ensure_output_dirs()` MUST create the seven new `godot-client/assets/generated/<kind>/` directories.

**FR-07:** `write_manifest()` MUST record new kinds in dedicated manifest buckets keyed by slug. Manifest schema version stays at 2; new buckets added non-destructively.

**FR-08:** A smoke-test invocation (`python tools/asset_pipeline.py --generate <kind> --limit 1 --backend local_sdxl --no-lora-stack=false`) MUST succeed end-to-end for every new kind without crashing the pipeline, producing a PNG at the expected size on disk.

## 4. Data Structures

All seven categories follow the existing `Job` dataclass (`tools/asset_pipeline.py`:381). The metadata dict carries kind-specific hints but no schema change is required.

Category definition tables (module-level dicts, `name: str → description: str`):

```python
SPELL_DEFS: dict[str, str]          # spell id -> painted descriptor
PORTRAIT_DEFS: dict[str, str]       # portrait id -> painted descriptor
STATUS_ICON_DEFS: dict[str, str]    # status effect id -> painted descriptor
BODY_SILHOUETTE_DEFS: dict[str, str]  # archetype id -> painted descriptor
COMBAT_UI_DEFS: dict[str, str]      # combat UI element id -> painted descriptor
STATUS_BAR_DEFS: dict[str, str]     # bar asset id -> painted descriptor
UI_BANNER_DEFS: dict[str, str]      # banner id -> painted descriptor
```

Per-category style prefix constants (compressed before prompt concat):

```python
SPELL_STYLE_PREFIX: str
PORTRAIT_STYLE_PREFIX: str
STATUS_ICON_STYLE_PREFIX: str
BODY_SILHOUETTE_STYLE_PREFIX: str
COMBAT_UI_STYLE_PREFIX: str
STATUS_BAR_STYLE_PREFIX: str
UI_BANNER_STYLE_PREFIX: str
```

## 5. Public API

```python
def build_spell_jobs(limit: int | None = None, variants: int = 1) -> list[Job]
def build_portrait_jobs(limit: int | None = None, variants: int = 1) -> list[Job]
def build_status_icon_jobs(limit: int | None = None, variants: int = 1) -> list[Job]
def build_body_silhouette_jobs(limit: int | None = None, variants: int = 1) -> list[Job]
def build_combat_ui_jobs(limit: int | None = None, variants: int = 1) -> list[Job]
def build_status_bar_jobs(limit: int | None = None, variants: int = 1) -> list[Job]
def build_ui_banner_jobs(limit: int | None = None, variants: int = 1) -> list[Job]

def size_for_kind(kind: str) -> tuple[int, int]
    # Returns the SDXL-native (width, height) for the given kind.
    # Defaults to (1024, 1024) for any unrecognized kind.

def postprocess_for_kind(raw_img: Image.Image, kind: str, final_size: tuple[int, int]) -> Image.Image
    # Applies the per-kind rembg / no-rembg policy and final resize.
```

## 6. Acceptance Criteria (AC)

**AC-01 [FR-01]:** Running `python tools/asset_pipeline.py --plan spells` writes a job plan JSON at `tools/asset_jobs/spells_plan.json` containing at least 20 jobs. Same for `portraits`, `status_icons`, `body_silhouettes`, `combat_ui`, `status_bars`, `ui_banners` (each with at least 5 jobs).

**AC-02 [FR-02]:** Every job in the new plan files has:
- a unique `key` starting with `spell_`, `portrait_`, `statusicon_`, `bodysilhouette_`, `combatui_`, `statusbar_`, or `uibanner_`
- a `prompt` longer than 20 words
- an `output_relative_path` under `spells/`, `portraits/`, `status_icons/`, `body_silhouettes/`, `combat_ui/`, `status_bars/`, or `ui_banners/`
- a stable deterministic `seed` that does not change between two runs

**AC-03 [FR-03]:** After calling `size_for_kind(kind)`, every returned tuple matches the FR-03 table exactly.

**AC-04 [FR-04]:** Running `--generate spells --limit 1` produces a PNG with an alpha channel that has at least one fully-transparent pixel (proving rembg ran). Running `--generate portraits --limit 1` produces a PNG whose alpha channel has zero fully-transparent pixels (proving rembg was skipped).

**AC-05 [FR-05]:** `build_jobs("all")` returns a job list whose distinct `kind` values are exactly `{sprites, tiles, items, spells, portraits, status_icons, body_silhouettes, combat_ui, status_bars, ui_banners}`.

**AC-06 [FR-06]:** After calling `ensure_output_dirs()`, all seven new directories exist on disk.

**AC-07 [FR-07]:** `write_manifest(cache, jobs)` writes a manifest JSON containing top-level keys `spells`, `portraits`, `status_icons`, `body_silhouettes`, `combat_ui`, `status_bars`, `ui_banners` (each an object keyed by slug).

**AC-08 [FR-08]:** A smoke-test invocation running 1 job per new kind completes without raising, with each resulting PNG on disk at the expected width × height per FR-03.

## 7. Performance Requirements

- Each 1024×1024 job on RTX 3070 8 GB with LCM 8-step: ≤ 12s warm (excluding first-load LoRA stack).
- Each 832×1216 or 1344×768 or 1536×640 job: ≤ 18s warm.
- Full category smoke test (7 jobs, one per kind): ≤ 3 minutes total including rembg postprocess.
- Module import of `asset_pipeline.py` after the edit: no change in import time (≤ 200 ms additional).

## 8. Error Handling

- If a new category's DEFS dict is empty, `build_<kind>_jobs()` returns an empty list (not an error).
- If `size_for_kind()` is called with an unknown kind, it returns `(1024, 1024)` and emits no warning.
- If rembg is unavailable at runtime, `postprocess_for_kind` falls back to `convert("RGBA")` for the removal-required kinds (same behavior as today's `remove_background`).
- If the SDXL pipeline fails for a single job, the loop skips it and continues with the next job (unchanged from current behavior).
- If `--limit` is set lower than the number of new kinds in `--generate all`, the loop processes jobs in the order returned by `build_jobs("all", ...)` and stops at the limit.

## 9. Integration Points

**Editable by this PRD (Claude's lane):**
- `tools/asset_pipeline.py` — add DEFS, style prefixes, build_* functions, size_for_kind, postprocess_for_kind, wire into dispatch + argparse + ensure_output_dirs + write_manifest
- `tools/asset_jobs/*_plan.json` — written by `--plan <kind>` invocations (not hand-authored)
- `godot-client/assets/generated/{spells,portraits,status_icons,body_silhouettes,combat_ui,status_bars,ui_banners}/` — output dirs, created by `ensure_output_dirs`

**Not editable by this PRD:**
- `frp-backend/**` — backend does not consume assets directly
- Godot scene files or scripts — consumer wiring is a separate PRD
- Existing category definitions (`SPRITE_DEFS`, `TILE_DEFS`, `ITEM_STYLE_PREFIX`, etc.)
- `project.godot` — already 1080p
- `tools/asset_jobs/adapter_prompts.json` — Wave 2 of Copilot handoff

## 10. Test Coverage Target

Manual smoke coverage for v1 (no pytest — pipeline is dev tooling, not shipped code):
- `--plan all` writes valid JSON for all kinds including the seven new ones
- `--generate <kind> --limit 1` succeeds for each new kind against `local_sdxl` backend
- Visual inspection of at least one generated asset per new kind before full-batch regen

## 11. Changelog
- 2026-04-11 v1 draft: initial specification for seven new asset families required by the playable shell.
