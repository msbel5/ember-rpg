# PRD: Combat Resolution System V1
**Project:** Ember RPG
**Phase:** 1
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-04-01
**Status:** Draft

---

## 1. Purpose

Defines the complete melee combat pipeline that synthesizes GemRB's d20 attack/defense math (THAC0/BAB → AC → damage) with Dwarf Fortress's tissue-layer physics (material shear/impact → wound generation → pain → incapacitation). The current `resolve_strike()` in `combat.py` auto-hits — this PRD adds the full attack roll, defense, critical hits, backstab, pain cascade, blood loss, morale, and multi-attack scheduling that make combat a real system.

**Synthesis:** GemRB M02 (THAC0/BAB attack rolls) + GemRB M03 (AC defense) + GemRB M04 (saving throws) + DF M01 (tissue penetration, material physics) + DF M03 (pain, incapacitation, death) into one deterministic pipeline.

## 2. Scope

### In scope
- Attack roll: d20 + BAB + STR/DEX modifiers + weapon proficiency + situational bonuses
- Defense AC: base 10 + armor bonus + DEX bonus + shield bonus + size modifier + deflection
- Hit determination: attack_roll >= target_ac
- Critical hits: natural 20 threatens, confirm roll, multiplied damage
- Backstab: rogue-style multiplier when flanking or unaware target
- Body part targeting: weighted random or called shot with penalty
- Armor coverage check: per-part coverage roll (existing `_resolve_armor` preserved)
- Damage calculation: weapon die + STR mod + quality + material physics (existing force model preserved)
- Wound creation: tissue-layer penetration from existing `_build_wound` preserved
- Pain accumulation: wound pain → actor total pain → threshold effects
- Incapacitation cascade: pain_stunned → pain_unconscious → pain_shock_death
- Blood loss: cumulative bleeding → unconscious → death
- Morale check: after first wound, after ally death, after 50% HP loss
- Attacks per round: BAB-based extra attacks, dual-wield, haste
- Saving throws: integration with Effect System (fortitude/reflex/will)

### Out of scope
- Ranged combat (future PRD)
- Spell-based attacks (uses Effect System + future Spell PRD)
- Initiative and turn ordering (future encounter management PRD)
- Stealth/detection for backstab eligibility (future PRD)
- Monster-specific attack patterns
- Formation and positioning system

## 3. Reference Mechanism Coverage

| Source | Mechanism | Coverage | Notes |
|--------|-----------|----------|-------|
| GemRB M02 | Combat (THAC0/BAB) | Full | BAB progression, proficiency bonuses, multiple attacks |
| GemRB M03 | Armor Class | Full | AC formula, armor/shield/dex/deflection components |
| GemRB M04 | Saving Throws | Via Effect System | Saves resolved through `PRD_effect_system_v1.md` |
| DF M01 | Combat (tissue physics) | Preserved | Material shear/impact yield, layer penetration already in combat.py |
| DF M01 | Pain/Incapacitation | Full | Pain thresholds, unconscious, shock death |
| DF M03 | Stress (combat stress) | Partial | Morale checks, witness-death stress |
| DF M17 | Wear/Degradation | Preserved | Armor wear from existing `_resolve_armor` |

## 4. Functional Requirements (FR)

**FR-01 (Attack Roll):** The attack roll formula is `d20 + BAB + ability_mod + proficiency_bonus + effect_bonuses`. BAB is derived from actor level and class. Ability modifier is `(STR - 10) // 2` for melee, `(DEX - 10) // 2` for finesse/ranged. Proficiency bonus is +0 (untrained), +1 (trained), +2 (proficient), +3 (expert), +4 (master).

**FR-02 (Defense AC):** Target AC is `10 + armor_bonus + shield_bonus + dex_bonus + size_mod + deflection + effect_bonuses`. `dex_bonus = min((DEX - 10) // 2, armor_max_dex)`. Size modifiers: tiny +2, small +1, medium 0, large -1, huge -2.

**FR-03 (Hit Determination):** An attack hits if `attack_roll >= target_ac`. Natural 1 always misses. Natural 20 always hits and threatens a critical.

