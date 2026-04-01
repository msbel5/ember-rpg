# PRD: Spell System V1
**Project:** Ember RPG
**Phase:** 2
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-04-01
**Status:** Draft

---

## 1. Purpose

Defines the spell casting pipeline synthesizing GemRB M05 (Spellbook memorization, casting time, interruption, spell failure, aura cooldown, magic resistance) with the Ember Effect System. Every spell is a `SpellDef` referencing one or more `EffectDef` IDs; casting a spell creates a `CastingAttempt` that moves through a pipeline (select → target → casting_time → interruption_check → spell_failure → aura_check → projectile_launch → effect_application → saving_throw → magic_resistance → slot_depletion). The kernel is deterministic — all rolls accept explicit RNG seeds.

## 2. Scope

### In scope
- `SpellDef`: static definition (school, level, type, casting_time, range, target_type, effect_ids, projectile_type)
- `SpellSlot` / `Spellbook`: per-actor memorized spells with slot counts per level
- Spell types: wizard (INT, learned from scrolls), priest (WIS, auto-access), innate (no memorize), sorcerer (spontaneous)
- Casting pipeline: 11-step pipeline from GemRB M05
- Interruption: damage during casting → concentration check (d20 + CON mod >= 10 + damage_taken) or auto-fail
- Spell failure: armor-based failure chance (IE_SPELLFAILUREMAGE)
- Aura cooldown: 6-second (6-tick) cooldown between casts
- Magic resistance: target's magic_resistance % chance to negate spell entirely
- Spell slots per level: derived from class tables + ability bonus
- Scroll learning: INT check to learn wizard spell, failure destroys scroll
- Integration with Effect System (spells apply EffectDef instances)
- Integration with Projectile System (spells launch projectiles)

### Out of scope
- Specific spell definitions (data files, not kernel code)
- Spell animation/VFX (UI layer)
- Wild magic / wild surge table (future)
- Psionics (future, PST-specific)

## 3. Reference Mechanism Coverage

| Source | Mechanism | Coverage | Notes |
|--------|-----------|----------|-------|
| GemRB M05 | Spell System | Full | 11-step pipeline, memorization, all spell types |
| GemRB M06 | Effect/Opcode | Via PRD_effect_system_v1 | Spells reference EffectDef IDs |
| GemRB M12 | Projectile | Via PRD_projectile_system_v1 | Spells launch projectiles |
| GemRB M04 | Saving Throws | Via PRD_effect_system_v1 | Effects handle saves |

## 4. Functional Requirements (FR)

**FR-01 (SpellDef):** A spell definition includes: spell_id, label, spell_type (wizard/priest/innate/sorcerer), school, level (1-9), casting_time (ticks), range, target_type (self/creature/point/area), hostile flag, effect_def_ids (list), projectile_type, components (verbal/somatic/material), material_cost.

**FR-02 (Spellbook):** Each actor has a `Spellbook` with: known_spells (learned spell IDs per level), memorized_slots (SpellSlot list per level), max_slots_per_level (from class table + ability bonus). Wizard: must learn then memorize. Priest: auto-access by level, must memorize. Sorcerer: knows limited spells, casts spontaneously from slots. Innate: always available, no slots.

**FR-03 (Slot Calculation):** `max_slots(level, spell_level) = class_table[level][spell_level] + ability_bonus(ability_score, spell_level)`. Wizard uses INT bonus. Priest uses WIS bonus. Sorcerer uses CHA bonus. Bonus spells: `bonus = max(0, (ability_score - 10) // 4 - spell_level + 1)` for spell_level <= (ability_score - 10) // 4.

**FR-04 (Learn Spell):** Wizard learning from scroll: `d100 <= learn_chance(INT)`. Learn chance from table: INT 9=35%, 10=40%, 12=50%, 14=60%, 16=70%, 18=85%, 19=95%, 20+=99%. Failure destroys scroll. Success adds spell to known_spells.

**FR-05 (Memorize):** Actor assigns known spells to empty slots. On rest: all memorized slots become available for casting. Sorcerer: all slots refill on rest without assignment.

**FR-06 (Casting Pipeline):** Cast attempt follows 11 steps in order:
1. SPELL_SELECT: verify spell is memorized/available
2. TARGET_SELECT: verify target is valid for spell's target_type and range
3. CASTING_TIME: spell enters casting state for casting_time ticks
4. INTERRUPTION_CHECK: if caster takes damage during casting → `d20 + CON_mod >= 10 + damage_taken` or spell fails
5. SPELL_FAILURE: if caster has spell_failure > 0 (from armor) → `d100 <= spell_failure` means spell fails
6. AURA_CHECK: if caster cast within last 6 ticks → spell fails (aura cooldown)
7. PROJECTILE_LAUNCH: create projectile with spell's effect_def_ids heading to target
8. EFFECT_APPLICATION: when projectile reaches target, apply all effects
9. SAVING_THROW: handled by Effect System per-effect
10. MAGIC_RESISTANCE: `d100 <= target.magic_resistance` → all effects negated
11. SLOT_DEPLETION: used spell slot marked as expended

