# PRD: Effect System V1
**Project:** Ember RPG
**Phase:** 1
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-04-01
**Status:** Draft

---

## 1. Purpose

The Effect System is the unified pipeline through which ALL runtime modifications to actors flow: combat buffs, spell results, item on-equip bonuses, syndrome progression, environmental hazards, and damage-over-time. Instead of each subsystem (combat, spells, items, syndromes) implementing its own ad-hoc stat modification and condition logic, every game effect is expressed as an `EffectDef`, instantiated as an `EffectInstance`, and processed through a per-actor `EffectQueue` each world tick.

This is the SPINE of the simulation — it connects combat (M01), medical (M05), syndromes (M06), items (M17), and colony morale (M03). Without it, each system talks past the others.

**Synthesis:** Merges GemRB M06 (310 opcodes for buffs/debuffs/spells) with DF M06 (syndromes with creature/material delivery and tick-based progression) into a single Ember pipeline.

## 2. Scope

### In scope
- `EffectDef`: static definition of any game effect (stat modification, damage-over-time, condition flag, healing, transformation)
- `EffectInstance`: runtime state of an applied effect on an actor (ticks remaining, stacks, source tracking)
- `EffectQueue`: per-actor ordered collection of active effects, ticked each world step
- Saving throw resolution (d20 + save_bonus vs DC) at application time
- Timing modes: instant, duration, permanent, while_equipped, conditional
- Stacking rules: same-source refresh, cross-source stacking with max_stacks cap
- Delivery methods: direct, contact, inhaled, injected, ingested (for syndrome integration)
- Stat modification pipeline: flat, percentage, and set modifiers applied in deterministic order
- Damage-over-time: per-tick damage routed through the existing wound system
- Condition flags: setting/clearing actor state flags (stunned, invisible, berserk, charmed, etc.)
- Dispel mechanics: remove effects by category, tag, or specific effect_id
- Serialization: full round-trip to_dict / from_dict for save/load

### Out of scope
- Spell definition format (future PRD; spells reference EffectDef IDs but spell casting rules are separate)
- Item definition format (future PRD; items reference EffectDef IDs for on-equip and on-hit effects)
- Visual/audio feedback for effect application (UI layer responsibility)
- AI decision-making about when to apply effects
- Network synchronization of effect state

## 2.1 Runtime Authority Closure

The effect system is no longer a kernel-only helper. Active campaign runtime must
tick effect state in this order on every authoritative world advance and avatar
command:

1. `tick_effects(...)` on each live `ActorRecord`
2. `tick_syndromes(...)` and `spread_contagion(...)`
3. medical side-effects produced by pain, bleeding, paralysis, and viability loss
4. environmental/system consequences that reuse the same actor effect queue

Authoritative runtime surfaces:
- `frp-backend/engine/api/campaign/live_kernel.py`
- `frp-backend/engine/api/campaign/runtime.py`
- `frp-backend/engine/api/campaign/persistence.py`

Release requirement: effect and syndrome mutations must survive campaign
save/load via canonical `kernel_game_state`, `kernel_actors`, and
`kernel_systems`, and must be visible in the Godot campaign payload.

## 3. Reference Mechanism Coverage

| Source | Mechanism | Coverage | Notes |
|--------|-----------|----------|-------|
| GemRB M06 | Effect/Opcode System | Core | 310 opcodes → Ember `EffectDef` categories; timing/stacking/save semantics preserved |
| DF M06 | Syndrome/Poison | Full | Delivery methods, tick progression, resistance DC, creature interaction tags |
| GemRB M04 | Saving Throws | Full | d20 + bonus vs DC; negate-or-half semantics |
| GemRB M02 | Combat (buffs) | Partial | THAC0/damage modifiers expressed as stat_mod effects |
| DF M01 | Combat (pain/stun) | Partial | Pain accumulation and incapacitation as condition effects |
| DF M03 | Stress | Partial | Morale modifiers as stat_mod effects feeding colony pressure |

## 4. Functional Requirements (FR)

**FR-01:** `EffectDef` defines all static properties needed for any game effect, including category, modifier, timing, saving throw, delivery method, and tags.

**FR-02:** `EffectInstance` tracks the runtime state of an applied effect on a specific actor, including ticks remaining, current stacks, source, and whether the target saved.

**FR-03:** When an effect with `saving_throw_type != "none"` is applied, the system rolls `d20 + target_save_bonus` against `saving_throw_dc`. On success: condition effects are negated; stat_mod and dot effects are halved. The `saved` flag is stored on the instance.

