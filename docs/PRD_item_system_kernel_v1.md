# PRD: Item System Kernel V1
**Project:** Ember RPG
**Phase:** 1
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-04-01
**Status:** Draft

---

## 1. Purpose

Defines the complete item system synthesizing GemRB M07 (IE item structure — weapon headers, usability bitmask, equipping effects, inventory slots, enchantment) with DF M17 (material-based wear, quality levels, material properties). Every item is an `ItemDef` (static template) instantiated as an `ItemInstance` (runtime, with wear/quality/material). Items have combat headers for weapons, equipping effects that integrate with the Effect System, and material physics that integrate with the Combat and Wear systems.

## 2. Scope

### In scope
- `ItemDef`: static item template (type, requirements, economics, combat_headers, equip_effect_ids)
- `ItemInstance`: runtime item (def reference, material, quality, wear, identified, charges)
- Item types: weapon, armor, shield, helmet, gloves, boots, cloak, belt, ring, amulet, ammunition, potion, scroll, wand, misc
- 16 equipment slots (from GemRB): helmet, armor, shield, gloves, left_ring, right_ring, amulet, belt, boots, cloak, weapon_1-4, quiver_1-4, quick_item_1-3
- 16 inventory slots (general backpack)
- Weapon combat headers: attack_type, range, speed, THAC0_bonus, dice, damage_bonus, damage_type, on_hit_effect_ids, projectile_type
- Equipping effects: effect_def_ids applied while item is equipped (via Effect System while_equipped)
- Requirements: min_str, min_dex, min_int, min_wis, min_con, min_cha, min_level, class_usability
- Material system: material_id → MaterialDef from existing kernel, affects damage/armor/weight
- Quality system: 6 levels (0=base through 5=masterwork) with multipliers from existing QUALITY_MULTIPLIERS
- Wear/degradation: wear accumulates from combat, item breaks at max_wear
- Identification: unidentified items show partial info, lore check to identify
- Weight: affects actor encumbrance
- Stacking: ammunition and consumables stack with max_stack

### Out of scope
- Item crafting recipes (handled by Job/Reaction Kernel)
- Item enchanting process (future)
- Artifact generation (handled by Strange Mood in Systems Closure)
- Visual item rendering

## 3. Functional Requirements (FR)

**FR-01 (ItemDef):** Defines item template with: item_def_id, label, item_type, item_category, weight, base_price, max_stack, enchantment_level, requirements (min stats, class usability), combat_headers (for weapons), equip_effect_ids (for all equippable), lore_to_identify, flags (two_handed, droppable, magical, cursed).

**FR-02 (ItemInstance):** Runtime item with: instance_id, item_def_id, material_id, quality (0-5), wear (current degradation), max_wear (from material), identified (bool), charges (for wands/potions), stack_count.

**FR-03 (Combat Header):** Weapon items define: attack_type (melee/ranged/launcher), range, speed_factor, thac0_bonus, dice_count, dice_sides, damage_bonus, damage_type (slashing/piercing/bludgeoning), on_hit_effect_ids, projectile_type, ammo_type (for launchers).

**FR-04 (Equipment Slots):** Actor has 16 named slots. Equipping: check requirements → remove from inventory → place in slot → activate equip effects. Unequipping: deactivate effects → place in inventory → free slot.

**FR-05 (Requirements Check):** `can_equip(actor, item_def)` returns True if actor meets all min stat requirements AND class_usability allows actor's class.

**FR-06 (Equip Effects):** When item is equipped, all effect_def_ids are applied as `timing_mode="while_equipped"` effects via Effect System. When unequipped, those effects are removed.

**FR-07 (Material/Quality):** Item physical properties derive from material: `effective_armor = base_armor * material.impact_fracture_ratio * QUALITY_MULTIPLIERS[quality]`. Item weight: `weight = base_weight * material.density_ratio`. Weapon damage: routed through existing combat.py force model.

**FR-08 (Wear):** Each combat interaction adds wear (from existing EquipmentWearUpdate). When `wear >= max_wear`, item is "broken": combat bonuses halved, equip effects deactivated, repair needed. max_wear = `base_durability * material.hardness_ratio * QUALITY_MULTIPLIERS[quality]`.

