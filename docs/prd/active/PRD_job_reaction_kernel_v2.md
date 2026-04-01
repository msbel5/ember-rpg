# PRD: Job and Reaction Kernel V2
**Project:** Ember RPG
**Phase:** 3
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-04-01
**Status:** Draft

---

## 1. Purpose
The Job and Reaction Kernel defines the typed work system that connects actors to worksites, recipes, skill growth, and deterministic production outputs. It replaces scattered crafting and workstation assumptions with explicit job records and reaction definitions that drive colony production chains, skill progression, skill rust, and room/zone assignment. This module covers DF-inspired mechanisms M02 (Skill/Learning), M04 (Job/Task Assignment), and M16 (Building/Room Assignment partial).

## 2. Scope
- **In scope:** `JobRecord` lifecycle (create, assign, tick, complete, cancel); `ReactionDef` with typed material inputs/outputs; `WorksiteRecord` binding reactions to rooms; labor assignment algorithm; job completion XP and skill leveling; skill rust mechanics; quality output formula; room/zone assignment basics (bedroom, dining, workshop).
- **Out of scope:** Full trade caravan economy; late-game industry balancing; UI job queue rendering; military squad assignment; strange mood crafting (covered by colony simulation M13).

## 2.1 Runtime Authority Closure

Jobs and reactions are logic-live only when they execute inside the authoritative
campaign runtime and feed the same save/load contract as the rest of the kernel.
Every world advance or commander action must run:

1. labor assignment on queued jobs
2. active job ticking
3. reaction completion
4. output material propagation to settlement economy and stock
5. pressure / farming follow-on updates

Authoritative runtime surfaces:
- `frp-backend/engine/api/campaign/live_kernel.py`
- `frp-backend/engine/api/campaign/runtime.py`
- `frp-backend/engine/api/campaign/persistence.py`

`JobRecord`, `ReactionDef`, and `WorksiteRecord` are not considered complete if
they only round-trip through tests; they must mutate live campaign payloads and
persist through canonical kernel save slices.

## 3. Functional Requirements (FR)

FR-01: The kernel must define a typed `JobRecord` with fields: `job_id`, `kind`, `priority`, `status`, `assignee_id`, `skill_id`, `worksite_id`, `input_tags`, `output_tags`, `completion_ticks`, `elapsed_ticks`.

FR-02: `JobRecord.status` must follow a strict state machine: `queued` -> `assigned` -> `active` -> `completed` | `cancelled`. No other transitions are valid.

FR-03: The kernel must define a typed `ReactionDef` with fields: `reaction_id`, `label`, `worksite_kind`, `input_materials` (list of `MaterialRequirement`), `output_products` (list of `ProductOutput`), `required_skill`, `base_duration_ticks`, `quality_formula`.

FR-04: The kernel must define a typed `MaterialRequirement` with fields: `tag`, `quantity`, `consumed` (bool, default True). Non-consumed inputs (e.g., anvil for smithing) are checked but not removed from stockpile.

FR-05: The kernel must define a typed `ProductOutput` with fields: `item_def_id`, `material_id`, `quantity`. The actual material may be inherited from input materials when `material_id` is `"inherit"`.

FR-06: The kernel must define a typed `WorksiteRecord` with fields: `worksite_id`, `label`, `kind`, `room_id`, `supported_jobs`, `reaction_ids`.

FR-07: The labor assignment algorithm must select workers using: (1) eligibility check (actor has required skill or skill_id is None), (2) proximity sort (closest eligible actor first), (3) skill preference (higher skill level preferred among equidistant actors).

FR-08: On job completion, the assigned actor must gain XP: `xp_gained = base_xp * (1 + mental_attr_bonus)` where `base_xp` is derived from the reaction's `base_duration_ticks` and `mental_attr_bonus` is `actor.stats.get("focus", 0) * 0.01`.

FR-09: Skill levels must follow cumulative XP thresholds: `[0, 500, 1100, 1800, 2600, 3500, 4500, 5600, 6800, 8100, 9500, 11000, 12600, 14300, 16100]` corresponding to levels 0-14. Level names: 0=Dabbling, 1=Novice, 2=Adequate, 3=Competent, 4=Skilled, 5=Proficient, 6=Talented, 7=Adept, 8=Expert, 9=Professional, 10=Accomplished, 11=Great, 12=Master, 13=High Master, 14=Grand Master, 15+=Legendary.

FR-10: Skill rust must apply when a skill is unused. Each tick a skill is not exercised, `unused_counter` increments. When `unused_counter > rust_threshold`, `rusty_level` increments by 1 and `effective_skill = base_level - rusty_level` (minimum 0). Legendary skills (level >= 15) have `rust_threshold = 500`; all others have `rust_threshold = 200`.