**FR-04:** Duration-based effects (`timing_mode == "duration"`) decrement `ticks_remaining` by 1 each world tick. When `ticks_remaining` reaches 0, the effect is removed and its modifications are reverted.

**FR-05:** Stacking rules: same `effect_def_id` from same `source_id` → refresh duration without increasing stacks. Different `source_id` → add new instance up to `max_stacks`. Beyond `max_stacks` → refresh oldest instance.

**FR-06:** Stat modification effects (`category == "stat_mod"`) modify actor stats through a single pipeline. Order: (1) flat additions, (2) percentage multipliers, (3) set overrides. Formula: `effective = (base + sum(flat)) * product(1 + pct/100)`, then overridden by set if present.

**FR-07:** Damage-over-time effects (`category == "dot"`) deal `damage_per_tick` damage each world tick as a `WoundRecord` through the wound system. If `saved`, damage is halved (floor division).

**FR-08:** Condition effects (`category == "condition"`) set actor state flags (stunned, invisible, berserk, charmed, paralyzed, frightened, prone, etc.) when applied, clear when expired/dispelled. A flag remains active while ANY active instance sets it.

**FR-09:** While-equipped effects (`timing_mode == "while_equipped"`) activate on equip, deactivate on unequip. `ticks_remaining == -1` (no expiry), not ticked down.

**FR-10:** Effects from items (on-hit, on-equip) and spells use the same `EffectDef` format. Weapon on-hit: `apply_effect(target, effect_def_id, source_id=weapon.instance_id)`. Spell: `apply_effect(target, effect_def_id, source_id=spell_id)`.

**FR-11:** Dispel mechanics: `dispel_by_category(actor, category)`, `dispel_by_tag(actor, tag)`, `dispel_by_id(actor, effect_def_id)`. Dispelled effects revert immediately.

**FR-12:** `EffectQueue` supports full serialization via `to_dict()` / `from_dict()`. All active instances preserved across save/load.

**FR-13:** Delivery method filtering: effects with `delivery == "inhaled"` only apply if target has functioning lungs. Effects with `delivery == "contact"` only apply if target has exposed skin (no full armor coverage on affected part). Effects with `delivery == "injected"` require an open wound.

**FR-14:** Resistance checks for syndrome delivery: `d20 + target.stats.get(resistance_stat, 0) >= resistance_dc`. Failure means effect is applied. Success means effect is blocked entirely (distinct from saving throw which reduces rather than blocks).

## 5. Data Structures

