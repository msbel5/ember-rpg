---
## 1. Purpose
Define a data-only adapter prompt map so item art generation can select a universe-appropriate prompt prefix without changing the asset pipeline implementation in this wave.

## 2. Scope
- In scope: a JSON registry of adapter prompt metadata and a shape-validation unit test.
- Out of scope: pipeline consumer wiring, prompt execution, LoRA model changes, or any generated asset refresh.

## 3. Functional Requirements (FR)
FR-01: The repo SHALL contain `tools/asset_jobs/adapter_prompts.json`.
FR-02: The file SHALL define prompt metadata for `fantasy_ember`, `scifi_frontier`, `post_apocalypse`, and `weird_fiction`.
FR-03: Each adapter entry SHALL expose `prompt_prefix`, `negative_prompt`, `seed_offset`, and `lora_weight_overrides`.
FR-04: A unit test SHALL verify the file exists, all required adapters are present, and the required fields are non-empty / correctly typed.

## 4. Data Structures
```json
{
  "<adapter_id>": {
    "prompt_prefix": "painted <universe descriptor>, <style anchor>, <tone>",
    "negative_prompt": "pixel art, blurry, low quality, watermark, ...",
    "seed_offset": 0,
    "lora_weight_overrides": {}
  }
}
```

## 5. Public API
This wave adds no runtime API. Consumers read the JSON file directly in a later asset-pipeline integration wave.

## 6. Acceptance Criteria (AC)
AC-01 [FR-01]: Given the repo root, when the asset job registry is inspected, then `tools/asset_jobs/adapter_prompts.json` exists.
AC-02 [FR-02]: Given the prompt registry is loaded, when required adapters are checked, then all four universe adapters are present.
AC-03 [FR-03]: Given an adapter entry, when its shape is inspected, then the four required fields are present with `int`/`dict` types where required.
AC-04 [FR-04]: Given the unit test suite runs, when `test_adapter_prompts_data.py` executes, then empty prompt prefixes are rejected and the shape contract passes.

## 7. Performance Requirements
The validation test should complete in under 50 ms on a warm local run because it only parses one small JSON file.

## 8. Error Handling
Missing files, unknown adapters, empty prompt strings, or wrong value types fail the contract test with adapter-specific messages.

## 9. Integration Points
- `docs/prd/active/PRD_character_creation_v2.md` for adapter naming context.
- `tools/asset_pipeline.py` as a future read-only consumer of this data.
- `frp-backend/tests/test_adapter_prompts_data.py` as the enforcement point.

## 10. Test Coverage Target
100% branch coverage for the shape-validation test file and 100% validation of required adapter IDs.