FR-11: Output quality must be determined by a weighted random formula: `quality = weighted_random(effective_skill)` producing quality levels 0-5 (0=ordinary, 1=well-crafted, 2=finely-crafted, 3=superior, 4=exceptional, 5=masterwork). Higher effective_skill shifts the distribution toward higher quality.

FR-12: Room/zone assignment must enforce furniture requirements: bedroom requires at least 1 bed; dining room requires at least 1 table and 1 chair; workshop requires at least 1 worksite of the appropriate kind. A room missing required furniture is flagged `"unfurnished"` and cannot fulfill its zone function.

FR-13: The kernel must support job cancellation at any stage. Cancelling an `active` job refunds unconsumed input materials to the stockpile. Consumed materials are lost.

FR-14: The kernel must extract `JobRecord`, `ReactionDef`, and `WorksiteRecord` lists from raw settlement state dictionaries via factory functions.

## 4. Data Structures

```python
@dataclass
class MaterialRequirement:
    """A single material input required by a reaction."""
    tag: str                    # Material tag to match (e.g. "ore", "fuel", "cloth")
    quantity: int               # Number of units required
    consumed: bool = True       # If False, item is checked but not removed (tool/fixture)

    def to_dict(self) -> dict[str, Any]: ...
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MaterialRequirement": ...


@dataclass
class ProductOutput:
    """A single product created by a reaction."""
    item_def_id: str            # Item definition ID for the output
    material_id: str            # Material ID; "inherit" = use input material
    quantity: int = 1           # Number of items produced

    def to_dict(self) -> dict[str, Any]: ...
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProductOutput": ...


@dataclass
class JobRecord:
    """A single unit of work to be performed by an actor at a worksite."""
    job_id: str
    kind: str                           # Job type: "forge", "brew", "construct", "haul", etc.
    priority: int                       # 1 = highest, 5 = lowest
    status: str                         # "queued" | "assigned" | "active" | "completed" | "cancelled"
    assignee_id: str | None = None      # Actor performing the job
    skill_id: str | None = None         # Skill required / exercised
    worksite_id: str | None = None      # Where the job is performed
    room_id: str | None = None          # Room containing the worksite
    input_tags: list[str] = field(default_factory=list)
    output_tags: list[str] = field(default_factory=list)
    completion_ticks: int = 100         # Total ticks required to complete
    elapsed_ticks: int = 0              # Ticks of work performed so far
    tags: list[str] = field(default_factory=list)

    def is_complete(self) -> bool:
        return self.elapsed_ticks >= self.completion_ticks

    def progress_fraction(self) -> float:
        if self.completion_ticks <= 0:
            return 1.0
        return min(1.0, self.elapsed_ticks / self.completion_ticks)

    def to_dict(self) -> dict[str, Any]: ...
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "JobRecord": ...


@dataclass
class ReactionDef:
    """A recipe that transforms inputs into outputs at a worksite."""
    reaction_id: str
    label: str                                          # Human-readable name
    worksite_kind: str                                  # Required worksite type
    input_materials: list[MaterialRequirement] = field(default_factory=list)
    output_products: list[ProductOutput] = field(default_factory=list)
    required_skill: str = ""                            # Skill ID needed; "" = no skill needed
    base_duration_ticks: int = 100                      # Base time to complete
    quality_formula: str = "weighted_random"             # "weighted_random" | "fixed"

    # Legacy compatibility shims
    input_tags: list[str] = field(default_factory=list)
    output_tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]: ...
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ReactionDef": ...


@dataclass
class WorksiteRecord:
    """A physical workstation within a room that supports specific jobs."""
    worksite_id: str
    label: str
    kind: str                                           # Worksite type: "forge", "loom", "kitchen"
    room_id: str | None = None
    supported_jobs: list[str] = field(default_factory=list)
    reaction_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]: ...
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorksiteRecord": ...


@dataclass
class SkillRecord:
    """Tracks XP, level, and rust state for a single skill on an actor."""
    skill_id: str
    xp: int = 0
    level: int = 0                      # Derived from XP thresholds
    rusty_level: int = 0                # Levels lost to rust
    unused_counter: int = 0             # Ticks since last use

    def effective_level(self) -> int:
        return max(0, self.level - self.rusty_level)

    def rust_threshold(self) -> int:
        return 500 if self.level >= 15 else 200


# Skill XP thresholds: index = level, value = cumulative XP required
SKILL_XP_THRESHOLDS: list[int] = [
    0, 500, 1100, 1800, 2600, 3500, 4500, 5600, 6800, 8100,
    9500, 11000, 12600, 14300, 16100,
]

SKILL_LEVEL_NAMES: dict[int, str] = {
    0: "Dabbling", 1: "Novice", 2: "Adequate", 3: "Competent",
    4: "Skilled", 5: "Proficient", 6: "Talented", 7: "Adept",
    8: "Expert", 9: "Professional", 10: "Accomplished", 11: "Great",
    12: "Master", 13: "High Master", 14: "Grand Master",
}
# Level 15+ = "Legendary"

# Quality levels for crafted output
QUALITY_LEVELS: dict[int, str] = {
    0: "ordinary", 1: "well-crafted", 2: "finely-crafted",
    3: "superior", 4: "exceptional", 5: "masterwork",
}


@dataclass
class RoomZoneDef:
    """Defines requirements for a room to serve a specific zone function."""
    zone_type: str                      # "bedroom" | "dining" | "workshop" | "hospital" | "temple"
    required_furniture: list[str]       # Furniture tags that must be present
    optional_furniture: list[str] = field(default_factory=list)

ROOM_ZONE_DEFS: dict[str, RoomZoneDef] = {
    "bedroom":  RoomZoneDef("bedroom",  required_furniture=["bed"]),
    "dining":   RoomZoneDef("dining",   required_furniture=["table", "chair"]),
    "workshop": RoomZoneDef("workshop", required_furniture=["worksite"]),
    "hospital": RoomZoneDef("hospital", required_furniture=["bed", "table"]),
    "temple":   RoomZoneDef("temple",   required_furniture=["altar"]),
}
```

