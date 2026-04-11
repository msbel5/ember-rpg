# Copilot Consumer Wiring Prompt — 2026-04-11

You just finished Waves 1–7 (all committed). Now Claude's asset pipeline lane needs you to close two follow-on tasks that were **explicitly out of scope** for Waves 2 and 3: wiring the adapter_prompts.json and ui_plan.json data files you shipped into their actual runtime consumers. After that, close the `asset_cache.json` / `items_plan.json` drift that your previous runs left in the working tree.

---

## 0. Starting state

Recent history (top to bottom = newest to oldest):
```
0315815 asset: per-kind LoRA scale override + technical prompt rewrite   [Claude]
6186f47 docs: land Wave 2/3 PRD content Copilot forgot to commit          [Claude]
fe43d3d asset: rembg birefnet fallback + alpha matting + silhouette rewrite [Claude]
580f951 asset: add 7 new categories for playable shell                    [Claude]
4cb6de9 fix(travel): sync world graph region transitions over ws          [you, Wave 7]
bdbd390 feat(dialog): wire ask-about topic probe modal                    [you, Wave 6]
0c6b1aa fix(save): enforce schema v4 on load and listings                 [you, Wave 5]
a51351b feat(combat): surface turn economy in campaign snapshot and rail  [you, Wave 4]
a7fb345 docs: PRD_ui_element_catalog_v1 + ui_plan data                    [you, Wave 3]
abf0594 docs: PRD_multi_universe_item_prompts_v1 + adapter prompt data    [you, Wave 2]
```

Claude also landed the Wave 2 and Wave 3 PRD markdown content you forgot to commit (6186f47), and extended `tools/asset_pipeline.py` with 7 new asset kinds + per-kind LoRA scale override + improved rembg.

---

## Hard rules (unchanged from Waves 1–7)

1. **Forbidden paths** — never read, never edit:
   - `frp-backend/engine/kernel/**` — frozen
   - `tools/asset_raw/**`, `tools/asset_cache.json`, `tools/asset_jobs/*_plan.json` — runtime artifacts, not committable
   - `godot-client/assets/generated/**` — runtime artifacts
   - `tools/smoke_new_categories.py` — Claude's lane
   - `godot-client/project.godot`, `.godot/**`, `*.import`
   - `frp-backend/requirements.txt`, `pyproject.toml`, `.venv/**`

2. **You may touch `tools/asset_pipeline.py`** — this is a deliberate exception for the consumer wiring in Wave C1 below. Read the current 2000-line file carefully before editing. Claude's lane normally owns it but this wiring belongs to you because it consumes the data you shipped.

3. **PowerShell only.** MSYS bash chokes on the wrapper shims. `powershell.exe -NoProfile -Command "..."` or cmd.

4. **One wave = one commit.** Scope discipline.

5. **Blockers**: `docs/handoffs/COPILOT_BLOCKED_wave_C*.md` with exact error and minimal unblocking question.

6. **Commit footer:**
   ```
   Co-Authored-By: GitHub Copilot CLI 1.0.21 <noreply@github.com>
   ```

---

## WAVE C1 — Wire adapter_prompts.json into the asset pipeline

**PRD:** `docs/prd/active/PRD_multi_universe_item_prompts_v1.md` (your own, content now landed)
**Data:** `tools/asset_jobs/adapter_prompts.json` (your own, already shipped)

**Goal:** Make the asset pipeline accept a `--adapter <id>` argument that selects one of the four universe adapters and:
1. Prepends the adapter's `prompt_prefix` to `ITEM_STYLE_PREFIX` for every item job in the run.
2. Appends the adapter's `negative_prompt` to the item kind's negative prompt.
3. Applies `seed_offset` to every item job's seed (for deterministic per-universe variation).
4. Applies `lora_weight_overrides` (if any) when calling `pipeline.set_adapters` at the start of the run.

**Work:**

1. Read `tools/asset_pipeline.py` in full before editing. Note the existing `build_item_prompt()`, `ITEM_STYLE_PREFIX`, `ITEM_NEGATIVE`, `_KIND_NEGATIVES`, `lora_scale_for_kind`, `LocalSDXLGenerator.__init__`, and the CLI argparse block.