```python
@dataclass
class EffectDef:
    """Static definition of a game effect. Loaded from data files or created by code."""
    effect_def_id: str
    label: str
    category: str  # "stat_mod" | "dot" | "condition" | "healing" | "transformation"

    # What this effect does
    target_stat: str = ""           # For stat_mod: which stat to modify
    modifier_type: str = "flat"     # "flat" | "percentage" | "set"
    modifier_value: float = 0.0     # The modification amount
    damage_per_tick: int = 0        # For dot: damage each tick
    damage_type: str = ""           # For dot: "fire", "poison", "bleed", etc.
    condition_flag: str = ""        # For condition: "stunned", "invisible", etc.
    healing_per_tick: int = 0       # For healing: HP restored each tick

    # Timing
    timing_mode: str = "duration"   # "instant" | "duration" | "permanent" | "while_equipped" | "conditional"
    base_duration_ticks: int = 0    # 0 for instant/permanent, -1 for while_equipped

    # Stacking
    max_stacks: int = 1             # Max instances from different sources

    # Saving throw
    saving_throw_type: str = "none" # "none" | "fortitude" | "reflex" | "will"
    saving_throw_dc: int = 0        # DC for the save

    # Delivery (for syndrome integration)
    delivery: str = "direct"        # "direct" | "contact" | "inhaled" | "injected" | "ingested"
    resistance_stat: str = ""       # Stat used for resistance check (e.g. "constitution")
    resistance_dc: int = 0          # DC for resistance check (0 = no resistance check)

    # Metadata
    tags: list[str] = field(default_factory=list)  # ["magic", "fire", "poison", "curse", etc.]
    source_type: str = ""           # "spell" | "item" | "syndrome" | "environment" | "combat"
    dispellable: bool = True

    def to_dict(self) -> dict[str, Any]: ...
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EffectDef": ...


@dataclass
class EffectInstance:
    """Runtime state of an applied effect on a specific actor."""
    instance_id: str
    effect_def_id: str
    effect_def: EffectDef          # Cached reference to the definition
    source_id: str                  # Who/what applied this (actor_id, item_id, spell_id)
    target_id: str                  # Actor this is applied to

    ticks_remaining: int = 0        # -1 for permanent/while_equipped
    current_stacks: int = 1
    saved: bool = False             # True if target passed saving throw (effect halved)

    tick_applied: int = 0           # World tick when this was applied

    def is_expired(self) -> bool:
        if self.ticks_remaining == -1:
            return False  # permanent or while_equipped
        return self.ticks_remaining <= 0

    def tick(self) -> None:
        """Advance one tick. Decrements duration if applicable."""
        if self.ticks_remaining > 0:
            self.ticks_remaining -= 1

    def effective_modifier_value(self) -> float:
        """Return modifier value, halved if saved."""
        if self.saved and self.effect_def.category in ("stat_mod", "dot"):
            return self.effect_def.modifier_value / 2.0
        return self.effect_def.modifier_value

    def effective_damage_per_tick(self) -> int:
        """Return DoT damage, halved if saved."""
        if self.saved:
            return self.effect_def.damage_per_tick // 2
        return self.effect_def.damage_per_tick

    def to_dict(self) -> dict[str, Any]: ...
    @classmethod
    def from_dict(cls, data: dict[str, Any], registry: dict[str, EffectDef]) -> "EffectInstance": ...


@dataclass
class EffectQueue:
    """Per-actor ordered collection of active effects."""
    actor_id: str
    instances: list[EffectInstance] = field(default_factory=list)

    # Computed cache: active condition flags
    _active_conditions: set[str] = field(default_factory=set, repr=False)

    def add(self, instance: EffectInstance) -> None:
        """Add an effect instance, respecting stacking rules (FR-05)."""
        ...

    def remove(self, instance_id: str) -> None:
        """Remove a specific effect instance and revert its modifications."""
        ...

    def tick_all(self, actor: "ActorRecord") -> list[dict]:
        """Tick all effects. Returns list of events (damage dealt, conditions applied/removed, effects expired)."""
        ...

    def compute_stat_modifier(self, stat_name: str) -> tuple[float, float, float | None]:
        """Return (flat_total, pct_total, set_override) for a stat across all active effects."""
        ...

    def has_condition(self, flag: str) -> bool:
        """Check if any active effect sets this condition flag."""
        return flag in self._active_conditions

    def active_conditions(self) -> set[str]:
        """Return set of all active condition flags."""
        return set(self._active_conditions)

    def dispel_by_category(self, category: str) -> list[EffectInstance]:
        """Remove all effects matching category. Returns removed instances."""
        ...

    def dispel_by_tag(self, tag: str) -> list[EffectInstance]:
        """Remove all effects with matching tag. Returns removed instances."""
        ...

    def dispel_by_id(self, effect_def_id: str) -> list[EffectInstance]:
        """Remove all instances of a specific effect definition. Returns removed instances."""
        ...

    def to_dict(self) -> dict[str, Any]: ...
    @classmethod
    def from_dict(cls, data: dict[str, Any], registry: dict[str, EffectDef]) -> "EffectQueue": ...
```

### Saving Throw Formula

```python
def resolve_saving_throw(
    target: ActorRecord,
    save_type: str,       # "fortitude" | "reflex" | "will"
    dc: int,
    d20_roll: int,        # Pre-rolled or from RNG
) -> bool:
    """
    Returns True if the target PASSES the save.
    Formula: d20_roll + save_bonus >= dc

    Save bonuses derived from stats:
    - fortitude: (CON - 10) // 2 + class_bonus
    - reflex: (DEX - 10) // 2 + class_bonus
    - will: (WIS - 10) // 2 + class_bonus

    Natural 1 always fails. Natural 20 always passes.
    """
```

### Stat Modification Pipeline

```
Given an actor with base STR = 14 and these active effects:
  Effect A: stat_mod, target=STR, flat +2
  Effect B: stat_mod, target=STR, flat +3
  Effect C: stat_mod, target=STR, pct +25
  Effect D: stat_mod, target=STR, set 20

Pipeline:
  Step 1 (flat):  14 + 2 + 3 = 19
  Step 2 (pct):   19 * (1 + 0.25) = 23.75 → 23
  Step 3 (set):   20 (override)

Result: effective STR = 20
```

