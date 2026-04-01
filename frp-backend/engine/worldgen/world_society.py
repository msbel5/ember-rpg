"""Species and civilization seeding helpers."""
from __future__ import annotations

import random

from .models import SettlementSeed, SpeciesLineage, WorldBlueprint
from .registries import load_adapter_pack, load_culture_templates, load_species_templates
from .world_regions import region_lookup
from .world_seed import stable_seed_from_parts


def seed_species(world: WorldBlueprint) -> WorldBlueprint:
    species_registry = load_species_templates()
    lineages: list[SpeciesLineage] = []
    domestication_pools: dict[str, list[str]] = {}
    for species_id in sorted(species_registry.keys()):
        template = species_registry[species_id]
        scored_regions: list[tuple[float, str]] = []
        for region in world.regions:
            score = 0.0
            if region["biome_id"] in template["habitats"]:
                score += 0.6
            temp_min, temp_max = template["temperature_range"]
            moist_min, moist_max = template["moisture_range"]
            if temp_min <= region["avg_temperature"] <= temp_max:
                score += 0.2
            if moist_min <= region["avg_moisture"] <= moist_max:
                score += 0.2
            if score > 0.0:
                scored_regions.append((round(score, 3), region["id"]))
        scored_regions.sort(key=lambda item: (-item[0], item[1]))
        if not scored_regions and template["sapient"]:
            fallback = sorted(
                world.regions,
                key=lambda region: (
                    abs(region["avg_temperature"] - sum(template["temperature_range"]) / 2),
                    abs(region["avg_moisture"] - sum(template["moisture_range"]) / 2),
                ),
            )[0]
            scored_regions.append((0.1, fallback["id"]))
        if not scored_regions:
            continue
        lineages.append(
            SpeciesLineage(
                species_id=species_id,
                species_name=template["name"],
                sapient=bool(template["sapient"]),
                home_regions=[scored_regions[0][1]],
                expansion_regions=[region_id for _, region_id in scored_regions[1:3]],
                adapter_payload={},
            )
        )
        for role in template.get("domestication_roles", []):
            domestication_pools.setdefault(role, []).append(species_id)
    world.species_lineages = lineages
    world.domestication_pools = domestication_pools
    return world


def adapt_species(world: WorldBlueprint, adapter_id: str) -> WorldBlueprint:
    labels = load_adapter_pack(adapter_id).get("species_labels", {})
    for lineage in world.species_lineages:
        lineage.adapter_payload = {
            "adapter_id": adapter_id,
            "display_name": labels.get(lineage.species_id, lineage.species_name),
        }
    return world


