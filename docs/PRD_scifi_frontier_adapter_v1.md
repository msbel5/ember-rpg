# PRD: Sci-Fi Frontier Adapter v1
**Project:** Ember RPG  
**Phase:** 1-4  
**Author:** Codex  
**Date:** 2026-03-27  
**Status:** Approved  

---

## 1. Purpose
Define the first non-fantasy live adapter for the world simulation kernel. The sci-fi frontier adapter maps kernel-native species, cultures, settlement templates, and labels into a frontier outpost campaign while keeping the kernel itself genre-agnostic.

## 2. Scope
- In scope: adapter registry format, allowed species, display labels, starter content defaults, and runtime campaign selection behavior.
- Out of scope: multi-planet travel, space combat, or a second sci-fi client UI theme pack.

## 3. Functional Requirements (FR)
FR-01: The adapter must load from `frp-backend/data/world/adapters/scifi_frontier.json`.
FR-02: The adapter must expose an `allowed_species` list that constrains which sapient and domesticated species can seed a playable sci-fi frontier campaign.
FR-03: The adapter must provide display labels for at least humans, synthetics, aurans, and mycoids.
FR-04: Campaign creation with `adapter_id="scifi_frontier"` must generate a valid world, active region, and realized settlement without using fantasy-only labels.
FR-05: The adapter must expose starter content defaults that the campaign runtime can use for player bootstrap and onboarding copy.
FR-06: Invalid species references in the adapter must fail registry validation deterministically.

## 4. Data Structures
```python
class AdapterPack(TypedDict):
    id: str
    allowed_species: list[str]
    species_labels: dict[str, str]
    starter_content: dict[str, Any]
```

## 5. Public API
```python
def load_adapter_pack(adapter_id: str) -> dict[str, Any]
def validate_world_registries() -> None
def create_campaign(player_name: str, player_class: str, adapter_id: str, profile_id: str, seed: int | None) -> CampaignContext
```
- Preconditions: `adapter_id` must resolve to a valid adapter pack.
- Postconditions: `create_campaign(..., adapter_id="scifi_frontier")` returns a playable campaign snapshot.
- Exceptions: unknown adapter IDs or invalid species references raise `FileNotFoundError` or `ValueError`.

## 6. Acceptance Criteria (AC)
AC-01 [FR-01]: The adapter file is present and loadable through `load_adapter_pack("scifi_frontier")`.
AC-02 [FR-02]: `allowed_species` includes `human`, `synthetic`, `auran`, and `mycoid`.
AC-03 [FR-03]: Applying the adapter yields display labels `Settler`, `Synth`, `Auran`, and `Mycoid`.
AC-04 [FR-04]: `POST /game/campaigns` with `adapter_id="scifi_frontier"` returns HTTP 200 and a populated campaign snapshot.
AC-05 [FR-05]: The adapter exposes `starter_content.default_player_class`.
AC-06 [FR-06]: Registry validation rejects unknown adapter species references.

## 7. Performance Requirements
- Adapter loading and validation must complete in under 20 ms on developer hardware.
- Sci-fi frontier campaign creation must remain within the same worldgen budget as fantasy campaigns.

## 8. Error Handling
- Unknown adapter files must raise `FileNotFoundError`.
- Unknown species references must raise `ValueError` during registry validation.
- Missing starter content falls back only if the adapter explicitly defines a fallback default.

## 9. Integration Points
- Consumed by `engine.api.campaign_runtime.CampaignRuntime`.
- Validated by `engine.worldgen.registries.validate_world_registries`.
- Surfaced to clients through the campaign-first API and adapter-aware UI labeling.

## 10. Test Coverage Target
- Minimum 95% coverage on sci-fi adapter loading and campaign bootstrap paths.
- Required targeted suites: `test_scifi_frontier_adapter.py` and `test_campaign_api_v2.py`.

## Changelog
- 2026-03-27: Initial approved PRD for the first non-fantasy live adapter.