2. Add a loader:
   ```python
   ADAPTER_PROMPTS_FILE = PROJECT_ROOT / "tools" / "asset_jobs" / "adapter_prompts.json"

   def load_adapter_prompts() -> dict[str, dict[str, Any]]:
       """Returns the full adapter prompts map, or {} if the file is missing."""
       ...

   def resolve_adapter(adapter_id: str | None) -> dict[str, Any]:
       """Returns the adapter entry, or {} if not set / unknown."""
       ...
   ```

3. Add `--adapter` to the argparse block with choices dynamically read from `adapter_prompts.json` at parse time. Default is no adapter (empty string) which preserves current behavior.

4. Thread the selected adapter through `generate_jobs()`. Adapter effects:
   - **Prompt prefix**: prepend `adapter["prompt_prefix"]` to `ITEM_STYLE_PREFIX` ONLY for items (`job.kind == "items"`). Do not touch other kinds.
   - **Negative**: concatenate `adapter["negative_prompt"]` onto the items negative.
   - **Seed offset**: add `adapter["seed_offset"]` to every `job.seed` at dispatch time for items only.
   - **LoRA weight overrides**: if `adapter["lora_weight_overrides"]` is non-empty, apply them to the LoRA stack via `pipeline.set_adapters(adapter_names, scaled_weights)` at `LocalSDXLGenerator.__init__` time (after the default stack loads). Leave the default alone if the override is empty.

5. Add two tests at `frp-backend/tests/test_adapter_prompts_wiring.py`:
   - `test_adapter_applies_prefix_and_seed_offset`: mock/spy on the prompt builder and seed resolution, assert that choosing `scifi_frontier` prepends its prefix and shifts the seed by the offset.
   - `test_adapter_none_preserves_default`: assert default behavior when `--adapter` is not set.

   These are pure Python tests against the pipeline module — no SDXL model load required. Use the `unittest.mock` standard library, not pytest fixtures with heavy imports.

6. Run the verification below.

**Verification:**
```powershell
C:\Users\msbel\projects\ember-rpg\.venv\Scripts\python.exe -m pytest frp-backend\tests\test_adapter_prompts_data.py frp-backend\tests\test_adapter_prompts_wiring.py -q
C:\Users\msbel\projects\ember-rpg\.venv\Scripts\python.exe -c "import sys; sys.path.insert(0, 'tools'); import asset_pipeline as ap; print(ap.load_adapter_prompts().keys())"
C:\Users\msbel\projects\ember-rpg\.venv\Scripts\python.exe tools\asset_pipeline.py --adapter scifi_frontier --plan items
```

**Commit message:**
```
feat(asset): wire adapter_prompts into asset_pipeline per-universe generation

- Add --adapter CLI flag with choices from adapter_prompts.json
- Prepend adapter prompt_prefix to ITEM_STYLE_PREFIX for item jobs
- Append adapter negative_prompt to items kind negative
- Apply adapter seed_offset to item jobs
- Apply lora_weight_overrides via set_adapters at pipeline init
- Add test_adapter_prompts_wiring.py contract coverage

Co-Authored-By: GitHub Copilot CLI 1.0.21 <noreply@github.com>
```

---

## WAVE C2 — Wire ui_plan.json into a UI element generation kind

**PRD:** `docs/prd/active/PRD_ui_element_catalog_v1.md` (your own, content now landed)
**Data:** `tools/asset_jobs/ui_plan.json` (your own, already shipped)

**Goal:** Make the asset pipeline able to generate painted UI elements from `ui_plan.json` via `--generate ui_plan`. This is a NEW asset kind beyond Claude's existing `combat_ui` / `status_bars` / `ui_banners` kinds — those are hand-authored in `asset_pipeline.py` DEFS dicts, while `ui_plan` is a data-driven extensible catalog.

**Work:**

1. Add a new kind `ui_plan` following the existing kind dispatch pattern in `asset_pipeline.py`:
   - `GENERATED_UI_PLAN_DIR = GENERATED_DIR / "ui_plan"`
   - `UI_PLAN_FILE = PROJECT_ROOT / "tools" / "asset_jobs" / "ui_plan.json"`
   - `build_ui_plan_jobs(limit, variants)` reads `ui_plan.json`, iterates entries, builds `Job` objects. Each entry has `{id, category, size, prompt_hint, variants}` per PRD_ui_element_catalog_v1.
   - Size per entry: if entry has `size: [w, h]` use it, else default to 1024x1024.
   - Prompt: template `"A painted CRPG {category} UI element for a BG1 style production game, {prompt_hint}, clean game HUD asset, transparent background, painterly brushwork"`
   - Output path: `ui_plan/{id}.png`
   - Register in `_KIND_SIZES`, `build_jobs()` dispatch, `ensure_output_dirs()`, `write_manifest()`, `list_assets()`, and argparse `_kind_choices`.
   - Add to `_TRANSPARENT_KINDS` (UI elements need alpha).