def seed_civilizations(world: WorldBlueprint) -> WorldBlueprint:
    species_registry = load_species_templates()
    cultures = load_culture_templates()
    sapient_lineages = sorted(
        [lineage for lineage in world.species_lineages if lineage.sapient],
        key=lambda item: item.species_id,
    )
    world.factions = []
    world.settlements = []
    world.settlement_nodes = []
    world.faction_presence = {str(region["id"]): [] for region in world.regions}
    world.travel_edges = []
    world.region_economy = {}
    world.region_alerts = {str(region["id"]): [] for region in world.regions}

    if not sapient_lineages:
        return world

    lineage_candidates = {
        lineage.species_id: lineage_candidate_regions(world, lineage, species_registry[lineage.species_id])
        for lineage in sapient_lineages
    }
    desired_faction_count = min(10, max(6, len(sapient_lineages) + 3))
    chosen_origins: list[str] = []
    for index in range(desired_faction_count):
        lineage = sapient_lineages[index % len(sapient_lineages)]
        template = species_registry[lineage.species_id]
        culture_id = template["culture_hint"]
        culture = cultures[culture_id]
        origin_region = choose_region_with_spacing(
            world,
            lineage_candidates[lineage.species_id],
            chosen_origins,
            2,
            f"faction-origin:{lineage.species_id}:{index}",
        )
        chosen_origins.append(str(origin_region["id"]))
        faction_id = f"{lineage.species_id}_faction_{index:02d}_{world.seed % 997}"
        influence = round(0.42 + float(origin_region["settlement_suitability"]) * 0.34 + (index % 3) * 0.02, 3)
        cohesion = round(0.52 + len(culture["institution_bias"]) * 0.04, 3)
        world.factions.append(
            FactionSeed(
                id=faction_id,
                culture_id=culture_id,
                species_id=lineage.species_id,
                origin_region_id=str(origin_region["id"]),
                traits={"influence": influence, "cohesion": cohesion},
            )
        )

    faction_rotation = sorted(world.factions, key=lambda faction: (faction.species_id, faction.id))
    desired_settlement_count = min(20, max(12, len(faction_rotation) * 2))
    used_settlement_regions: list[str] = []
    biome_prefix = {
        "coast": "Harbor",
        "desert": "Sun",
        "mountain": "Stone",
        "plains": "Field",
        "swamp": "Mire",
        "temperate_forest": "Grove",
    }
    for settlement_index in range(desired_settlement_count):
        faction = faction_rotation[settlement_index % len(faction_rotation)]
        lineage = next(lineage for lineage in sapient_lineages if lineage.species_id == faction.species_id)
        culture = cultures[faction.culture_id]
        template = species_registry[faction.species_id]
        region = choose_region_with_spacing(
            world,
            lineage_candidates[lineage.species_id],
            used_settlement_regions,
            2,
            f"settlement:{faction.id}:{settlement_index}",
        )
        if str(region["id"]) in used_settlement_regions:
            continue
        used_settlement_regions.append(str(region["id"]))
        settlement_type = settlement_type_for_species(faction.species_id)
        focus = focus_for_culture(culture)
        prefix = biome_prefix.get(str(region["biome_id"]), "Frontier")
        center_name = f"{prefix} {template['name']} {settlement_type.title()}"
        population = int(150 + float(region["settlement_suitability"]) * 180 + (settlement_index % 4) * 18)
        node_id = f"node_{region['id']}_{settlement_index:02d}"
        node = {
            "id": node_id,
            "region_id": str(region["id"]),
            "faction_id": faction.id,
            "name": center_name,
            "settlement_type": settlement_type,
            "population": population,
            "building_focus": focus,
            "primary": True,
            "node_type": "primary_settlement",
            "biome_id": str(region["biome_id"]),
            "grid_position": list(region_grid_position(region)),
        }
        region["controller_faction_id"] = faction.id
        region["settlement_id"] = node_id
        region["settlement_node_ids"] = [node_id]
        region["primary_settlement_name"] = center_name
        world.settlement_nodes.append(node)
        world.settlements.append(
            SettlementSeed(
                id=node_id,
                faction_id=faction.id,
                region_id=str(region["id"]),
                settlement_type=settlement_type,
                population=population,
                center_name=center_name,
                building_focus=focus,
            )
        )
        world.faction_presence[str(region["id"])].append(
            {
                "faction_id": faction.id,
                "species_id": faction.species_id,
                "presence_type": "primary_settlement",
                "pressure": round(faction.traits.get("influence", 0.5), 3),
            }
        )

    for region in world.regions:
        region_id = str(region["id"])
        current_presence = world.faction_presence.setdefault(region_id, [])
        ranked = sorted(
            (
                (
                    next(score for score, candidate_region_id in lineage_candidates[faction.species_id] if candidate_region_id == region_id),
                    faction,
                )
                for faction in world.factions
            ),
            key=lambda item: (-item[0], item[1].id),
        )[:3]
        for score, faction in ranked:
            if any(item["faction_id"] == faction.id for item in current_presence):
                continue
            if score < 0.55:
                continue
            current_presence.append(
                {
                    "faction_id": faction.id,
                    "species_id": faction.species_id,
                    "presence_type": "minor_enclave" if score > 0.82 else "influence",
                    "pressure": round(min(0.95, score), 3),
                }
            )
        if current_presence and "controller_faction_id" not in region:
            region["controller_faction_id"] = current_presence[0]["faction_id"]
        world.region_economy[region_id] = region_resources_to_economy(
            region,
            has_settlement=bool(region.get("settlement_id")),
        )

    world.travel_edges = build_travel_edges(world)
    world.metadata["world_graph_dimensions"] = {
        "columns": len({int(region["x"]) for region in world.regions}),
        "rows": len({int(region["y"]) for region in world.regions}),
    }
    return world


def region_grid_position(region: dict[str, object]) -> tuple[int, int]:
    return (
        int(region["x"]) // max(1, int(region["width"])),
        int(region["y"]) // max(1, int(region["height"])),
    )


def region_distance(left: dict[str, object], right: dict[str, object]) -> int:
    lx, ly = region_grid_position(left)
    rx, ry = region_grid_position(right)
    return abs(lx - rx) + abs(ly - ry)


def lineage_candidate_regions(
    world: WorldBlueprint,
    lineage: SpeciesLineage,
    template: dict[str, object],
) -> list[tuple[float, str]]:
    scored: list[tuple[float, str]] = []
    temp_mid = sum(template["temperature_range"]) / 2
    moist_mid = sum(template["moisture_range"]) / 2
    habitats = set(template.get("habitats", []))
    for region in world.regions:
        score = float(region.get("settlement_suitability", region.get("settlement_score", 0.0)))
        score += 0.32 if region["biome_id"] in habitats else -0.18
        score += max(0.0, 0.18 - abs(float(region["avg_temperature"]) - temp_mid) * 0.28)
        score += max(0.0, 0.16 - abs(float(region["avg_moisture"]) - moist_mid) * 0.22)
        if region["id"] in lineage.home_regions:
            score += 0.24
        elif region["id"] in lineage.expansion_regions:
            score += 0.12
        if region.get("river_present"):
            score += 0.06
        if region.get("water_access") == "coast":
            score += 0.05
        scored.append((round(score, 4), str(region["id"])))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return scored


def settlement_type_for_species(species_id: str) -> str:
    return {
        "dwarf": "stronghold",
        "elf": "grove",
        "dragon": "eyrie",
        "synthetic": "hub",
        "auran": "wayport",
        "mycoid": "synod",
    }.get(species_id, "city")