**FR-07 (Interruption):** Damage during casting_time triggers concentration check. Formula: `d20 + (CON - 10) // 2 >= 10 + damage_taken`. Failure: spell is lost, slot is expended, no effect. Success: casting continues.

**FR-08 (Spell Failure):** Armor causes arcane spell failure. Light armor: 10%, medium: 20%, heavy: 40%, shield: +15%. Check: `d100 <= total_failure_chance` → spell fails, slot expended.

**FR-09 (Aura Cooldown):** Each actor tracks `last_cast_tick`. If `current_tick - last_cast_tick < 6`, spell cannot be cast. Returns error, slot NOT expended.

**FR-10 (Magic Resistance):** Before effect application, check `d100 <= target.stats.get("magic_resistance", 0)`. If passed, ALL spell effects are negated. This is distinct from saving throws (which are per-effect).

**FR-11 (Caster Level):** Spell potency scales with caster level: damage dice, duration, range may scale. Formula provided per-spell in SpellDef as `scaling_stat` and `scaling_formula`.

**FR-12 (Spell Slots Serialization):** Spellbook with all known/memorized/expended state must round-trip via to_dict()/from_dict().

## 5. Data Structures

```python
@dataclass
class SpellDef:
    spell_id: str
    label: str
    spell_type: str          # "wizard" | "priest" | "innate" | "sorcerer"
    school: str              # "abjuration" | "conjuration" | "divination" | "enchantment" | "evocation" | "illusion" | "necromancy" | "transmutation"
    level: int               # 1-9
    casting_time: int        # Ticks
    range: int               # 0=self, else feet
    target_type: str         # "self" | "creature" | "point" | "area"
    area_radius: int = 0     # For area spells, in feet
    hostile: bool = False
    effect_def_ids: list[str] = field(default_factory=list)
    projectile_type: str = "none"  # "none" | "arrow" | "fireball" | "cone" | "bouncing" | "traveling"
    components: list[str] = field(default_factory=list)  # ["verbal", "somatic", "material"]
    material_cost: dict[str, int] = field(default_factory=dict)
    scaling_stat: str = ""   # "caster_level" etc.
    scaling_formula: str = "" # e.g. "min(10, caster_level) * d6"
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]: ...
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SpellDef": ...


@dataclass
class SpellSlot:
    spell_level: int
    spell_id: str | None = None  # None = empty slot
    memorized: bool = False
    expended: bool = False

    def to_dict(self) -> dict[str, Any]: ...


@dataclass
class Spellbook:
    actor_id: str
    spell_type: str          # "wizard" | "priest" | "sorcerer" | "innate"
    known_spells: dict[int, list[str]] = field(default_factory=dict)  # level → [spell_ids]
    slots: dict[int, list[SpellSlot]] = field(default_factory=dict)   # level → [SpellSlot]
    max_slots: dict[int, int] = field(default_factory=dict)           # level → max_count

    def available_slots(self, level: int) -> int: ...
    def memorize(self, spell_id: str, level: int) -> bool: ...
    def expend_slot(self, spell_id: str, level: int) -> bool: ...
    def rest_refresh(self) -> None: ...
    def to_dict(self) -> dict[str, Any]: ...
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Spellbook": ...


@dataclass
class CastingAttempt:
    caster_id: str
    spell_def: SpellDef
    target_id: str | None = None
    target_point: tuple[int, int] | None = None
    tick_started: int = 0
    ticks_remaining: int = 0
    interrupted: bool = False
    failed: bool = False
    failure_reason: str = ""
    completed: bool = False

    def to_dict(self) -> dict[str, Any]: ...
```

## 6. Public API