### Quality Output Formula

```python
def weighted_random_quality(effective_skill: int, rng_value: float) -> int:
    """
    Determine output quality from effective skill level.
    rng_value: uniform random in [0.0, 1.0).
    Returns: quality level 0-5.

    Distribution shifts based on effective_skill:
    - skill 0-2:  90% ordinary, 10% well-crafted
    - skill 3-5:  50% ordinary, 35% well-crafted, 15% finely-crafted
    - skill 6-8:  20% ordinary, 30% well-crafted, 30% finely-crafted, 15% superior, 5% exceptional
    - skill 9-11: 5% ordinary, 15% well-crafted, 30% finely-crafted, 30% superior, 15% exceptional, 5% masterwork
    - skill 12-14: 5% well-crafted, 15% finely-crafted, 30% superior, 30% exceptional, 20% masterwork
    - skill 15+:  5% finely-crafted, 15% superior, 30% exceptional, 50% masterwork
    """
```

### XP Gain Formula

```python
def xp_on_job_complete(actor: ActorRecord, job: JobRecord, reaction: ReactionDef) -> int:
    base_xp = reaction.base_duration_ticks  # 1 tick = 1 base XP
    mental_attr_bonus = actor.stats.get("focus", 0) * 0.01
    xp_gained = int(base_xp * (1.0 + mental_attr_bonus))
    return xp_gained
```

### Skill Level Derivation

```python
def level_from_xp(xp: int) -> int:
    for level in range(len(SKILL_XP_THRESHOLDS) - 1, -1, -1):
        if xp >= SKILL_XP_THRESHOLDS[level]:
            return level
    return 0
    # XP beyond threshold 14 (16100): level = 14 + (xp - 16100) // 2000, labeled "Legendary"
```

### Skill Rust Algorithm (per tick)

```python
def tick_skill_rust(skill: SkillRecord, used_this_tick: bool) -> None:
    if used_this_tick:
        skill.unused_counter = 0
        skill.rusty_level = max(0, skill.rusty_level - 1)  # Using a skill reduces rust by 1
        return
    skill.unused_counter += 1
    if skill.unused_counter > skill.rust_threshold():
        skill.rusty_level += 1
        skill.unused_counter = 0  # Reset counter after applying rust
```

### Labor Assignment Algorithm

```python
def assign_labor(
    job: JobRecord,
    candidates: list[ActorRecord],
    worksites: list[WorksiteRecord],
) -> str | None:
    """
    Select the best worker for a job.
    1. Filter: actor must have skill_id in skills (or skill_id is None).
    2. Sort by proximity to worksite (Manhattan distance).
    3. Break ties by skill level (higher preferred).
    Returns: actor_id of selected worker, or None if no eligible candidate.
    """
```

## 5. Public API

