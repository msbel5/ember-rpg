from __future__ import annotations

from random import Random

from engine.kernel.actor import ActorRecord, BodyState, EquipmentLoadout, ItemStack, WoundRecord

from .combat_types import (
    ArmorInteraction,
    BLUNT_DAMAGE_TYPES,
    EDGE_DAMAGE_TYPES,
    EquipmentWearUpdate,
    QUALITY_MULTIPLIERS,
    material_def_from_legacy_name,
)


def choose_hit_part(body_state: BodyState, rng: Random) -> str:
    weighted_parts: list[tuple[str, int]] = []
    for part in body_state.plan.parts:
        weighted_parts.append((part.part_id, max(1, int(part.relative_size))))
    total = sum(weight for _, weight in weighted_parts)
    roll = rng.randint(1, total)
    running = 0
    for part_id, weight in weighted_parts:
        running += weight
        if roll <= running:
            return part_id
    return weighted_parts[0][0]


def damage_type_for_weapon(weapon: ItemStack | None) -> str:
    if weapon is None:
        return "bludgeoning"
    damage_type = str(weapon.payload.get("damage_type", "")).strip().lower()
    if damage_type:
        return damage_type
    item_id = str(weapon.item_def_id).lower()
    if any(token in item_id for token in ("sword", "knife", "spear", "dagger", "rapier")):
        return "slashing"
    if any(token in item_id for token in ("hammer", "club", "mace", "staff")):
        return "bludgeoning"
    return "bludgeoning"


