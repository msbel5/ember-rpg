"""Registry loading and validation for the world simulation kernel."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from engine.data_loader import load_json_path, load_registry_map_from_path


_BASE_DIR = Path(__file__).resolve().parents[2] / "data" / "world"


def _normalized_map(filename: str, key: str) -> dict[str, dict[str, Any]]:
    return load_registry_map_from_path(_BASE_DIR / filename, collection_key=key, id_field="id")


@lru_cache(maxsize=None)
def load_world_profiles() -> dict[str, dict[str, Any]]:
    return _normalized_map("profiles.json", "profiles")


@lru_cache(maxsize=None)
def load_world_biomes() -> dict[str, dict[str, Any]]:
    return _normalized_map("biomes.json", "biomes")


@lru_cache(maxsize=None)
def load_species_templates() -> dict[str, dict[str, Any]]:
    return _normalized_map("species_templates.json", "species_templates")


@lru_cache(maxsize=None)
def load_culture_templates() -> dict[str, dict[str, Any]]:
    return _normalized_map("cultures.json", "cultures")


@lru_cache(maxsize=None)
def load_building_templates() -> dict[str, dict[str, Any]]:
    return _normalized_map("building_templates.json", "building_templates")


@lru_cache(maxsize=None)
def load_furniture_templates() -> dict[str, dict[str, Any]]:
    return _normalized_map("furniture.json", "furniture")


@lru_cache(maxsize=None)
def load_adapter_pack(adapter_id: str) -> dict[str, Any]:
    path = _BASE_DIR / "adapters" / f"{adapter_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Adapter pack not found: {adapter_id}")
    return load_json_path(path)


@lru_cache(maxsize=None)
def load_adapter_ids() -> tuple[str, ...]:
    adapters_dir = _BASE_DIR / "adapters"
    return tuple(sorted(path.stem for path in adapters_dir.glob("*.json")))


def validate_world_registries() -> None:
    profiles = load_world_profiles()
    biomes = load_world_biomes()
    species = load_species_templates()
    cultures = load_culture_templates()
    buildings = load_building_templates()
    furniture = load_furniture_templates()
    if "standard" not in profiles:
        raise ValueError("Missing required standard world profile")

    for profile_id, profile in profiles.items():
        if profile["world_width"] <= 0 or profile["world_height"] <= 0:
            raise ValueError(f"Invalid world dimensions for profile {profile_id}")
        if profile["plate_count"] < 2:
            raise ValueError(f"Invalid plate count for profile {profile_id}")

    for biome_id, biome in biomes.items():
        for field in ("temperature_range", "moisture_range", "elevation_range"):
            if len(biome[field]) != 2:
                raise ValueError(f"Biome {biome_id} has invalid range field {field}")

    for species_id, template in species.items():
        for habitat in template.get("habitats", []):
            if habitat not in biomes:
                raise ValueError(f"Species {species_id} references unknown biome {habitat}")
        culture_hint = template.get("culture_hint")
        if template.get("sapient") and culture_hint not in cultures:
            raise ValueError(f"Sapient species {species_id} has unknown culture hint {culture_hint}")

    for building_id, building in buildings.items():
        for item in building.get("required_furniture", []):
            if item["kind"] not in furniture:
                raise ValueError(
                    f"Building template {building_id} references unknown furniture {item['kind']}"
                )

    for adapter_id in load_adapter_ids():
        adapter = load_adapter_pack(adapter_id)
        species_labels = adapter.get("species_labels", {})
        allowed_species = adapter.get("allowed_species", [])
        for species_id in species_labels:
            if species_id not in species:
                raise ValueError(f"Adapter {adapter_id} references unknown species {species_id}")
        for species_id in allowed_species:
            if species_id not in species:
                raise ValueError(f"Adapter {adapter_id} allows unknown species {species_id}")