**FR-09 (Identification):** Unidentified items show item_type and generic description only. `identify(actor, item)`: if `actor.skills.get("lore", 0) >= item_def.lore_to_identify`, item becomes identified. Alternatively, Identify spell sets identified=True.

**FR-10 (Stacking):** Items with `max_stack > 1` stack in inventory. Same item_def_id + same material_id + same quality = can stack up to max_stack.

**FR-11 (Use Item):** Consumables (potions, scrolls, wands): using applies the item's effect_def_ids to the user/target. Charges decrement. At 0 charges: item is destroyed (potion/scroll) or becomes inert (wand).

**FR-12 (Serialization):** ItemDef, ItemInstance, and full inventory round-trip via to_dict()/from_dict().

## 4. Data Structures

```python
@dataclass
class CombatHeader:
    attack_type: str         # "melee" | "ranged" | "launcher"
    range: int               # Feet (0 for melee)
    speed_factor: int        # Lower = faster
    thac0_bonus: int = 0
    dice_count: int = 1
    dice_sides: int = 6
    damage_bonus: int = 0
    damage_type: str = "bludgeoning"
    on_hit_effect_ids: list[str] = field(default_factory=list)
    projectile_type: str = "none"
    ammo_type: str = ""      # "arrow" | "bolt" | "bullet" for launchers

    def to_dict(self) -> dict[str, Any]: ...
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CombatHeader": ...


@dataclass
class ItemRequirements:
    min_str: int = 0
    min_dex: int = 0
    min_int: int = 0
    min_wis: int = 0
    min_con: int = 0
    min_cha: int = 0
    min_level: int = 0
    class_usability: list[str] = field(default_factory=list)  # Empty = all classes

    def met_by(self, actor: "ActorRecord") -> tuple[bool, list[str]]:
        """Returns (meets_all, list_of_failures)."""
        ...

    def to_dict(self) -> dict[str, Any]: ...
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ItemRequirements": ...


@dataclass
class ItemDef:
    item_def_id: str
    label: str
    item_type: str           # "weapon" | "armor" | "shield" | ... | "misc"
    item_category: str       # "sword" | "axe" | "chainmail" | "potion_healing" | etc.
    weight: int              # Base weight (lbs × 10)
    base_price: int          # Gold
    max_stack: int = 1
    enchantment: int = 0     # +1, +2, etc.
    requirements: ItemRequirements = field(default_factory=ItemRequirements)
    combat_headers: list[CombatHeader] = field(default_factory=list)
    equip_effect_ids: list[str] = field(default_factory=list)
    use_effect_ids: list[str] = field(default_factory=list)   # For consumables
    lore_to_identify: int = 0
    base_durability: int = 100
    flags: list[str] = field(default_factory=list)  # ["two_handed", "magical", "cursed", "droppable"]
    description: str = ""
    identified_description: str = ""

    def to_dict(self) -> dict[str, Any]: ...
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ItemDef": ...


@dataclass
class ItemInstance:
    instance_id: str
    item_def_id: str
    material_id: str = "iron"
    quality: int = 0         # 0-5
    wear: int = 0
    max_wear: int = 100
    identified: bool = False
    charges: int = -1        # -1 = unlimited
    stack_count: int = 1
    equipped_slot: str | None = None

    @property
    def is_broken(self) -> bool:
        return self.wear >= self.max_wear

    def add_wear(self, amount: int) -> None:
        self.wear = min(self.max_wear, self.wear + amount)

    def to_dict(self) -> dict[str, Any]: ...
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ItemInstance": ...


EQUIPMENT_SLOTS = [
    "helmet", "armor", "shield", "gloves",
    "left_ring", "right_ring", "amulet", "belt",
    "boots", "cloak",
    "weapon_1", "weapon_2", "weapon_3", "weapon_4",
    "quiver_1", "quiver_2", "quiver_3", "quiver_4",
    "quick_item_1", "quick_item_2", "quick_item_3",
]

INVENTORY_SIZE = 16
```

## 5. Public API