def attack_force(
    attacker: ActorRecord,
    weapon: ItemStack | None,
    *,
    raw_damage: int,
    crit: bool,
    damage_type: str,
) -> int:
    base_damage = max(1, int(raw_damage))
    mig = int(attacker.stats.get("MIG", attacker.stats.get("strength", 10)))
    agi = int(attacker.stats.get("AGI", attacker.stats.get("agility", 10)))
    melee_skill = int(attacker.skills.get("melee", attacker.skills.get("sword", attacker.skills.get("axe", 0))))
    stat_bonus = max(0, (mig - 10) // 2)
    velocity = 100 + (agi - 10) * 3 + melee_skill * 4 + (20 if crit else 0)
    size = max(4, int(weapon.payload.get("damage", base_damage)) if weapon is not None else base_damage)
    material = material_def_from_legacy_name(weapon.material_id if weapon is not None else "bone")
    quality = QUALITY_MULTIPLIERS.get(int(weapon.quality), 1.0) if weapon is not None else 1.0
    if damage_type in EDGE_DAMAGE_TYPES:
        sharpness = int((weapon.sharpness if weapon is not None else 80) * material.max_edge / 100)
        return int((base_damage + stat_bonus + melee_skill + size) * quality * max(50, sharpness) * velocity / 850)
    density_bonus = max(1, material.density // 250)
    return int((base_damage + stat_bonus + melee_skill + density_bonus) * quality * velocity / 18)


def resolve_armor(
    equipment: EquipmentLoadout,
    hit_part_id: str,
    attack_force: int,
    rng: Random,
) -> tuple[list[ArmorInteraction], list[EquipmentWearUpdate], int]:
    interactions: list[ArmorInteraction] = []
    wear_updates: list[EquipmentWearUpdate] = []
    absorbed_total = 0
    remaining_force = attack_force
    for slot, item in equipment.covering_items(hit_part_id):
        coverage = int(item.payload.get("coverage_percentage", 100))
        roll = rng.randint(1, 100)
        engaged = roll <= max(1, coverage)
        quality = QUALITY_MULTIPLIERS.get(int(item.quality), 1.0)
        absorbed = 0
        if engaged:
            material = material_def_from_legacy_name(item.material_id or item.payload.get("material_id"))
            armor_score = max(1, int(round((material.impact_fracture / 22.0) * quality)))
            absorbed = min(max(0, remaining_force // 10), armor_score)
            remaining_force = max(0, remaining_force - absorbed)
            wear_delta = max(0, int(round(max(0, absorbed) / 8.0)))
            if wear_delta > 0:
                item.wear += wear_delta
                wear_updates.append(
                    EquipmentWearUpdate(
                        slot=slot,
                        item_instance_id=item.instance_id,
                        wear_delta=wear_delta,
                        new_wear=item.wear,
                    )
                )
        interactions.append(
            ArmorInteraction(
                slot=slot,
                item_instance_id=item.instance_id,
                item_name=str(item.payload.get("name", item.item_def_id)),
                engaged=engaged,
                absorbed=absorbed,
                coverage_roll=roll,
                quality_multiplier=quality,
            )
        )
        absorbed_total += absorbed
        if remaining_force <= 0:
            break
    return interactions, wear_updates, absorbed_total


def build_wound(
    body_state: BodyState,
    hit_part_id: str,
    *,
    damage_type: str,
    effective_damage: int,
    attack_force: int,
    source_item_id: str | None,
) -> WoundRecord | None:
    if effective_damage <= 0:
        return None
    part_def = body_state.part_def(hit_part_id)
    remaining_force = attack_force
    layer_hits: list[str] = []
    under_pressure_hit = False
    vital_hit = False
    structural_hit = False
    for layer in part_def.layers:
        threshold = layer_threshold(layer.material_id, damage_type, layer.relative_thickness)
        if remaining_force < threshold:
            break
        layer_hits.append(layer.layer_id)
        remaining_force = max(0, remaining_force - threshold)
        under_pressure_hit = under_pressure_hit or layer.under_pressure
        vital_hit = vital_hit or layer.vital or (part_def.vital and layer.layer_id in {"brain", "artery", "lungs", "organs"})
        structural_hit = structural_hit or layer.structural
    open_wound = damage_type in EDGE_DAMAGE_TYPES or effective_damage >= 4
    fracture = structural_hit and (damage_type in BLUNT_DAMAGE_TYPES or effective_damage >= max(6, part_def.max_hp // 2))
    crippled = effective_damage >= max(4, part_def.max_hp // 2)
    bleeding = 0
    if open_wound:
        bleeding = max(1, effective_damage // 3)
        if under_pressure_hit:
            bleeding += 2
    pain = max(1, effective_damage * 2)
    if vital_hit:
        pain += 2
    return WoundRecord(
        wound_id=f"wound_{hit_part_id}_{len(body_state.wounds) + 1}",
        body_part_id=hit_part_id,
        damage_type=damage_type,
        damage_amount=effective_damage,
        bleeding=bleeding,
        pain=pain,
        open_wound=open_wound,
        infected=False,
        untreated=open_wound,
        fracture=fracture,
        crippled=crippled,
        vital=part_def.vital or vital_hit,
        attack_force=attack_force,
        source_item_id=source_item_id,
        layer_hits=layer_hits,
        tags=wound_tags(part_def.part_id, fracture=fracture, vital=vital_hit, open_wound=open_wound),
    )


def layer_threshold(material_id: str, damage_type: str, thickness: int) -> int:
    material = material_def_from_legacy_name(material_id)
    reference = material.shear_yield if damage_type in EDGE_DAMAGE_TYPES else material.impact_yield
    return max(20, int(reference) * max(1, int(thickness)))


def wound_tags(part_id: str, *, fracture: bool, vital: bool, open_wound: bool) -> list[str]:
    tags: list[str] = [part_id]
    if fracture:
        tags.append("fracture")
    if vital:
        tags.append("vital")
    if open_wound:
        tags.append("open_wound")
    if "leg" in part_id:
        tags.append("mobility_risk")
    return tags


__all__ = [
    "attack_force",
    "build_wound",
    "choose_hit_part",
    "damage_type_for_weapon",
    "layer_threshold",
    "resolve_armor",
    "wound_tags",
]
