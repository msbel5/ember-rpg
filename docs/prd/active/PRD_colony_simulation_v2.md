# PRD: Colony Simulation Kernel V2
**Project:** Ember RPG
**Phase:** 3
**Author:** Alcyone (CAPTAIN)
**Date:** 2026-04-01
**Status:** Draft

---

## 1. Purpose
The Colony Simulation Kernel manages the living state of a player's settlement by tracking individual actor needs, aggregating them into colony-wide pressure metrics, detecting shortages, cascading morale consequences, and generating quest hooks from pressure state. It replaces ad-hoc settlement helpers with a deterministic, typed system that drives behavior changes, production decisions, and narrative events without any LLM dependency. This module covers DF-inspired mechanisms M03 (Need/Happiness/Stress), M04 (partial job-need interaction), M11 (Trade partial), M12 (Migration partial), M16 (Building/Room), and M19 (Farming partial).

## 2. Scope
- **In scope:** `NeedState` per-actor need tracking with decay and fulfillment; `ColonyPressureState` aggregate colony metrics; morale cascade thresholds and behavior modifiers; production ledger shortage detection; quest hook generation from pressure; pressure tag system; room quality contribution to morale; farming yield contribution to food pressure.
- **Out of scope:** Trade caravan AI routing; diplomacy resolution; UI dashboard rendering; AI narration text generation; full migration/population growth simulation (only the pressure signal that triggers migration is in scope).

## 2.1 Runtime Authority Closure

Colony state is authoritative only when it participates in the live campaign
tick, not when it exists as a typed projection. On every world advance or
commander command, runtime must apply the settlement loop in this order:

1. need decay
2. morale cascade
3. production ledger recompute
4. farm growth and harvest
5. shortage / surplus propagation
6. quest seed regeneration

Authoritative runtime surfaces:
- `frp-backend/engine/api/campaign/live_kernel.py`
- `frp-backend/engine/api/campaign/runtime.py`
- `frp-backend/engine/api/campaign/persistence.py`

`campaign.settlement` remains a presentation aggregate. Runtime authority lives
in canonical `colony_pressure`, `production_ledger`, `jobs`, `reactions`,
`worksites`, and persisted kernel payload slices.

## 3. Functional Requirements (FR)

FR-01: The kernel must maintain a typed `NeedState` per actor with individual need values for: `eat`, `drink`, `sleep`, `pray`, `socialize`, `craft`, `train`, `admire_art`.

FR-02: Each need must decay deterministically per tick at its configured `decay_rate`. When a need value reaches 0, the actor enters a `desperate` state for that need.

FR-03: Need fulfillment occurs when an actor performs the corresponding activity. The fulfillment amount is determined by the activity's `fulfillment_base` and the facility's `quality` modifier: `amount = fulfillment_base * (1.0 + quality * 0.1)`.

FR-04: The kernel must compute a per-actor `mood` string from the aggregate of all need satisfaction levels using defined thresholds: `content` (weighted_satisfaction >= 75), `unhappy` (>= 50), `miserable` (>= 25), `breakdown` (< 25).

FR-05: The kernel must maintain a typed `ColonyPressureState` with fields: `food`, `safety`, `morale`, `supply`, `housing`, `unrest`, `shortages`, `pressure_tags`, `quest_seeds`.

FR-06: Colony pressure must be computed deterministically from settlement runtime state using the exact formulas documented in Section 4.

FR-07: The kernel must apply morale cascade rules based on `unrest` thresholds: content (unrest < 25), unhappy (25-50), miserable (50-75), breakdown (> 75). Each tier applies specific behavior modifiers to affected actors.

FR-08: The kernel must detect production shortages by comparing need levels against threshold (need_level >= 3 triggers shortage) and populate the `shortages` list accordingly.

FR-09: The kernel must generate typed `quest_seeds` from the current shortage list, mapping each shortage type to a quest template.

FR-10: The kernel must assign `pressure_tags` when metrics drop below 55 (food_insecure, unsafe, resource_strain, housing_strain) or when unrest >= 50.

FR-11: The `ProductionLedger` must track economy state, shortages, surpluses, and quest seeds as typed fields with deterministic derivation from settlement state.

FR-12: Room quality must contribute to morale: each room adds +2 morale per room present. Rooms missing required furniture reduce their contribution to 0.

FR-13: The farming subsystem must contribute to food pressure: each active farm plot reduces food need_level by 1 (capped at 0). Unharvested or fallow plots contribute nothing.