2. Add `frp-backend/tests/test_ui_plan_jobs.py`:
   - `test_build_ui_plan_jobs_non_empty`: loads `ui_plan.json`, builds jobs, asserts len >= 5.
   - `test_ui_plan_jobs_have_required_fields`: every job has key, prompt (>20 words), output_relative_path starting with `ui_plan/`, seed.

3. Run verification.

**Verification:**
```powershell
C:\Users\msbel\projects\ember-rpg\.venv\Scripts\python.exe -m pytest frp-backend\tests\test_ui_plan_data.py frp-backend\tests\test_ui_plan_jobs.py -q
C:\Users\msbel\projects\ember-rpg\.venv\Scripts\python.exe tools\asset_pipeline.py --plan ui_plan
C:\Users\msbel\projects\ember-rpg\.venv\Scripts\python.exe tools\asset_pipeline.py --list
```

`--list` should now show `ui_plan` with a non-zero count.

**Commit message:**
```
feat(asset): wire ui_plan.json into data-driven UI asset generation

- Add ui_plan asset kind reading tools/asset_jobs/ui_plan.json
- build_ui_plan_jobs() iterates the catalog with per-entry size
- Integrate into build_jobs() dispatch, ensure_output_dirs,
  write_manifest, list_assets, CLI argparse
- Mark ui_plan as transparent-kind so rembg runs at postprocess
- Add test_ui_plan_jobs.py contract coverage

Co-Authored-By: GitHub Copilot CLI 1.0.21 <noreply@github.com>
```

---

## WAVE C3 — Clean working-tree drift

**Goal:** The repo has uncommitted drift from your earlier runs that isn't meaningful changes. Trim it to a clean state so the overnight asset generation Claude is about to run starts from a pristine baseline.

**Work:**

1. Check `git status --short`. For each unstaged modification:
   - `tools/asset_cache.json`, `tools/asset_jobs/items_plan.json`, `tools/asset_raw/*.png` → these are runtime artifacts. Leave them alone or add them to `.gitignore` if they're not already there. Do NOT commit them.
   - `godot-client/autoloads/game_state.gd` → if the modification is a real bug fix not already in your committed waves, commit it separately with a descriptive message. Otherwise `git checkout -- godot-client/autoloads/game_state.gd`.
   - Any other drift: evaluate individually, don't mass-commit.

2. Verify `.gitignore` covers:
   - `tools/asset_raw/`
   - `tools/asset_cache.json`
   - `godot-client/assets/generated/`
   - `tools/asset_jobs/*_plan.json` (these are runtime artifacts, not committed data — the hand-authored data files are `adapter_prompts.json` and `ui_plan.json` only)
   
   If any of those aren't ignored, add them in a single `chore(gitignore)` commit.

3. DO NOT run `git clean -fd`. DO NOT `git checkout` on files you don't understand.

**Verification:**
```powershell
git status --short
```
Should show only legitimately in-progress files or be completely clean.

---

## After C1, C2, C3

Run the full verification suite one final time:

```powershell
C:\Users\msbel\projects\ember-rpg\.venv\Scripts\python.exe -m pytest frp-backend\tests -q
godot --headless --path C:\Users\msbel\projects\ember-rpg\godot-client -s res://tests/run_headless_tests.gd
```

Write `docs/handoffs/COPILOT_WAVE_C_COMPLETE.md` with a one-paragraph summary of C1/C2/C3 outcomes and stop. Do not start new work autonomously.

---

## Cheat sheet — invocation

```powershell
cd C:\Users\msbel\projects\ember-rpg
codex exec --model gpt-5 @"
Read docs/handoffs/COPILOT_WAVE_3_CONSUMER_WIRING.md from top to bottom.
Execute Waves C1, C2, C3 in order. Commit after each wave's verification
passes. Do not touch forbidden paths. Stop after C3.
"@
```