```python
def job_records_from_settlement(settlement_state: dict[str, Any]) -> list[JobRecord]:
    """
    Extract typed JobRecord list from raw settlement state.
    Preconditions: settlement_state has "jobs" and optionally "construction_queue".
    Postconditions: returns one JobRecord per job/construction entry.
    Returns: list of JobRecord.
    """

def reaction_defs_from_settlement(settlement_state: dict[str, Any]) -> list[ReactionDef]:
    """
    Extract typed ReactionDef list from raw settlement state.
    Preconditions: settlement_state has "rooms" with "workstations".
    Postconditions: returns one ReactionDef per unique workstation type.
    Returns: list of ReactionDef.
    """

def worksite_records_from_settlement(settlement_state: dict[str, Any]) -> list[WorksiteRecord]:
    """
    Extract typed WorksiteRecord list from raw settlement state.
    Preconditions: settlement_state has "rooms".
    Postconditions: returns one WorksiteRecord per room.
    Returns: list of WorksiteRecord.
    """

def assign_labor(
    job: JobRecord,
    candidates: list[ActorRecord],
    worksites: list[WorksiteRecord],
) -> str | None:
    """
    Select the best eligible worker for a job.
    Preconditions: job.status == "queued", candidates is non-empty.
    Postconditions: returns actor_id of chosen worker or None.
    Returns: str | None.
    """

def tick_job(job: JobRecord, actor: ActorRecord, work_speed_mult: float = 1.0) -> bool:
    """
    Advance a job by one tick of work.
    Preconditions: job.status == "active", actor is assigned.
    Postconditions: job.elapsed_ticks incremented. Returns True if job is now complete.
    Returns: bool.
    """

def complete_job(
    job: JobRecord,
    actor: ActorRecord,
    reaction: ReactionDef,
    rng_value: float,
) -> tuple[int, int, list[dict[str, Any]]]:
    """
    Finalize a completed job: award XP, determine quality, produce output items.
    Preconditions: job.is_complete() == True.
    Postconditions: actor skill XP increased; job.status set to "completed".
    Returns: (xp_gained, quality_level, output_items).
    Raises: ValueError if job is not complete.
    """

def cancel_job(job: JobRecord) -> list[str]:
    """
    Cancel a job and return list of refundable input tags.
    Preconditions: job.status in ("queued", "assigned", "active").
    Postconditions: job.status set to "cancelled".
    Returns: list of input_tags that were not yet consumed (refundable).
    """

def tick_skill_rust(skill: SkillRecord, used_this_tick: bool) -> None:
    """
    Update rust state for a single skill.
    Preconditions: skill is a valid SkillRecord.
    Postconditions: unused_counter and rusty_level updated.
    """

def level_from_xp(xp: int) -> int:
    """
    Derive skill level from cumulative XP.
    Preconditions: xp >= 0.
    Returns: int level (0-14 from thresholds, 15+ for legendary).
    """

def weighted_random_quality(effective_skill: int, rng_value: float) -> int:
    """
    Determine crafted item quality from skill and RNG.
    Preconditions: effective_skill >= 0, rng_value in [0.0, 1.0).
    Returns: quality level 0-5.
    """

def validate_room_zone(room: dict[str, Any], zone_type: str) -> tuple[bool, list[str]]:
    """
    Check if a room meets furniture requirements for a zone type.
    Preconditions: zone_type is a key in ROOM_ZONE_DEFS.
    Returns: (is_valid, list_of_missing_furniture).
    Raises: KeyError if zone_type is unknown.
    """
```

## 6. Acceptance Criteria (AC)

AC-01 [FR-01]: Given a raw settlement state with 2 jobs and 1 construction entry, when `job_records_from_settlement` is called, then 3 `JobRecord` instances are returned with correct `kind`, `priority`, `status`, and `skill_id` fields.

AC-02 [FR-02]: Given a `JobRecord` with status `"queued"`, when it is assigned then activated then completed, then status transitions follow `queued -> assigned -> active -> completed` with no skipped states.

AC-03 [FR-02]: Given a `JobRecord` with status `"active"`, when `cancel_job` is called, then status becomes `"cancelled"` and a list of refundable input tags is returned.

AC-04 [FR-03, FR-04]: Given a `ReactionDef` for "forge_sword" with `input_materials = [MaterialRequirement("ore", 2, True), MaterialRequirement("anvil", 1, False)]`, when the reaction is inspected, then the anvil requirement has `consumed = False`.

AC-05 [FR-05]: Given a `ReactionDef` with `output_products = [ProductOutput("iron_sword", "inherit", 1)]` and iron ore as input, when the job completes, then the output item has `material_id = "iron"` (inherited from input).

AC-06 [FR-07]: Given 3 candidate actors where Actor A has smithing=5 at distance 3, Actor B has smithing=8 at distance 1, and Actor C has smithing=3 at distance 1, when `assign_labor` is called for a forge job, then Actor B is selected (closest + highest skill among equidistant).