FR-14: Migration pressure signal: when `housing > 80` and `morale > 70` and `food > 60`, the kernel must emit a `migration_candidate` pressure tag indicating the colony can accept new residents.

## 4. Data Structures

```python
@dataclass
class NeedDef:
    """Static definition of a single need type."""
    need_id: str                # e.g. "eat", "drink", "sleep"
    label: str                  # Human-readable name
    decay_rate: float           # Amount subtracted per tick (e.g. 0.5)
    fulfillment_base: float     # Base amount restored per fulfillment event
    desperate_threshold: float  # Below this value, actor is desperate (default 10.0)
    weight: float               # Contribution weight to overall mood (default 1.0)

# Canonical need definitions
NEED_DEFS: dict[str, NeedDef] = {
    "eat":          NeedDef("eat",          "Hunger",       decay_rate=0.8,  fulfillment_base=60.0, desperate_threshold=10.0, weight=1.5),
    "drink":        NeedDef("drink",        "Thirst",       decay_rate=1.0,  fulfillment_base=70.0, desperate_threshold=10.0, weight=1.5),
    "sleep":        NeedDef("sleep",        "Rest",         decay_rate=0.4,  fulfillment_base=80.0, desperate_threshold=15.0, weight=1.2),
    "pray":         NeedDef("pray",         "Spirituality", decay_rate=0.2,  fulfillment_base=40.0, desperate_threshold=5.0,  weight=0.6),
    "socialize":    NeedDef("socialize",    "Social",       decay_rate=0.3,  fulfillment_base=35.0, desperate_threshold=10.0, weight=0.8),
    "craft":        NeedDef("craft",        "Industry",     decay_rate=0.15, fulfillment_base=30.0, desperate_threshold=5.0,  weight=0.5),
    "train":        NeedDef("train",        "Training",     decay_rate=0.15, fulfillment_base=30.0, desperate_threshold=5.0,  weight=0.5),
    "admire_art":   NeedDef("admire_art",   "Aesthetics",   decay_rate=0.1,  fulfillment_base=25.0, desperate_threshold=5.0,  weight=0.4),
}


@dataclass
class NeedState:
    """Per-actor need tracker. Each value ranges 0.0-100.0."""
    values: dict[str, float]        # need_id -> current satisfaction (0=empty, 100=full)
    mood: str = "steady"            # "content" | "unhappy" | "miserable" | "breakdown" | "steady"
    modifiers: dict[str, Any] = field(default_factory=dict)
    # modifiers holds behavior changes keyed by modifier_id:
    #   "work_speed_mult": float    (1.0 = normal, <1.0 = slowdown)
    #   "social_hostility": bool    (true = may pick fights)
    #   "task_refusal": bool        (true = may refuse non-critical tasks)
    #   "tantrum_risk": float       (0.0-1.0 probability per tick)

    def weighted_satisfaction(self) -> float:
        """Return weighted average satisfaction across all needs, 0.0-100.0."""
        ...

    def to_dict(self) -> dict[str, Any]: ...
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NeedState": ...
    @classmethod
    def from_legacy(cls, legacy: Any) -> "NeedState": ...


@dataclass
class ColonyPressureState:
    """Aggregate colony health metrics. Each metric ranges 0-100."""
    food: int                               # 100 = well-fed, 0 = starvation
    safety: int                             # 100 = secure, 0 = under siege
    morale: int                             # 100 = thriving, 0 = despair
    supply: int                             # 100 = abundant, 0 = depleted
    housing: int                            # 100 = spacious, 0 = overcrowded
    unrest: int                             # 0 = peaceful, 100 = riot
    shortages: list[str] = field(default_factory=list)
    pressure_tags: list[str] = field(default_factory=list)
    quest_seeds: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]: ...
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ColonyPressureState": ...


@dataclass
class ProductionLedger:
    """Tracks economy input/output and shortage/surplus state."""
    economy: dict[str, Any] = field(default_factory=dict)
    shortages: list[str] = field(default_factory=list)
    surpluses: list[str] = field(default_factory=list)
    quest_seeds: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]: ...
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProductionLedger": ...


@dataclass
class MoraleCascade:
    """Defines behavior modifiers applied at each unrest tier."""
    tier: str                   # "content" | "unhappy" | "miserable" | "breakdown"
    unrest_min: int             # Inclusive lower bound
    unrest_max: int             # Exclusive upper bound (100 for breakdown)
    work_speed_mult: float      # Multiplier on task completion speed
    social_hostility: bool      # Whether actors may initiate fights
    task_refusal: bool          # Whether actors may refuse non-critical tasks
    tantrum_risk: float         # Per-tick probability of tantrum/berserk episode

MORALE_CASCADE_TIERS: list[MoraleCascade] = [
    MoraleCascade("content",    0,  25, work_speed_mult=1.0,  social_hostility=False, task_refusal=False, tantrum_risk=0.0),
    MoraleCascade("unhappy",   25,  50, work_speed_mult=0.8,  social_hostility=False, task_refusal=False, tantrum_risk=0.0),
    MoraleCascade("miserable", 50,  75, work_speed_mult=0.5,  social_hostility=True,  task_refusal=True,  tantrum_risk=0.02),
    MoraleCascade("breakdown", 75, 101, work_speed_mult=0.2,  social_hostility=True,  task_refusal=True,  tantrum_risk=0.10),
]


@dataclass
class QuestSeed:
    """A typed quest hook generated from colony pressure."""
    quest_id: str               # e.g. "pressure_food"
    kind: str                   # shortage type: "food", "materials", "security"
    title: str                  # Human-readable quest title
    priority: int = 3           # 1 = critical, 5 = low
    source_pressure: str = ""   # Which pressure metric triggered this
```