### Delivery Method Checks

```python
DELIVERY_REQUIREMENTS = {
    "direct": None,                    # Always applies
    "contact": "exposed_skin",         # Target must have exposed skin
    "inhaled": "functioning_lungs",    # Target must breathe
    "injected": "open_wound",          # Target must have an open wound
    "ingested": "functioning_stomach", # Target must have eaten/drunk
}
```

## 6. Public API

```python
def apply_effect(
    target: ActorRecord,
    effect_def: EffectDef,
    source_id: str,
    *,
    current_tick: int = 0,
    d20_roll: int | None = None,     # If None, rolled from RNG
    rng: Random | None = None,
) -> tuple[bool, EffectInstance | None]:
    """
    Apply an effect to a target actor.

    Steps:
    1. Check delivery requirements (FR-13)
    2. Roll resistance check if resistance_dc > 0 (FR-14)
    3. Roll saving throw if saving_throw_type != "none" (FR-03)
    4. Create EffectInstance
    5. Add to actor's EffectQueue respecting stacking (FR-05)

    Returns: (applied: bool, instance or None)
    """


def tick_effects(actor: ActorRecord, current_tick: int) -> list[dict]:
    """
    Tick all effects on an actor for one world step.

    For each active effect:
    - stat_mod: recalculate stat modifiers
    - dot: apply damage as WoundRecord
    - condition: verify flags
    - healing: restore HP
    - duration: decrement ticks_remaining, remove if expired

    Returns: list of events [{type, effect_id, detail}]
    """


def compute_effective_stat(actor: ActorRecord, stat_name: str) -> int:
    """
    Compute the effective value of a stat after all active effects.
    Pipeline: base + flat → * pct → set override (FR-06)
    """


def dispel_effects(
    actor: ActorRecord,
    *,
    category: str | None = None,
    tag: str | None = None,
    effect_def_id: str | None = None,
) -> list[EffectInstance]:
    """
    Remove effects from an actor by filter (FR-11).
    Exactly one of category/tag/effect_def_id must be non-None.
    Returns removed instances.
    """


def resolve_saving_throw(
    target: ActorRecord,
    save_type: str,
    dc: int,
    d20_roll: int,
) -> bool:
    """
    Returns True if target passes the save.
    d20 + save_bonus >= dc. Natural 1 fails, natural 20 passes.
    """


def check_delivery_requirements(
    target: ActorRecord,
    delivery: str,
) -> bool:
    """
    Check if the target meets delivery method requirements (FR-13).
    Returns True if effect can be delivered.
    """


def check_resistance(
    target: ActorRecord,
    resistance_stat: str,
    resistance_dc: int,
    d20_roll: int,
) -> bool:
    """
    Check if target resists a syndrome/effect entirely (FR-14).
    d20 + stat_bonus >= resistance_dc → resisted (returns True = blocked).
    """
```

## 7. Acceptance Criteria (AC)

AC-01 [FR-01]: Given an `EffectDef` with `category="stat_mod"`, `target_stat="STR"`, `modifier_type="flat"`, `modifier_value=4`, when serialized via `to_dict()` and restored via `from_dict()`, then all fields round-trip without loss.

AC-02 [FR-03]: Given a target with `will` save bonus +3, when an effect with `saving_throw_type="will"`, `saving_throw_dc=15` is applied and the d20 roll is 12 (total=15), then the save passes and the instance has `saved=True`.

AC-03 [FR-03]: Given a condition effect where the target passes the save, then the effect is NOT applied (negated). Given a stat_mod effect where the target passes the save, then the modifier is halved.

AC-04 [FR-04]: Given a duration effect with `base_duration_ticks=10` and `ticks_remaining=3`, when `tick_effects` is called 3 times, then the effect expires and is removed from the queue.

AC-05 [FR-05]: Given effect X from source A with 5 ticks remaining, when effect X is applied again from source A, then `ticks_remaining` is refreshed to `base_duration_ticks` and stacks remain at 1.

AC-06 [FR-05]: Given effect X from source A (1 stack), when effect X is applied from source B with `max_stacks=3`, then a second instance is added (2 total stacks).

AC-07 [FR-05]: Given effect X at max_stacks=2 from sources A and B, when applied from source C, then the oldest instance is refreshed (no third instance created).

AC-08 [FR-06]: Given base STR=14 with flat +2, flat +3, pct +25, set 20 effects, when `compute_effective_stat("STR")` is called, then the result is 20 (set override wins).