```python
def compute_max_spell_slots(
    actor: ActorRecord,
    spell_type: str,
    class_table: dict,
) -> dict[int, int]:
    """Compute max slots per spell level from class table + ability bonus."""

def learn_spell(
    actor: ActorRecord,
    spellbook: Spellbook,
    spell_def: SpellDef,
    d100_roll: int,
) -> tuple[bool, str]:
    """Wizard learns spell from scroll. Returns (success, message). Failure destroys scroll."""

def begin_casting(
    caster: ActorRecord,
    spellbook: Spellbook,
    spell_def: SpellDef,
    target_id: str | None,
    target_point: tuple[int, int] | None,
    current_tick: int,
) -> tuple[bool, CastingAttempt | None, str]:
    """
    Start casting: verify slot available, target valid, aura cooldown passed.
    Returns (can_start, attempt, error_message).
    """

def tick_casting(
    attempt: CastingAttempt,
    damage_taken: int,
    d20_roll: int | None,
    d100_roll: int | None,
    caster: ActorRecord,
) -> tuple[str, CastingAttempt]:
    """
    Advance casting by one tick. Checks interruption and spell failure.
    Returns (status: "casting"|"interrupted"|"failed"|"ready", updated_attempt).
    """

def resolve_cast(
    attempt: CastingAttempt,
    caster: ActorRecord,
    target: ActorRecord | None,
    d100_roll: int,
    current_tick: int,
) -> dict:
    """
    Finalize spell: magic resistance check → launch projectile or apply effects directly.
    Returns {resisted: bool, projectile_launched: bool, effects_applied: list, slot_expended: bool}.
    """

def rest_refresh_spellbook(spellbook: Spellbook) -> None:
    """Refresh all expended slots on rest."""
```

## 7. Acceptance Criteria (AC)

AC-01 [FR-03]: Given a level 5 wizard with INT=16, when max_slots are computed, then level 1 has class_base + bonus slots.

AC-02 [FR-04]: Given INT=14 (learn_chance=60%) and d100_roll=55, when learn_spell is called, then spell is added to known_spells.

AC-03 [FR-04]: Given INT=14 and d100_roll=65, when learn_spell is called, then learning fails and scroll is consumed.

AC-04 [FR-05]: Given a wizard with 3 level-1 slots all memorized, when rest_refresh is called, then all 3 slots have expended=False.

AC-05 [FR-06]: Given a valid memorized spell and valid target, when begin_casting is called, then a CastingAttempt is returned with ticks_remaining = spell.casting_time.

AC-06 [FR-07]: Given a caster taking 8 damage during casting with CON=14 (+2), when tick_casting is called with d20_roll=15 (total 17 >= 10+8=18 → FAIL), then spell is interrupted.

AC-07 [FR-07]: Given same scenario with d20_roll=16 (total 18 >= 18), then casting continues.

AC-08 [FR-08]: Given a caster with spell_failure=20% and d100_roll=15, then spell fails.

AC-09 [FR-08]: Given spell_failure=20% and d100_roll=25, then spell succeeds.

AC-10 [FR-09]: Given last_cast_tick=100 and current_tick=103, when begin_casting is called, then it returns (False, None, "aura cooldown").

AC-11 [FR-09]: Given last_cast_tick=100 and current_tick=106, then casting can begin.

AC-12 [FR-10]: Given target with magic_resistance=40 and d100_roll=35, when resolve_cast is called, then all effects are negated (resisted=True).

AC-13 [FR-10]: Given magic_resistance=40 and d100_roll=45, then effects are applied normally.

AC-14 [FR-12]: Given a Spellbook with 3 known spells and 2 memorized slots, when to_dict()/from_dict() round-trip, then all state is preserved.

## 8. Performance Requirements
- begin_casting: < 0.1 ms
- tick_casting: < 0.05 ms
- resolve_cast: < 0.5 ms (excluding effect application)
- compute_max_spell_slots: < 0.1 ms
- All operations deterministic given same roll inputs

## 9. Error Handling
- Unknown spell_type: raise ValueError
- Casting without available slot: return (False, None, "no available slot")
- Target out of range: return (False, None, "target out of range")
- Unknown spell_id in spellbook: raise KeyError
- Sorcerer memorize call: ignore (sorcerer doesn't memorize specific slots)

## 10. Integration Points
- **Effect System** (PRD_effect_system_v1): spell effects are EffectDef instances applied via apply_effect()
- **Projectile System** (PRD_projectile_system_v1): spells with projectile_type != "none" launch projectiles
- **Actor Kernel** (PRD_actor_kernel_v1): INT/WIS/CHA for slot computation, CON for concentration, magic_resistance stat
- **Combat Resolution** (PRD_combat_resolution_v1): damage during casting triggers interruption
- **Item System** (PRD_item_system_kernel_v1): scrolls consumed on learn, armor causes spell failure

## 11. Test Coverage Target
- All 4 spell types (wizard, priest, sorcerer, innate) with memorize/cast cycle
- Learn spell success and failure at boundary INT values
- All 11 casting pipeline steps
- Interruption at exact DC boundary
- Spell failure at exact percentage boundary
- Aura cooldown at exactly 6 ticks
- Magic resistance at exact percentage boundary
- Serialization round-trip for SpellDef, SpellSlot, Spellbook, CastingAttempt