### Pressure Update Formulas

These formulas are implemented in `colony_pressure_from_settlement` and must remain deterministic:

```
food    = max(0, 100 - needs["food"] * 15)
safety  = max(0, 100 - len(alerts) * 12 - needs["security"] * 10 + drafted_count * 5)
morale  = max(0, 100 - len(alerts) * 8 - len(shortages) * 10 + len(rooms) * 2)
supply  = max(0, 100 - needs["materials"] * 15 - len(construction_queue) * 6)
housing = max(0, 100 - max(0, resident_count - max(1, bed_count)) * 20)
unrest  = min(100, len(alerts) * 14 + len(shortages) * 12 + len(historical_pressure) * 6)
```

### Pressure Tag Assignment

```
if food < 55:    pressure_tags.append("food_insecure")
if safety < 55:  pressure_tags.append("unsafe")
if supply < 55:  pressure_tags.append("resource_strain")
if housing < 55: pressure_tags.append("housing_strain")
if unrest >= 50: pressure_tags.append("unrest")
if housing > 80 and morale > 70 and food > 60: pressure_tags.append("migration_candidate")
```

### Need Decay Algorithm (per tick, per actor)

```python
for need_id, need_def in NEED_DEFS.items():
    current = actor.needs.values.get(need_id, 100.0)
    current = max(0.0, current - need_def.decay_rate)
    actor.needs.values[need_id] = current
```

### Need Fulfillment Algorithm

```python
def fulfill_need(actor: ActorRecord, need_id: str, facility_quality: int = 0) -> float:
    need_def = NEED_DEFS[need_id]
    amount = need_def.fulfillment_base * (1.0 + facility_quality * 0.1)
    old = actor.needs.values.get(need_id, 0.0)
    actor.needs.values[need_id] = min(100.0, old + amount)
    return actor.needs.values[need_id] - old
```

### Mood Computation

```python
def compute_mood(needs: NeedState) -> tuple[str, dict[str, Any]]:
    avg = needs.weighted_satisfaction()
    if avg >= 75.0:
        return "content", {"work_speed_mult": 1.0}
    elif avg >= 50.0:
        return "unhappy", {"work_speed_mult": 0.8}
    elif avg >= 25.0:
        return "miserable", {"work_speed_mult": 0.5, "social_hostility": True, "task_refusal": True, "tantrum_risk": 0.02}
    else:
        return "breakdown", {"work_speed_mult": 0.2, "social_hostility": True, "task_refusal": True, "tantrum_risk": 0.10}
```

### Quest Hook Generation

```python
SHORTAGE_QUEST_MAP: dict[str, dict[str, Any]] = {
    "food":      {"kind": "food",      "title": "Address Food Pressure",      "priority": 1},
    "materials": {"kind": "materials", "title": "Address Materials Pressure",  "priority": 2},
    "security":  {"kind": "security",  "title": "Address Security Pressure",  "priority": 1},
}

def quest_seeds_from_shortages(shortages: list[str]) -> list[QuestSeed]:
    seeds = []
    for shortage in shortages:
        template = SHORTAGE_QUEST_MAP.get(shortage, {
            "kind": shortage,
            "title": f"Address {shortage.title()} Pressure",
            "priority": 3,
        })
        seeds.append(QuestSeed(
            quest_id=f"pressure_{shortage}",
            kind=template["kind"],
            title=template["title"],
            priority=template["priority"],
            source_pressure=shortage,
        ))
    return seeds
```