AC-09 [FR-06]: Given base STR=14 with flat +2, pct +50 effects (no set), when computed, then result is `int((14 + 2) * 1.5)` = 24.

AC-10 [FR-07]: Given a DoT effect with `damage_per_tick=5` and `saved=False`, when ticked, then a WoundRecord with `damage_amount=5` is created on the target.

AC-11 [FR-07]: Given a DoT effect with `damage_per_tick=5` and `saved=True`, when ticked, then `damage_amount=2` (5//2).

AC-12 [FR-08]: Given two active effects both setting condition `"stunned"`, when one expires, then `has_condition("stunned")` still returns True. When both expire, returns False.

AC-13 [FR-09]: Given a while_equipped effect, when the source item is unequipped, then the effect is removed and stat modifications revert.

AC-14 [FR-11]: Given 3 active effects (2 tagged "magic", 1 tagged "poison"), when `dispel_by_tag("magic")` is called, then 2 effects are removed and the "poison" one remains.

AC-15 [FR-12]: Given an EffectQueue with 5 active instances, when `to_dict()` and `from_dict()` are called, then all 5 instances are preserved with correct ticks_remaining and saved flags.

AC-16 [FR-13]: Given a target wearing full plate (100% torso coverage), when a "contact" delivery effect targets the torso, then the effect is blocked.

AC-17 [FR-13]: Given a target with no open wounds, when an "injected" delivery effect is applied, then the effect is blocked.

AC-18 [FR-14]: Given a target with CON=16 (+3 bonus) and a syndrome with `resistance_dc=12`, when d20 roll is 9 (total=12), then resistance succeeds and the effect is blocked entirely.

AC-19 [FR-03]: Given d20 natural roll = 1, when saving throw is resolved regardless of bonus, then the save fails.

AC-20 [FR-03]: Given d20 natural roll = 20, when saving throw is resolved regardless of DC, then the save passes.

## 8. Performance Requirements
- `apply_effect`: < 0.1 ms per application
- `tick_effects` for a single actor with 20 active effects: < 1 ms
- `compute_effective_stat`: < 0.05 ms per stat
- `dispel_effects`: < 0.5 ms even with 50 active effects
- All operations deterministic given same RNG seed

## 9. Error Handling
- Unknown `category` in EffectDef: raise `ValueError`
- Unknown `saving_throw_type`: raise `ValueError`
- Unknown `delivery` method: raise `ValueError`
- `modifier_value` on a non-stat_mod effect: ignored (no error)
- `damage_per_tick` on a non-dot effect: ignored (no error)
- Missing `target_stat` on a stat_mod effect: raise `ValueError`
- Negative `ticks_remaining` after tick: clamp to 0, mark expired
- `from_dict` with unknown `effect_def_id`: raise `KeyError` with descriptive message

## 10. Integration Points

- **Actor Kernel** (`engine/kernel/actor.py`): `ActorRecord` gains an `effect_queue: EffectQueue` field. `ConditionRecord` is replaced by the effect system's condition flags.
- **Combat** (`engine/kernel/combat.py`): Attack/damage modifiers read from `compute_effective_stat()`. Pain and stun applied as condition effects after wounds.
- **Medical** (future `engine/kernel/medical.py`): Healing effects, fever from infection, treatment bonuses expressed as effects.
- **Systems Closure** (`engine/kernel/systems.py`): `SyndromeDef` maps to `EffectDef` entries with appropriate delivery methods.
- **Colony** (`engine/kernel/colony.py`): Morale modifiers (happy/sad thoughts) expressed as stat_mod effects on mood/stress.
- **Items**: On-equip bonuses and on-hit effects reference `EffectDef` IDs.

## 11. Test Coverage Target
- 95% line coverage for the effect system module
- Every category (stat_mod, dot, condition, healing) has dedicated tests
- Every timing mode (instant, duration, permanent, while_equipped) has tests
- Every delivery method has a pass/fail test
- Saving throw: natural 1, natural 20, exact DC, above DC, below DC
- Stacking: same source refresh, cross source stack, max_stacks overflow
- Stat pipeline: flat only, pct only, set only, all three combined
- Dispel: by category, by tag, by id, partial dispel
- Serialization round-trip for EffectDef, EffectInstance, EffectQueue

## Changelog

- 2026-04-01: Initial creation. Synthesizes GemRB M06 (opcodes) + DF M06 (syndromes) + GemRB M04 (saving throws).