**FR-04 (Critical Hits):** A natural 20 (or roll within weapon's threat range) threatens a critical. Confirmation: roll another d20 + BAB + modifiers; if `confirm_roll >= target_ac`, the critical is confirmed. Confirmed crits multiply weapon damage dice by the weapon's crit multiplier (default x2).

**FR-05 (Backstab):** When the attacker has the "backstab" ability and the target is flanked or unaware, backstab multiplier applies: `extra_damage = backstab_level * weapon_base_dice`. Backstab level scales 1-5 based on rogue/thief level.

**FR-06 (Body Part Targeting):** Default: weighted random selection by part `relative_size` (existing `_choose_hit_part`). Called shot: attacker specifies a part, attack roll takes -4 penalty.

**FR-07 (Armor Check):** Per-part armor coverage check using existing `_resolve_armor`. Coverage percentage roll determines if armor engages. Material-based absorption reduces attack force.

**FR-08 (Damage Calculation):** Damage uses the existing force model: `attack_force = f(base_damage, stat_bonus, melee_skill, weapon_quality, material, velocity)`. This force is then reduced by armor absorption. Effective HP damage = `max(1, remaining_force / 55)` (existing formula preserved).

**FR-09 (Wound Creation):** Wounds created by existing `_build_wound` with tissue-layer penetration. Layer thresholds based on material shear/impact yield. Wound records include: bleeding, pain, open_wound, fracture, crippled, vital flags, layer_hits.

**FR-10 (Pain Accumulation):** Each wound contributes `pain = max(1, effective_damage * 2)` (existing). Actor total pain = sum of all wound pain values. PainState thresholds from `PRD_actor_kernel_v1`:
- `pain >= 0.5 * max_pain`: stunned condition, -2 to all rolls
- `pain >= 0.8 * max_pain`: unconscious, actor drops to ground, cannot act
- `pain >= 1.2 * max_pain`: death from pain shock
- Willpower modifier reduces effective pain: `effective_pain = total_pain * (1 - willpower_mod)`
- Toughness modifier increases max_pain threshold: `max_pain = base_max * (1 + toughness_mod)`

**FR-11 (Incapacitation Cascade):** When pain/blood loss/vital destruction causes incapacitation:
1. Stunned: actor can only defend (no attacks), movement halved
2. Unconscious: actor drops prone, cannot act, drops held items
3. Dead: actor is removed from combat, death event emitted for M03 stress

**FR-12 (Blood Loss):** Each tick: `actor.blood_count -= sum(wound.bleeding for wound in active_wounds)`. Thresholds:
- `blood_count <= max_blood * 0.7`: dizzy condition (-1 to rolls)
- `blood_count <= max_blood * 0.5`: unconscious
- `blood_count <= max_blood * 0.0`: death from blood loss

**FR-13 (Morale Check):** Morale check triggered by: first wound received, ally death witnessed, HP below 50%, outnumbered 2:1. Formula: `d20 + morale_bonus >= morale_dc`. Failure: actor attempts to flee. Morale_dc: 10 (minor), 15 (serious), 20 (dire). Morale_bonus: `(WIS - 10) // 2 + leadership_bonus + trait_bonus`.

**FR-14 (Attacks Per Round):** Base attacks from BAB: 1 at BAB 1-5, 2 at BAB 6-10, 3 at BAB 11-15, 4 at BAB 16-20. Each extra attack takes cumulative -5 penalty. Dual-wield: one extra off-hand attack at -4 (-2 with light weapon). Haste: one extra attack at full BAB (from effect system).

## 5. Data Structures

```python
@dataclass
class AttackRoll:
    """Result of computing an attack roll."""
    d20_natural: int            # The raw d20 result
    bab: int                    # Base Attack Bonus
    ability_mod: int            # STR or DEX modifier
    proficiency_bonus: int      # 0-4 based on training level
    effect_bonuses: int         # From active effects (via Effect System)
    situational: int            # Called shot penalty, flanking bonus, etc.
    total: int                  # Sum of all components
    is_natural_one: bool        # Auto-miss
    is_natural_twenty: bool     # Auto-hit + threatens crit

    def to_dict(self) -> dict[str, Any]: ...


@dataclass
class DefenseProfile:
    """Target's AC breakdown."""
    base: int = 10
    armor_bonus: int = 0
    shield_bonus: int = 0
    dex_bonus: int = 0
    size_mod: int = 0
    deflection: int = 0
    effect_bonuses: int = 0
    total: int = 10             # Sum of all components

    def to_dict(self) -> dict[str, Any]: ...


@dataclass
class PainState:
    """Pain accumulation and threshold tracking per actor."""
    current_pain: float = 0.0   # Total accumulated pain from wounds
    base_max_pain: float = 100.0
    willpower_modifier: float = 0.0   # Reduces effective pain
    toughness_modifier: float = 0.0   # Increases max_pain threshold

    @property
    def max_pain(self) -> float:
        return self.base_max_pain * (1.0 + self.toughness_modifier)

    @property
    def effective_pain(self) -> float:
        return self.current_pain * (1.0 - self.willpower_modifier)

    @property
    def pain_ratio(self) -> float:
        mp = self.max_pain
        return self.effective_pain / mp if mp > 0 else 0.0

    @property
    def is_stunned(self) -> bool:
        return self.pain_ratio >= 0.5

    @property
    def is_unconscious(self) -> bool:
        return self.pain_ratio >= 0.8

    @property
    def is_dead_from_shock(self) -> bool:
        return self.pain_ratio >= 1.2

    def add_pain(self, amount: float) -> None:
        self.current_pain += max(0, amount)

    def to_dict(self) -> dict[str, Any]: ...
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PainState": ...


@dataclass
class BloodState:
    """Blood level tracking per actor."""
    blood_count: int = 5000     # Current blood in arbitrary units
    max_blood: int = 5000

    @property
    def is_dizzy(self) -> bool:
        return self.blood_count <= self.max_blood * 0.7

    @property
    def is_unconscious(self) -> bool:
        return self.blood_count <= self.max_blood * 0.5

    @property
    def is_dead(self) -> bool:
        return self.blood_count <= 0

    def drain(self, amount: int) -> None:
        self.blood_count = max(0, self.blood_count - amount)

    def to_dict(self) -> dict[str, Any]: ...
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BloodState": ...


@dataclass
class MoraleState:
    """Morale tracking per actor in combat."""
    base_morale: int = 10       # WIS-based
    leadership_bonus: int = 0
    trait_bonus: int = 0
    fleeing: bool = False
    checks_failed: int = 0

    @property
    def morale_bonus(self) -> int:
        return self.base_morale + self.leadership_bonus + self.trait_bonus

    def to_dict(self) -> dict[str, Any]: ...
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MoraleState": ...


@dataclass
class RoundAttackSchedule:
    """Computed attacks for one actor in a combat round."""
    attacks: list[dict]  # [{attack_index, bab_for_attack, is_offhand, is_haste}]

    def to_dict(self) -> dict[str, Any]: ...


@dataclass
class CombatResult:
    """Full result of resolving one attack in the pipeline."""
    attack_roll: AttackRoll
    defense: DefenseProfile
    hit: bool
    critical_threatened: bool = False
    critical_confirmed: bool = False
    backstab_applied: bool = False
    backstab_multiplier: int = 1
    strike_resolution: StrikeResolution | None = None  # From existing resolve_strike
    pain_state_after: PainState | None = None
    blood_state_after: BloodState | None = None
    morale_check: dict | None = None  # {triggered, dc, roll, passed}
    incapacitation: str | None = None  # None, "stunned", "unconscious", "dead"
    events: list[dict] = field(default_factory=list)  # death, unconscious, flee, etc.

    def to_dict(self) -> dict[str, Any]: ...
```

## 6. Public API

```python
def compute_attack_roll(
    attacker: ActorRecord,
    *,
    weapon: ItemStack | None = None,
    d20_roll: int | None = None,
    rng: Random | None = None,
    called_shot: str | None = None,
    flanking: bool = False,
) -> AttackRoll:
    """
    Compute the full attack roll for an attacker.
    Preconditions: attacker has stats and skills.
    Postconditions: returns AttackRoll with all components broken down.
    """


def compute_defense_ac(
    defender: ActorRecord,
    *,
    flat_footed: bool = False,    # Loses DEX bonus
    touch_attack: bool = False,   # Ignores armor and shield
) -> DefenseProfile:
    """
    Compute the target's AC with all components.
    Preconditions: defender has stats and equipment.
    Postconditions: returns DefenseProfile.
    """


def resolve_attack(
    attacker: ActorRecord,
    defender: ActorRecord,
    *,
    weapon: ItemStack | None = None,
    seed: int | None = None,
    called_shot: str | None = None,
    flanking: bool = False,
    backstab: bool = False,
    flat_footed: bool = False,
    raw_damage: int = 0,
) -> CombatResult:
    """
    Full attack pipeline: roll → AC → hit → crit → targeting → armor → damage → wound → pain → blood → morale.

    This wraps the existing resolve_strike() and adds the d20 layer on top.

    Steps:
    1. compute_attack_roll()
    2. compute_defense_ac()
    3. If attack_roll.total >= defense.total (or natural 20): HIT
    4. If natural 20 or in threat range: attempt critical confirmation
    5. If backstab eligible: compute multiplier
    6. Call existing resolve_strike() with hit=True, crit=confirmed, explicit_hit_part=called_shot
    7. Update PainState from wound
    8. Update BloodState
    9. Check incapacitation cascade
    10. Check morale if applicable

    Returns: CombatResult with full breakdown.
    """


def compute_attacks_per_round(
    attacker: ActorRecord,
    *,
    dual_wield: bool = False,
    off_hand_light: bool = False,
    haste: bool = False,
) -> RoundAttackSchedule:
    """
    Compute how many attacks the actor gets this round.
    BAB 1-5: 1 attack. BAB 6-10: 2 attacks. BAB 11-15: 3. BAB 16-20: 4.
    Each extra attack at cumulative -5 BAB.
    Dual-wield adds off-hand at -4 (or -2 if light).
    Haste adds one attack at full BAB.
    """


def resolve_combat_round(
    attacker: ActorRecord,
    defender: ActorRecord,
    *,
    weapon: ItemStack | None = None,
    off_hand_weapon: ItemStack | None = None,
    seed: int | None = None,
    flanking: bool = False,
    backstab_first_only: bool = False,
    flat_footed: bool = False,
) -> list[CombatResult]:
    """
    Resolve all attacks in a round for one attacker.
    Stops early if defender becomes incapacitated.
    Returns: list of CombatResult, one per attack attempted.
    """


def check_morale(
    actor: ActorRecord,
    morale_state: MoraleState,
    trigger: str,   # "first_wound" | "ally_death" | "hp_below_50" | "outnumbered"
    d20_roll: int | None = None,
    rng: Random | None = None,
) -> dict:
    """
    Perform a morale check.
    DC: first_wound=10, ally_death=15, hp_below_50=15, outnumbered=20.
    Returns: {triggered: bool, dc: int, roll: int, total: int, passed: bool}
    """


def tick_blood_loss(
    actor: ActorRecord,
    blood_state: BloodState,
) -> dict:
    """
    Apply one tick of blood loss from all active bleeding wounds.
    Returns: {drained: int, new_blood: int, unconscious: bool, dead: bool}
    """


def tick_pain(
    actor: ActorRecord,
    pain_state: PainState,
) -> dict:
    """
    Recalculate pain state from all active wounds.
    Returns: {total_pain: float, pain_ratio: float, stunned: bool, unconscious: bool, dead: bool}
    """
```

## 7. Acceptance Criteria (AC)

AC-01 [FR-01]: Given attacker with STR=16 (+3), BAB=5, proficiency=2, when `compute_attack_roll(d20_roll=12)` is called, then `total = 12 + 5 + 3 + 2 = 22`.

AC-02 [FR-02]: Given defender with DEX=14 (+2), chain mail (+5 armor, max_dex=2), shield (+2), when `compute_defense_ac()` is called, then `total = 10 + 5 + 2 + 2 = 19`.

AC-03 [FR-03]: Given attack_roll total=18 vs target_ac=19, when hit is determined, then attack misses.

AC-04 [FR-03]: Given d20 natural=1 with total=25 vs target_ac=15, when hit is determined, then attack misses (natural 1 auto-miss).

AC-05 [FR-03]: Given d20 natural=20 vs target_ac=30, when hit is determined, then attack hits (natural 20 auto-hit).

AC-06 [FR-04]: Given natural 20 hit with BAB=6, when confirmation roll is d20=14 (total=20) vs AC=19, then critical is confirmed (20 >= 19). Damage dice are doubled.

AC-07 [FR-04]: Given natural 20 hit, when confirmation roll total=14 vs AC=19, then critical is NOT confirmed. Normal damage applies.

AC-08 [FR-05]: Given attacker with backstab_level=3 and weapon_base_dice=6, when backstab is applied, then extra_damage = 3 * 6 = 18 added to base damage.

AC-09 [FR-06]: Given a called shot to "head" (penalty -4), when attack_roll is computed, then `situational = -4`.

AC-10 [FR-10]: Given wounds totaling 80 pain on an actor with base_max_pain=100 and willpower_modifier=0, when pain_ratio is computed, then ratio = 0.8 and `is_unconscious = True`.

AC-11 [FR-10]: Given wounds totaling 80 pain with willpower_modifier=0.2, when effective pain is computed, then effective = 80 * 0.8 = 64, ratio = 0.64, `is_stunned = True` but `is_unconscious = False`.

AC-12 [FR-11]: Given an actor becomes unconscious from pain, then they drop prone, drop held items, and cannot act.

AC-13 [FR-12]: Given blood_count=2500 and max_blood=5000, when blood state is checked, then `is_unconscious = True` (2500 <= 2500).

AC-14 [FR-12]: Given blood_count=0, when checked, then `is_dead = True`.

AC-15 [FR-13]: Given trigger="ally_death" (DC=15), actor morale_bonus=+4, d20=10, then total=14 < 15, morale check fails, actor flees.

AC-16 [FR-13]: Given same scenario with d20=12, total=16 >= 15, morale check passes.

AC-17 [FR-14]: Given BAB=11, when `compute_attacks_per_round()` is called, then 3 attacks at BAB +11/+6/+1.

AC-18 [FR-14]: Given BAB=6, dual_wield=True, off_hand_light=True, then 3 attacks: main +6, main +1, off-hand +4.

AC-19 [FR-14]: Given BAB=6, haste=True, then 3 attacks: haste +6, main +6, main +1.

AC-20 [FR-08, FR-09]: Given an attack that hits, when damage is resolved, the existing `resolve_strike()` force model is used — material physics, quality multipliers, and tissue-layer penetration are preserved from `combat.py`.

AC-21 [FR-02]: Given flat_footed=True, when AC is computed, then DEX bonus is excluded.

AC-22 [FR-02]: Given touch_attack=True, when AC is computed, then armor and shield bonuses are excluded.

## 8. Performance Requirements

- `compute_attack_roll`: < 0.05 ms
- `compute_defense_ac`: < 0.05 ms
- `resolve_attack` (full pipeline): < 1 ms per attack
- `resolve_combat_round` for 4-attack round: < 5 ms
- 20-actor melee (10v10, one round): < 100 ms
- All calculations deterministic given same seed

## 9. Error Handling

- Unknown damage_type: raise `ValueError`
- Missing body_state on defender: return miss result (cannot resolve physical damage)
- BAB < 0: clamp to 0
- Negative d20_roll (shouldn't happen): clamp to 1
- Called shot to non-existent body part: raise `ValueError`
- Actor with no stats dict: use defaults (all 10)
- Blood_count below 0: clamp to 0
- Pain below 0: clamp to 0

## 10. Integration Points

- **Existing `combat.py`**: `resolve_strike()`, `_resolve_armor()`, `_build_wound()`, `_attack_force()` are all PRESERVED. This PRD adds the d20 attack/defense layer ON TOP.
- **Actor Kernel** (`actor.py`): `ActorRecord.stats` provides ability scores. `ActorRecord.skills` provides proficiency levels. `PainState` and `BloodState` added to ActorRecord.
- **Effect System** (`PRD_effect_system_v1.md`): `compute_effective_stat()` used for modified STR/DEX/etc. Pain and stun applied as condition effects. Haste detected via `effect_queue.has_condition("haste")`.
- **Colony Simulation**: Death events feed M03 stress (witness death → morale penalty on allies).
- **Medical System**: Wounds created here feed into medical treatment pipeline.
- **Military** (`hybrid.py`): Squad engagement uses `resolve_combat_round()`.

## 11. Test Coverage Target

- 95% line coverage for attack roll, defense AC, hit determination
- 100% branch coverage on critical hit path (threaten, confirm, fail confirm)
- Backstab at levels 1-5
- Called shot penalty applied correctly
- Pain thresholds at exactly 0.5, 0.8, 1.2 boundaries
- Blood loss at 0.7, 0.5, 0.0 boundaries
- Morale checks for all 4 triggers
- Multi-attack schedules for BAB 1, 6, 11, 16, 20
- Dual-wield and haste combinations
- Natural 1 and natural 20 edge cases
- Flat-footed and touch attack AC variants
- Integration test: full round of combat producing wounds, pain, blood loss
- Property-based test: attack_roll always between 1 and max possible
- Serialization round-trip for all dataclasses

## Changelog

- 2026-04-01: Initial creation. Synthesizes GemRB M02/M03/M04 (d20 combat math) with DF M01/M03 (tissue physics, pain cascade).