AC-07 [FR-08, FR-09]: Given an actor with `focus = 10` completing a job with `base_duration_ticks = 100`, when `complete_job` is called, then `xp_gained = int(100 * (1 + 10 * 0.01)) = 110`.

AC-08 [FR-09]: Given a skill with `xp = 1100`, when `level_from_xp` is called, then level is 2 (Adequate). Given `xp = 1099`, level is 1 (Novice).

AC-09 [FR-10]: Given a skill at level 5 with `unused_counter = 200` and `rust_threshold = 200`, when `tick_skill_rust` is called with `used_this_tick = False`, then `rusty_level` increments to 1 and `unused_counter` resets to 0.

AC-10 [FR-10]: Given a legendary skill (level 15) with `unused_counter = 499`, when `tick_skill_rust` is called with `used_this_tick = False`, then `rusty_level` does not change (threshold is 500).

AC-11 [FR-11]: Given `effective_skill = 0` and `rng_value = 0.95`, when `weighted_random_quality` is called, then quality is 1 (well-crafted, since 90% cutoff is at 0.90). Given `rng_value = 0.50`, quality is 0 (ordinary).

AC-12 [FR-12]: Given a room with furniture tags `["bed", "table"]`, when `validate_room_zone("dining")` is called, then result is `(False, ["chair"])` since chair is missing.

AC-13 [FR-12]: Given a room with furniture tags `["bed"]`, when `validate_room_zone("bedroom")` is called, then result is `(True, [])`.

AC-14 [FR-14]: Given a `JobRecord`, when `to_dict()` is called followed by `from_dict()`, then all fields including `completion_ticks` and `elapsed_ticks` round-trip without data loss.

## 7. Performance Requirements
- `assign_labor` must complete in < 2 ms for up to 200 candidates and 50 worksites.
- `tick_job` must complete in < 0.05 ms per job.
- `tick_skill_rust` must complete in < 0.01 ms per skill per actor.
- All quality and XP calculations must be deterministic given the same `rng_value` input.

## 8. Error Handling
- If `assign_labor` receives an empty candidate list, return `None`.
- If `tick_job` is called on a job with status other than `"active"`, raise `ValueError`.
- If `complete_job` is called on a job where `is_complete()` is False, raise `ValueError`.
- If `cancel_job` is called on a job with status `"completed"` or `"cancelled"`, raise `ValueError`.
- If `level_from_xp` receives a negative XP value, return 0.
- If `weighted_random_quality` receives `rng_value` outside [0.0, 1.0), clamp to valid range.
- If a `ReactionDef` references a `worksite_kind` not present in any `WorksiteRecord`, the reaction is skipped during extraction with a warning logged.

## 9. Integration Points
- **Actor Kernel** (`engine.kernel.actor`): `ActorRecord.skills` provides skill levels for eligibility and quality. `ActorRecord.stats["focus"]` feeds XP bonus. `ActorRecord.position` feeds proximity sorting.
- **Colony Simulation Kernel**: `ProductionLedger` shortages inform job priority escalation. Morale cascade `work_speed_mult` feeds into `tick_job`.
- **Inventory System**: `MaterialRequirement` checks consume items from actor/stockpile inventory. `ProductOutput` creates new `ItemStack` entries.
- **World Tick**: `tick_job` is called once per tick for each active job. `tick_skill_rust` is called once per tick for each actor's skills.
- **Room/Zone System**: `WorksiteRecord.room_id` links to room definitions. `validate_room_zone` is called when rooms are modified.

## 10. Test Coverage Target
- Minimum 95% line coverage for the job/reaction kernel module.
- Job state machine: test all valid transitions and reject all invalid transitions.
- Labor assignment: test eligibility filtering, proximity sorting, and skill tie-breaking.
- XP formula: test with 0 focus, positive focus, and boundary XP values at each threshold.
- Skill rust: test unused_counter increment, rust application, rust recovery on use, legendary threshold.
- Quality formula: test each skill bracket with rng_value at 0.0, midpoint, and 0.999.
- Room validation: test each zone type with complete, partial, and empty furniture sets.
- Round-trip serialization for `JobRecord`, `ReactionDef`, `WorksiteRecord`, `SkillRecord`.

---

## Changelog
- **v1 (2026-03-31):** Initial sparse draft with 6 FRs and 4 ACs.
- **v2 (2026-04-01):** Full rewrite. Added MaterialRequirement/ProductOutput dataclasses, SkillRecord with XP thresholds and rust, quality formula, labor assignment algorithm, room/zone validation, 14 FRs, 14 ACs, complete data structures and public API.