## 5. Public API

```python
def decay_needs(actor: ActorRecord, tick_count: int = 1) -> NeedState:
    """
    Decay all needs for the given actor over tick_count ticks.
    Preconditions: actor.needs.values is populated.
    Postconditions: each need value is reduced by decay_rate * tick_count, clamped to [0, 100].
    Returns: the updated NeedState (also mutates actor.needs in place).
    """

def fulfill_need(actor: ActorRecord, need_id: str, facility_quality: int = 0) -> float:
    """
    Fulfill a specific need for the actor.
    Preconditions: need_id is a valid key in NEED_DEFS.
    Postconditions: need value increased by fulfillment_base * (1 + quality * 0.1), clamped to 100.
    Returns: the actual amount restored.
    Raises: KeyError if need_id is not in NEED_DEFS.
    """

def compute_mood(needs: NeedState) -> tuple[str, dict[str, Any]]:
    """
    Compute mood tier and behavior modifiers from current need satisfaction.
    Preconditions: needs.values contains at least one entry.
    Postconditions: returns (mood_string, modifiers_dict).
    Returns: tuple of mood label and modifier dictionary.
    """

def colony_pressure_from_settlement(settlement_state: dict[str, Any]) -> ColonyPressureState:
    """
    Compute aggregate colony pressure from raw settlement state.
    Preconditions: settlement_state contains keys: needs, alerts, residents, rooms,
                   economy, construction_queue, faction_pressure.
    Postconditions: returns a fully populated ColonyPressureState.
    Returns: ColonyPressureState with deterministic metric values.
    """

def production_ledger_from_settlement(settlement_state: dict[str, Any]) -> ProductionLedger:
    """
    Derive production ledger (shortages, surpluses, quest seeds) from settlement state.
    Preconditions: settlement_state contains keys: needs, economy.
    Postconditions: returns a ProductionLedger with shortages detected when need_level >= 3.
    Returns: ProductionLedger instance.
    """

def apply_morale_cascade(actors: list[ActorRecord], unrest: int) -> None:
    """
    Apply morale cascade modifiers to all actors based on colony unrest level.
    Preconditions: unrest in [0, 100].
    Postconditions: each actor's needs.modifiers updated with the tier's behavior modifiers.
    """

def quest_seeds_from_shortages(shortages: list[str]) -> list[QuestSeed]:
    """
    Generate quest hook seeds from a list of active shortages.
    Preconditions: each entry in shortages is a recognized shortage type string.
    Postconditions: returns one QuestSeed per shortage.
    Returns: list of QuestSeed instances.
    """
```

## 6. Acceptance Criteria (AC)

AC-01 [FR-01]: Given a newly created actor, when `NeedState` is initialized with defaults, then `values` contains all 8 need types (`eat`, `drink`, `sleep`, `pray`, `socialize`, `craft`, `train`, `admire_art`) each set to 100.0.

AC-02 [FR-02]: Given an actor with `eat` at 80.0 and `decay_rate` 0.8, when `decay_needs` is called for 10 ticks, then `eat` equals 72.0.

AC-03 [FR-02]: Given an actor with `drink` at 5.0 and `decay_rate` 1.0, when `decay_needs` is called for 10 ticks, then `drink` equals 0.0 (clamped, not negative).

AC-04 [FR-03]: Given an actor with `eat` at 20.0 and a facility with quality 2, when `fulfill_need("eat")` is called, then `eat` equals min(100.0, 20.0 + 60.0 * 1.2) = 92.0.

AC-05 [FR-04]: Given an actor whose weighted satisfaction is 80.0, when `compute_mood` is called, then mood is `"content"` and `work_speed_mult` is 1.0.

AC-06 [FR-04]: Given an actor whose weighted satisfaction is 20.0, when `compute_mood` is called, then mood is `"breakdown"` and `tantrum_risk` is 0.10.

AC-07 [FR-05, FR-06]: Given a settlement with `needs.food = 4`, `alerts = [a1, a2]`, `residents = 5`, `rooms = 3 (with 3 beds)`, `construction_queue = [c1]`, `needs.materials = 2`, `needs.security = 1`, `faction_pressure = [p1]`, when `colony_pressure_from_settlement` is called, then:
- food = max(0, 100 - 4*15) = 40
- safety = max(0, 100 - 2*12 - 1*10 + 0*5) = 66
- morale = max(0, 100 - 2*8 - 1*10 + 3*2) = 80 (where shortages = ["food"], len = 1)
- supply = max(0, 100 - 2*15 - 1*6) = 64
- housing = max(0, 100 - max(0, 5 - max(1,3)) * 20) = 60
- unrest = min(100, 2*14 + 1*12 + 1*6) = 46