def focus_for_culture(culture: dict[str, object]) -> list[str]:
    return sorted(
        culture["institution_bias"].keys(),
        key=lambda key: (-culture["institution_bias"][key], key),
    )[:3]


def choose_region_with_spacing(
    world: WorldBlueprint,
    candidate_regions: list[tuple[float, str]],
    chosen_region_ids: list[str],
    min_distance: int,
    seed_label: str,
) -> dict[str, object]:
    rng = random.Random(stable_seed_from_parts(world.seed, seed_label, len(chosen_region_ids)))
    chosen_regions = [region_lookup(world, region_id) for region_id in chosen_region_ids]
    best_region = None
    best_score = None
    fallback_region = None
    fallback_score = None
    for base_score, region_id in candidate_regions:
        region = region_lookup(world, region_id)
        distance_penalty = 0.0
        nearest = None
        for other in chosen_regions:
            distance = region_distance(region, other)
            nearest = distance if nearest is None else min(nearest, distance)
            if distance < min_distance:
                distance_penalty += (min_distance - distance) * 0.18
        score = round(base_score - distance_penalty + rng.random() * 0.04, 4)
        if fallback_score is None or score > fallback_score:
            fallback_region = region
            fallback_score = score
        if nearest is None or nearest >= min_distance:
            if best_score is None or score > best_score:
                best_region = region
                best_score = score
    if best_region is not None:
        return best_region
    if fallback_region is not None:
        return fallback_region
    return region_lookup(world, candidate_regions[0][1])


def region_resources_to_economy(region: dict[str, object], has_settlement: bool) -> dict[str, object]:
    resources = set(region.get("resources", []))
    base_food = 24 if region["biome_id"] in {"plains", "temperate_forest", "coast"} else 12
    if "fish" in resources or "salt" in resources:
        base_food += 8
    ore = 24 if "ore" in resources else 8
    wood = 24 if {"timber", "herbs", "amber"} & resources else 10
    gold = int(16 + float(region.get("settlement_score", 0.0)) * 18 + (8 if has_settlement else 0))
    return {
        "resources": {
            "food": int(base_food + float(region.get("vegetation_density", 0.0)) * 12),
            "ore": ore,
            "wood": wood,
            "gold": gold,
        },
        "prosperity": round(42 + float(region.get("settlement_suitability", 0.0)) * 28 + (6 if has_settlement else 0), 3),
    }


def build_travel_edges(world: WorldBlueprint) -> list[dict[str, object]]:
    nodes = list(world.settlement_nodes)
    if len(nodes) < 2:
        return []
    positions = {
        str(node["id"]): tuple(int(value) for value in node.get("grid_position", [0, 0]))
        for node in nodes
    }
    node_by_id = {str(node["id"]): node for node in nodes}
    seen_pairs: set[tuple[str, str]] = set()
    edges: list[dict[str, object]] = []

    def distance(left_id: str, right_id: str) -> int:
        lx, ly = positions[left_id]
        rx, ry = positions[right_id]
        return abs(lx - rx) + abs(ly - ry)

    visited = {str(nodes[0]["id"])}
    unvisited = {str(node["id"]) for node in nodes[1:]}
    while unvisited:
        best: tuple[int, str, str] | None = None
        for left_id in visited:
            for right_id in unvisited:
                candidate = (distance(left_id, right_id), left_id, right_id)
                if best is None or candidate < best:
                    best = candidate
        assert best is not None
        _, left_id, right_id = best
        pair = tuple(sorted((left_id, right_id)))
        seen_pairs.add(pair)
        left_node = node_by_id[left_id]
        right_node = node_by_id[right_id]
        edges.append(
            {
                "id": f"edge_{left_id}_{right_id}",
                "from_settlement_id": left_id,
                "to_settlement_id": right_id,
                "from_region_id": left_node["region_id"],
                "to_region_id": right_node["region_id"],
                "travel_hours": max(2, distance(left_id, right_id) * 2),
            }
        )
        visited.add(right_id)
        unvisited.remove(right_id)

    for node in nodes:
        node_id = str(node["id"])
        neighbors = sorted(
            (
                (distance(node_id, str(other["id"])), str(other["id"]))
                for other in nodes
                if str(other["id"]) != node_id
            ),
            key=lambda item: (item[0], item[1]),
        )[:2]
        for dist, other_id in neighbors:
            pair = tuple(sorted((node_id, other_id)))
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            other_node = node_by_id[other_id]
            edges.append(
                {
                    "id": f"edge_{node_id}_{other_id}",
                    "from_settlement_id": node_id,
                    "to_settlement_id": other_id,
                    "from_region_id": node["region_id"],
                    "to_region_id": other_node["region_id"],
                    "travel_hours": max(2, dist * 2),
                }
            )
    edges.sort(key=lambda item: (item["from_region_id"], item["to_region_id"], item["id"]))
    return edges


from .models import FactionSeed  # imported late to keep type section compact

__all__ = ["adapt_species", "seed_civilizations", "seed_species"]