```python
def can_equip(actor: ActorRecord, item_def: ItemDef) -> tuple[bool, list[str]]:
    """Check if actor meets all requirements to equip item."""

def equip_item(actor: ActorRecord, item: ItemInstance, slot: str, item_def: ItemDef) -> list[dict]:
    """Equip item to slot. Activate equip effects. Returns events."""

def unequip_item(actor: ActorRecord, slot: str) -> list[dict]:
    """Unequip from slot. Deactivate effects. Returns events."""

def use_item(actor: ActorRecord, item: ItemInstance, item_def: ItemDef, target: ActorRecord | None, rng: Random | None = None) -> dict:
    """Use consumable. Apply effects, decrement charges. Returns {effects, charges_remaining, destroyed}."""

def identify_item(actor: ActorRecord, item: ItemInstance, item_def: ItemDef) -> bool:
    """Attempt identification via lore. Returns True if identified."""

def compute_item_wear(item: ItemInstance, item_def: ItemDef, material: MaterialDef) -> int:
    """Compute max_wear from base_durability, material, quality."""

def apply_item_wear(item: ItemInstance, wear_amount: int) -> bool:
    """Add wear. Returns True if item just broke."""

def can_stack(a: ItemInstance, b: ItemInstance) -> bool:
    """Check if two item instances can stack."""

def compute_encumbrance(inventory: list[ItemInstance], item_registry: dict[str, ItemDef]) -> int:
    """Total weight of all carried items."""
```

## 6. Acceptance Criteria (AC)

AC-01 [FR-05]: Given actor STR=12 and item min_str=14, when can_equip is called, then returns (False, ["min_str: need 14 have 12"]).

AC-02 [FR-06]: Given item with equip_effect_ids=["str_bonus_2"], when equipped, then Effect System applies while_equipped effect. When unequipped, effect is removed.

AC-03 [FR-07]: Given iron material (density=1.0) and quality=3, when max_wear is computed, then max_wear = base_durability * hardness_ratio * 1.6.

AC-04 [FR-08]: Given item with wear=99 and max_wear=100, when 2 wear is added, then item is broken (wear clamped to 100).

AC-05 [FR-09]: Given item with lore_to_identify=40 and actor lore=45, when identify is called, then item.identified becomes True.

AC-06 [FR-09]: Given actor lore=35, then identification fails.

AC-07 [FR-10]: Given two ItemInstance with same item_def_id, material, quality, and max_stack=20, when can_stack is called, then returns True.

AC-08 [FR-11]: Given potion with charges=1 and use_effect_ids=["heal_20"], when used, then heal effect is applied and item is destroyed.

AC-09 [FR-03]: Given weapon with thac0_bonus=2 and damage_bonus=3, when used in combat, then attack_roll gets +2 and damage gets +3.

AC-10 [FR-12]: ItemDef and ItemInstance round-trip via to_dict()/from_dict() preserves all fields.

AC-11 [FR-04]: Given actor with sword in weapon_1, when equip_item is called for weapon_1 with axe, then sword is moved to inventory first.

AC-12 [FR-01]: Given enchantment=2 and a creature immune to non-magical weapons, the item bypasses weapon immunity.

## 7. Performance Requirements
- can_equip: < 0.05 ms
- equip_item/unequip_item: < 0.2 ms
- compute_encumbrance for 40 items: < 0.1 ms

## 8. Error Handling
- Equip to invalid slot: raise ValueError
- Equip item that doesn't fit slot type: raise ValueError
- Use non-consumable: raise ValueError
- Stack overflow beyond max_stack: raise ValueError

## 9. Integration Points
- **Effect System**: equip effects as while_equipped, use effects as instant/duration
- **Combat Resolution**: CombatHeader feeds attack_roll and damage
- **Combat Physics**: material and quality feed existing force model in combat.py
- **Job/Reaction Kernel**: crafting creates ItemInstance with quality from skill formula
- **Store/Trade**: pricing uses base_price * quality * material modifiers
- **Actor Kernel**: inventory on ActorRecord, EquipmentLoadout updated

## 10. Test Coverage Target
- All equipment slot types
- Requirements check with edge cases
- Equip/unequip effect activation/deactivation
- Wear progression and break threshold
- Identification success/failure
- Stacking logic
- Consumable use with charge depletion
- Serialization round-trip for all dataclasses