AC-08 [FR-07]: Given unrest = 60, when `apply_morale_cascade` is called on a list of actors, then each actor's modifiers contain `work_speed_mult = 0.5`, `social_hostility = True`, `task_refusal = True`, `tantrum_risk = 0.02`.

AC-09 [FR-08, FR-09]: Given `needs.food = 3` and `needs.materials = 1`, when `production_ledger_from_settlement` is called, then `shortages == ["food"]` and `surpluses` contains `"materials"`, and `quest_seeds` contains one seed with `kind = "food"`.

AC-10 [FR-10]: Given food = 40, safety = 70, supply = 50, housing = 60, unrest = 30, when pressure tags are computed, then tags contain `"food_insecure"` and `"resource_strain"` but not `"unsafe"`, `"housing_strain"`, or `"unrest"`.

AC-11 [FR-11]: Given a `ProductionLedger` instance with non-empty economy, shortages, surpluses, and quest_seeds, when `to_dict()` is called and then `from_dict()` is called on the result, then all fields round-trip without data loss.

AC-12 [FR-12]: Given 4 rooms in settlement state with no alerts and no shortages, when morale is computed, then the room contribution is +8 (4 * 2) applied to the morale formula.

AC-13 [FR-13]: Given 2 active farm plots and `needs.food = 5`, when farm contribution is applied before pressure calculation, then effective food need_level is max(0, 5 - 2) = 3.

AC-14 [FR-14]: Given housing = 85, morale = 75, food = 65, when pressure tags are computed, then `"migration_candidate"` is present in the tags list.

## 7. Performance Requirements
- `colony_pressure_from_settlement` must complete in < 5 ms for settlements with up to 200 residents, 50 rooms, and 20 alerts.
- `decay_needs` for a single actor must complete in < 0.1 ms.
- All operations must be deterministic: identical input must produce identical output with no random or time-dependent components.

## 8. Error Handling
- If `settlement_state` is missing the `needs` key, default to `{}` (all needs at 0).
- If `settlement_state` is missing `alerts`, `residents`, `rooms`, `construction_queue`, or `faction_pressure`, default to empty lists.
- If a need value would go below 0.0 after decay, clamp to 0.0.
- If a need value would exceed 100.0 after fulfillment, clamp to 100.0.
- If `fulfill_need` is called with an unknown `need_id`, raise `KeyError`.
- If `ColonyPressureState.from_dict` receives non-integer values for metric fields, cast to `int`.
- Pressure metrics are clamped: food/safety/morale/supply/housing to [0, 100], unrest to [0, 100].

## 9. Integration Points
- **Actor Kernel** (`engine.kernel.actor`): `NeedState` is stored on `ActorRecord.needs`. Mood and modifiers feed into actor behavior decisions.
- **Job/Reaction Kernel** (`engine.kernel.colony`): `ProductionLedger` shortages inform job prioritization. Morale cascade affects work speed.
- **World Tick**: `decay_needs` is called once per tick for each living actor. `colony_pressure_from_settlement` is called once per tick for the active settlement.
- **Quest Generation**: `quest_seeds` from `ColonyPressureState` are consumed by the quest engine to create player-facing quests.
- **Schedule System**: Actor schedules determine when need fulfillment activities occur (eating during meal period, sleeping during rest period).

## 10. Test Coverage Target
- Minimum 95% line coverage for the colony simulation module.
- All 8 need types must have decay and fulfillment tests.
- All 4 morale cascade tiers must have dedicated test cases.
- Pressure formula boundary conditions: 0, mid-range, and max for each metric.
- Round-trip serialization for `NeedState`, `ColonyPressureState`, `ProductionLedger`.
- Quest seed generation for each shortage type.
- Pressure tag assignment at boundary values (54, 55, 56 for threshold tests).
- Edge case: settlement with 0 residents, 0 rooms, 0 alerts.

---

## Changelog
- **v1 (2026-03-31):** Initial sparse draft with 6 FRs and 4 ACs.
- **v2 (2026-04-01):** Full rewrite. Added NeedDef with 8 need types, decay/fulfillment formulas, morale cascade tiers, pressure update formulas from code, quest hook mapping, 14 FRs, 14 ACs, complete data structures and public API.
